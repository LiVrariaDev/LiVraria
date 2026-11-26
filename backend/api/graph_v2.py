"""会話グラフ v2: 司書のレファレンスインタビューの流れをグラフの構造にしたもの。

LIVRARIA_GRAPH=v2 のときに llm_chat から呼ばれる（既定は v1）。設計は SilverBullet の
Notes/LiVraria/Graph-Redesign を参照。

    START → understand → route ┬→ interview ─────────────────────→ END
                               ├→ crd → plan → search → select ─→ END
                               └→ answer ────────────────────────→ END

- understand / plan / select は構造化出力（pydantic）。interview / answer は文章
- route / crd / search はコードだけで動く（挙動を説明でき、再現できる）
- 失敗したときのやり直しはノード単位で行う。グラフ全体はやり直さない
- 429 はノードでは握りつぶさず llm_chat_v2 まで上げ、混雑の定型文を返す
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, List, Literal, Optional, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field, ValidationError

from backend import PROMPTS_DIR
from backend.api import llm as llm_module
from backend.api import llm_usage
from backend.api.llm_usage import is_rate_limit_error
from backend.api.trace_store import TraceStep, current_turn
from backend.search import crd

logger = logging.getLogger("uvicorn.error")

PROMPTS_V2_DIR = Path(PROMPTS_DIR, "v2")

# 各 LLM ノードの出力枠。思考で出力枠を使い切らないよう、文章を返すノードは余裕を持たせる
MAX_TOKENS = {"understand": 1024, "plan": 512, "select": 2048, "interview": 1024, "answer": 1024}
EMPTY_RETRIES = 1           # 文章を返すノードが空応答だったときのやり直し回数
SELECT_RETRIES = 1          # 選書の構造化出力が読み取れなかったときのやり直し回数
HISTORY_TURNS_FOR_LLM = 12  # LLM に渡す直近の履歴のメッセージ数
HISTORY_CHARS_FOR_LLM = 300 # 履歴の1メッセージあたりの最大文字数
MAX_QUERIES = 4
MAX_WORDS_PER_QUERY = 2
SEARCH_COUNT_PER_QUERY = 10
CANDIDATE_LIMIT = 20
ENOUGH_CANDIDATES = 10      # 全組の AND 検索でこれだけ集まれば、0件だった組の OR 検索のやり直しを省く
CAPTION_MIN_CHARS = 30      # これより短い内容紹介は「内容紹介なし」として優先度を下げる
MAX_PICKS = 3
CRD_HINT_LIMIT = 3
PROFILE_LIST_LIMIT = 8
PROFILE_TEXT_LIMIT = 40

INTENTS = ("chit_chat", "need_more", "ready", "ask_book", "refine", "lookup_title")
SEARCH_INTENTS = ("ready", "refine", "lookup_title")
CRD_INTENTS = ("ready", "refine", "lookup_title")
SLOTS = ("ど真ん中", "少し外す", "意外な1冊")

MESSAGE_NO_CANDIDATES = "ごめんなさい、今の条件では本が見つかりませんでした。言葉を変えて、もう少し教えていただけますか。"
MESSAGE_NO_PICKS = "ごめんなさい、ぴったりの本を選べませんでした。条件を少し変えて、一緒に探してみませんか。"


# ---------------------------------------------------------------------------
# データ構造
# ---------------------------------------------------------------------------

class ReadingProfile(BaseModel):
	"""読書プロフィール。項目は増やしすぎない（抽出が不安定になるため）。"""
	interests: List[str] = Field(default_factory=list, description="興味のあるテーマや題材（名詞）")
	mood: str = Field("", description="今の気分や状況")
	purpose: Literal["楽しみ", "学び", "調べ物", "贈り物", "不明"] = Field("不明", description="読む目的")
	reader: Literal["自分", "子ども", "ほかの人"] = Field("自分", description="誰が読むか")
	level: Literal["入門", "普通", "専門", "不明"] = Field("不明", description="内容の水準")
	avoid: List[str] = Field(default_factory=list, description="避けたいもの")
	mentioned_books: List[str] = Field(default_factory=list, description="会話に出た本")


class UnderstandOutput(BaseModel):
	profile: ReadingProfile = Field(description="更新後の読書プロフィール（すべての項目）")
	intent: Literal["chit_chat", "need_more", "ready", "ask_book", "refine", "lookup_title"] = Field(description="今回の発言の意図")


class SearchQuery(BaseModel):
	keywords: List[str] = Field(description="1〜2語の名詞")


class PlanOutput(BaseModel):
	queries: List[SearchQuery] = Field(description="検索キーワードの組（2〜4組）")


class Pick(BaseModel):
	id: int = Field(description="候補の番号")
	slot: str = Field(description="枠: ど真ん中 / 少し外す / 意外な1冊")
	reason: str = Field(description="選んだ理由（60字以内）")


class SelectOutput(BaseModel):
	picks: List[Pick] = Field(default_factory=list, description="選んだ本（最大3冊。0冊でもよい）")
	response: str = Field("", description="利用者への紹介の言葉（140字以内）")


class V2State(TypedDict, total=False):
	message: str                 # 今回の利用者の発言
	messages: List[BaseMessage]  # 表示用テキストの履歴（今回の発言は含まない）
	user_context: str            # ニックネームや AI Insights
	profile: dict
	last_picks: List[dict]
	intent: str
	route: str
	crd_hints: List[dict]
	queries: List[List[str]]
	candidates: List[dict]
	picks: List[dict]
	response_text: str
	expression: str
	path: List[str]              # 通ったノード（表情の決定とトレース用）


class _Options:
	"""LLM の呼び出しに使う設定（llm_chat の引数から作る）。"""

	def __init__(self, backend: Optional[str], temperature: float):
		self.backend = backend
		self.temperature = temperature


# ---------------------------------------------------------------------------
# 補助関数
# ---------------------------------------------------------------------------

def load_v2_prompt(name: str, **values: str) -> str:
	"""prompts/v2/<name>.md を読み、{{key}} を値で置き換える。"""
	text = Path(PROMPTS_V2_DIR, f"{name}.md").read_text(encoding="utf-8")
	if "{{persona}}" in text:
		values.setdefault("persona", Path(PROMPTS_V2_DIR, "persona.md").read_text(encoding="utf-8").strip())
	for key, value in values.items():
		text = text.replace("{{" + key + "}}", value)
	return text


def _clean_list(values: Any, limit: int = PROFILE_LIST_LIMIT) -> List[str]:
	result: List[str] = []
	for value in values or []:
		text = str(value).strip()[:PROFILE_TEXT_LIMIT]
		if text and text not in result:
			result.append(text)
	return result[:limit]


def normalize_profile(data: Any) -> ReadingProfile:
	"""保存されていた dict などから ReadingProfile を作る。不正な値は既定値にする。"""
	if isinstance(data, ReadingProfile):
		raw = data.model_dump()
	elif isinstance(data, dict):
		raw = dict(data)
	else:
		raw = {}
	defaults = ReadingProfile()
	cleaned = {
		"interests": _clean_list(raw.get("interests")),
		"mood": str(raw.get("mood") or "").strip()[:PROFILE_TEXT_LIMIT],
		"avoid": _clean_list(raw.get("avoid")),
		"mentioned_books": _clean_list(raw.get("mentioned_books")),
	}
	for key in ("purpose", "reader", "level"):
		value = raw.get(key)
		try:
			ReadingProfile(**{key: value})
			cleaned[key] = value
		except (ValidationError, TypeError):
			cleaned[key] = getattr(defaults, key)
	return ReadingProfile(**cleaned)


def profile_text(profile: ReadingProfile) -> str:
	return json.dumps(profile.model_dump(), ensure_ascii=False, indent=1)


def user_context_text(user_context: str) -> str:
	return f"## 利用者について\n\n{user_context.strip()}" if user_context and user_context.strip() else ""


def has_search_material(profile: ReadingProfile, intent: str) -> bool:
	"""検索に使える手がかりがプロフィールにあるか。"""
	if intent == "lookup_title":
		return bool(profile.mentioned_books or profile.interests)
	return bool(profile.interests or profile.mentioned_books or profile.mood)


def decide_route(intent: str, profile: ReadingProfile, last_picks: List[dict]) -> str:
	"""意図とプロフィールの埋まり具合から次のノードを決める（"interview" / "search" / "answer"）。"""
	if intent == "ask_book":
		return "answer" if last_picks else "interview"
	if intent in SEARCH_INTENTS and has_search_material(profile, intent):
		return "search"
	return "interview"


def _transcript(messages: List[BaseMessage]) -> str:
	lines = []
	for msg in messages[-HISTORY_TURNS_FOR_LLM:]:
		speaker = "利用者" if isinstance(msg, HumanMessage) else "司書"
		text = llm_module.extract_user_visible_text(msg.content)[:HISTORY_CHARS_FOR_LLM]
		if text:
			lines.append(f"{speaker}: {text}")
	return "\n".join(lines) or "（なし）"


def _chat_messages(system_prompt: str, history: List[BaseMessage], message: str) -> List[BaseMessage]:
	"""文章を返すノード用: システム指示 + 直近の履歴 + 今回の発言。"""
	recent = []
	for msg in history[-HISTORY_TURNS_FOR_LLM:]:
		text = llm_module.extract_user_visible_text(msg.content)[:HISTORY_CHARS_FOR_LLM]
		if not text:
			continue
		recent.append(HumanMessage(content=text) if isinstance(msg, HumanMessage) else AIMessage(content=text))
	return [SystemMessage(content=system_prompt), *recent, HumanMessage(content=message)]


def _book_label(book: dict) -> str:
	authors = book.get("authors") or []
	author = authors[0] if authors else "不明"
	return f"『{book.get('title') or '不明'}』 - {author}"


def _picks_text(picks: List[dict]) -> str:
	if not picks:
		return "（なし）"
	lines = []
	for i, book in enumerate(picks, 1):
		lines.append(f"{i}. {_book_label(book)}")
		if book.get("recommendation_slot"):
			lines.append(f"   枠: {book['recommendation_slot']}")
		if book.get("recommendation_reason"):
			lines.append(f"   紹介した理由: {book['recommendation_reason']}")
		caption = llm_module.clean_caption(book.get("itemCaption"), limit=400)
		if caption:
			lines.append(f"   内容: {caption}")
	return "\n".join(lines)


def _crd_hints_text(hints: List[dict]) -> str:
	if not hints:
		return "（なし）"
	lines = []
	for hint in hints:
		parts = [f"- 相談: {hint.get('question') or '（不明）'}"]
		if hint.get("keywords"):
			parts.append(f"  キーワード: {'、'.join(hint['keywords'])}")
		if hint.get("ndc"):
			parts.append(f"  NDC: {'、'.join(hint['ndc'])}")
		if hint.get("process"):
			parts.append(f"  探し方: {hint['process']}")
		lines.append("\n".join(parts))
	return "\n".join(lines)


def _caption_length(book: dict) -> int:
	return len(llm_module.clean_caption(book.get("itemCaption"), limit=10_000))


def _book_key(book: dict) -> str:
	isbn = str(book.get("isbn") or "").strip()
	if isbn:
		return f"isbn:{isbn}"
	authors = book.get("authors") or []
	return f"title:{book.get('title') or ''}/{authors[0] if authors else ''}"


def _public_book(candidate: dict) -> dict:
	"""フロントに返す本の dict（v1 と同じ楽天の項目）。候補の内部用の項目は除く。"""
	return {k: v for k, v in candidate.items() if k not in ("candidate_id", "source")}


def _usage(message: Any) -> Optional[dict]:
	usage = getattr(message, "usage_metadata", None)
	return dict(usage) if usage else None


def _trace_step(node: str, started: datetime, *, attempt: int = 0, ai_text: Optional[str] = None,
	            results: Optional[List[dict]] = None, usage: Optional[dict] = None,
	            error: Optional[BaseException] = None) -> None:
	"""ノード1回分の処理をトレースに記録する。失敗しても会話は止めない。"""
	try:
		turn = current_turn.get()
		if turn is None:
			return
		ended = datetime.now()
		step = TraceStep(
			index=len(turn.steps),
			node=node,
			attempt=attempt,
			started_at=started.isoformat(),
			ended_at=ended.isoformat(),
			duration_ms=int((ended - started).total_seconds() * 1000),
			ai_text=ai_text,
			usage=usage,
		)
		for result in results or []:
			step.tool_results.append({
				"name": result.get("name"),
				"content": str(result.get("content"))[:llm_module.TRACE_CONTENT_LIMIT],
			})
		if error is not None:
			step.error = {"type": type(error).__name__, "message": str(error)}
		turn.steps.append(step)
	except Exception:
		logger.exception("Failed to record v2 trace step")


def _record_turn_summary(result: dict) -> None:
	"""意図、振り分け、通ったノード、プロフィール、レファ協の手がかりをターンのトレースに記録する。"""
	try:
		turn = current_turn.get()
		if turn is None:
			return
		turn.intent = result.get("intent")
		turn.route = result.get("route")
		turn.path = list(result.get("path") or [])
		turn.profile = result.get("profile")
		turn.crd_hints = list(result.get("crd_hints") or [])
	except Exception:
		logger.exception("Failed to record v2 turn summary")


# ---------------------------------------------------------------------------
# LLM 呼び出し
# ---------------------------------------------------------------------------

def _invoke_structured(role: str, schema: type[BaseModel], messages: List[BaseMessage], options: _Options, max_tokens: int):
	"""構造化出力で LLM を呼ぶ。読み取れなければ (None, raw, error)。429 は例外のまま上げる。"""
	llm = llm_module.get_llm(role=role, backend=options.backend, temperature=options.temperature, max_tokens=max_tokens)
	runnable = llm.with_structured_output(schema, include_raw=True)
	try:
		result = runnable.invoke(messages)
	except Exception as exc:
		llm_usage.record_error(role, exc)
		if is_rate_limit_error(exc):
			raise
		logger.warning("[WARNING] v2 structured call failed (%s/%s): %s", role, schema.__name__, exc)
		return None, None, exc

	raw = result.get("raw") if isinstance(result, dict) else None
	parsed = result.get("parsed") if isinstance(result, dict) else result
	llm_usage.record_success(role, raw)
	if isinstance(parsed, dict):
		try:
			parsed = schema.model_validate(parsed)
		except ValidationError as exc:
			return None, raw, exc
	if not isinstance(parsed, schema):
		error = result.get("parsing_error") if isinstance(result, dict) else None
		return None, raw, error or ValueError("structured output could not be parsed")
	return parsed, raw, None


def _invoke_text(role: str, messages: List[BaseMessage], options: _Options, max_tokens: int):
	"""文章を返すノード用。空応答や内部形式の混入は ""。429 は例外のまま上げる。"""
	llm = llm_module.get_llm(role=role, backend=options.backend, temperature=options.temperature, max_tokens=max_tokens)
	try:
		response = llm.invoke(messages)
	except Exception as exc:
		llm_usage.record_error(role, exc)
		if is_rate_limit_error(exc):
			raise
		logger.warning("[WARNING] v2 text call failed (%s): %s", role, exc)
		return "", None, exc
	llm_usage.record_success(role, response)
	text = llm_module.extract_user_visible_text(response.content)
	if llm_module.contains_internal_response(text):
		logger.error("[ERROR] v2 model returned internal tool or thought text")
		return "", response, None
	return text, response, None


def _text_with_retry(node: str, role: str, messages: List[BaseMessage], options: _Options) -> str:
	"""空応答ならノード単位でやり直し、それでも空なら空文字を返す。"""
	for attempt in range(EMPTY_RETRIES + 1):
		started = datetime.now()
		text, raw, error = _invoke_text(role, messages, options, MAX_TOKENS[node])
		_trace_step(node, started, attempt=attempt, ai_text=text or None, usage=_usage(raw), error=error)
		if text:
			return text
		logger.warning("[WARNING] v2 %s returned empty text (attempt %d)", node, attempt + 1)
	return ""


# ---------------------------------------------------------------------------
# ノード
# ---------------------------------------------------------------------------

def _make_nodes(options: _Options):
	def understand(state: V2State) -> dict:
		"""① 発言から読書プロフィールを更新し、意図を判定する。軽量モデル → 会話用モデルの順に試す。"""
		previous = normalize_profile(state.get("profile"))
		last_picks = state.get("last_picks") or []
		prompt = load_v2_prompt("understand")
		content = (
			f"## これまでのプロフィール\n{profile_text(previous)}\n\n"
			f"## 直前に紹介した本\n{_picks_text(last_picks) if last_picks else '（なし）'}\n\n"
			f"## 直近の会話\n{_transcript(state.get('messages') or [])}\n\n"
			f"## 今回の発言\n{state['message']}"
		)
		user_context = user_context_text(state.get("user_context", ""))
		if user_context:
			content = f"{user_context}\n\n{content}"
		messages = [SystemMessage(content=prompt), HumanMessage(content=content)]

		for attempt, role in enumerate(("light", "chat")):
			started = datetime.now()
			parsed, raw, error = _invoke_structured(role, UnderstandOutput, messages, options, MAX_TOKENS["understand"])
			result_json = parsed.model_dump_json() if parsed else None
			_trace_step("understand", started, attempt=attempt, usage=_usage(raw), error=error,
			            results=[{"name": f"understand ({role})", "content": result_json or "(読み取れず)"}])
			if parsed is not None:
				intent = parsed.intent
				if intent in ("ask_book", "refine") and not last_picks:
					intent = "ready" if intent == "refine" else "need_more"
				return {"profile": normalize_profile(parsed.profile).model_dump(), "intent": intent,
				        "path": [*state.get("path", []), "understand"]}

		# どちらでも読み取れなければ、プロフィールは前のまま、聞き取りに回す
		return {"profile": previous.model_dump(), "intent": "need_more", "path": [*state.get("path", []), "understand"]}

	def route(state: V2State) -> dict:
		"""② 振り分け（コード）。"""
		started = datetime.now()
		profile = normalize_profile(state.get("profile"))
		decision = decide_route(state.get("intent", "need_more"), profile, state.get("last_picks") or [])
		_trace_step("route", started, results=[{"name": "route", "content": f"intent={state.get('intent')} -> {decision}"}])
		return {"route": decision, "path": [*state.get("path", []), "route"]}

	def interview(state: V2State) -> dict:
		"""③ 次に聞くことを発話で返す。"""
		profile = normalize_profile(state.get("profile"))
		prompt = load_v2_prompt("interview", profile=profile_text(profile),
		                        user_context=user_context_text(state.get("user_context", "")))
		text = _text_with_retry("interview", "chat", _chat_messages(prompt, state.get("messages") or [], state["message"]), options)
		return {"response_text": text or llm_module.MESSAGE_EMPTY_RESPONSE, "picks": [],
		        "path": [*state.get("path", []), "interview"]}

	def crd_node(state: V2State) -> dict:
		"""④a レファ協の事例から手がかりを取り出す（ready / refine / lookup_title のとき）。失敗しても先へ進む。

		ready / refine は興味（なければ気分）で質問文を検索する。lookup_title は会話に出た本の言葉で
		事例全体（anywhere）を検索する（書名は回答や回答プロセスに書かれていることが多いため）。
		"""
		started = datetime.now()
		hints: List[dict] = []
		intent = state.get("intent")
		if intent in CRD_INTENTS:
			profile = normalize_profile(state.get("profile"))
			if intent == "lookup_title":
				words, field = profile.mentioned_books[:2], "anywhere"
			else:
				words, field = (profile.interests[:2] or ([profile.mood] if profile.mood else [])), "question"
			if words:
				hints = crd.search_crd_hints(words, field=field)[:CRD_HINT_LIMIT]
		_trace_step("crd", started, results=[{"name": "crd", "content": json.dumps(hints, ensure_ascii=False)}])
		return {"crd_hints": hints, "path": [*state.get("path", []), "crd"]}

	def plan(state: V2State) -> dict:
		"""④b 検索キーワードを2〜4組作る。読み取れなければプロフィールから作る。"""
		profile = normalize_profile(state.get("profile"))
		prompt = load_v2_prompt("plan", profile=profile_text(profile), intent=state.get("intent", "ready"),
		                        crd_hints=_crd_hints_text(state.get("crd_hints") or []))
		content = f"## 直近の会話\n{_transcript(state.get('messages') or [])}\n\n## 今回の発言\n{state['message']}"
		started = datetime.now()
		parsed, raw, error = _invoke_structured("light", PlanOutput, [SystemMessage(content=prompt), HumanMessage(content=content)],
		                                        options, MAX_TOKENS["plan"])
		queries = clean_queries([q.keywords for q in parsed.queries]) if parsed else []
		source = "llm"
		if not queries:
			queries = fallback_queries(profile, state.get("crd_hints") or [])
			source = "fallback"
		_trace_step("plan", started, usage=_usage(raw), error=error,
		            results=[{"name": f"plan ({source})", "content": json.dumps(queries, ensure_ascii=False)}])
		return {"queries": queries, "path": [*state.get("path", []), "plan"]}

	def search(state: V2State) -> dict:
		"""⑤ 楽天を検索して重複を除く（コード）。"""
		started = datetime.now()
		exclude = {_book_key(b) for b in state.get("last_picks") or []} if state.get("intent") == "refine" else set()
		candidates = collect_candidates(state.get("queries") or [], exclude)
		summary = "\n".join(f"{c['candidate_id']}. {_book_label(c)} [{c['source']}]" for c in candidates)
		_trace_step("search", started, results=[{"name": "search", "content": summary or "(0件)"}])
		return {"candidates": candidates, "path": [*state.get("path", []), "search"]}

	def select(state: V2State) -> dict:
		"""⑥ 候補から最大3冊を枠付きで選び、紹介の言葉を返す。候補にない ID は捨てる。"""
		path = [*state.get("path", []), "select"]
		candidates = state.get("candidates") or []
		if not candidates:
			return {"picks": [], "response_text": MESSAGE_NO_CANDIDATES, "path": path}

		profile = normalize_profile(state.get("profile"))
		prompt = load_v2_prompt("select", profile=profile_text(profile),
		                        user_context=user_context_text(state.get("user_context", "")))
		candidate_text = "\n".join(llm_module.format_book_candidate(c["candidate_id"], c) for c in candidates)
		content = (
			f"## 直近の会話\n{_transcript(state.get('messages') or [])}\n\n"
			f"## 今回の発言\n{state['message']}\n\n"
			f"## 候補の本\n{candidate_text}"
		)
		messages = [SystemMessage(content=prompt), HumanMessage(content=content)]

		parsed = None
		for attempt in range(SELECT_RETRIES + 1):
			started = datetime.now()
			parsed, raw, error = _invoke_structured("chat", SelectOutput, messages, options, MAX_TOKENS["select"])
			_trace_step("select", started, attempt=attempt, usage=_usage(raw), error=error,
			            ai_text=(parsed.response if parsed else None),
			            results=[{"name": "select", "content": parsed.model_dump_json() if parsed else "(読み取れず)"}])
			if parsed is not None:
				break
		if parsed is None:
			return {"picks": [], "response_text": llm_module.MESSAGE_EMPTY_RESPONSE, "path": path}

		picks = validate_picks(parsed.picks, candidates)
		response_text = llm_module.extract_user_visible_text(parsed.response)
		if llm_module.contains_internal_response(response_text):
			response_text = ""
		if not picks:
			# 選んだ ID がすべて候補になかった、または合う本がなかった
			if parsed.picks or not response_text:
				response_text = MESSAGE_NO_PICKS
		elif not response_text:
			response_text = default_pick_message(picks)
		return {"picks": picks, "response_text": response_text, "path": path}

	def answer(state: V2State) -> dict:
		"""推薦した本への質問に、last_picks の内容紹介をもとに答える。"""
		prompt = load_v2_prompt("answer", picks=_picks_text(state.get("last_picks") or []),
		                        user_context=user_context_text(state.get("user_context", "")))
		text = _text_with_retry("answer", "chat", _chat_messages(prompt, state.get("messages") or [], state["message"]), options)
		return {"response_text": text or llm_module.MESSAGE_EMPTY_RESPONSE, "picks": [],
		        "path": [*state.get("path", []), "answer"]}

	return {"understand": understand, "route": route, "interview": interview, "crd": crd_node,
	        "plan": plan, "search": search, "select": select, "answer": answer}


def clean_queries(raw_queries: List[List[str]]) -> List[List[str]]:
	"""キーワードの組を整える: 空語を除き、1組2語まで、重複を除き、最大4組。"""
	queries: List[List[str]] = []
	for keywords in raw_queries:
		words = _clean_list(keywords, limit=MAX_WORDS_PER_QUERY)
		if words and words not in queries:
			queries.append(words)
	return queries[:MAX_QUERIES]


def fallback_queries(profile: ReadingProfile, crd_hints: List[dict]) -> List[List[str]]:
	"""plan が使えないときに、プロフィールとレファ協の手がかりから組を作る。"""
	raw: List[List[str]] = []
	if profile.interests:
		raw.append(profile.interests[:2])
		raw.extend([interest] for interest in profile.interests[:3])
	raw.extend([title] for title in profile.mentioned_books[:2])
	for hint in crd_hints:
		if hint.get("keywords"):
			raw.append(hint["keywords"][:2])
	if not raw and profile.mood:
		raw.append([profile.mood])
	return clean_queries(raw)


def collect_candidates(queries: List[List[str]], exclude_keys: Optional[set] = None) -> List[dict]:
	"""各組で楽天を検索し、重複を除いた候補を返す。内容紹介のない本は後ろに回す。

	まず全組を AND 検索し、0件だった組だけを OR 検索でやり直す。ただし、ほかの組で候補が
	ENOUGH_CANDIDATES 件以上集まっていれば、やり直しを省く（楽天の呼び出しは1秒以上空けるため、
	呼び出しが減るほど応答が速くなる）。検索で例外になった組はやり直さない。
	"""
	exclude_keys = exclude_keys or set()
	seen = set(exclude_keys)
	collected: List[dict] = []

	def search(keywords: List[str], orflag: int) -> Optional[list]:
		try:
			return llm_module.rakuten_search_books(keywords, count=SEARCH_COUNT_PER_QUERY, orflag=orflag) or []
		except Exception as exc:
			logger.warning("[WARNING] v2 rakuten search failed for %s (orflag=%d): %s", keywords, orflag, exc)
			return None

	def add(keywords: List[str], books: list) -> None:
		for book in books:
			key = _book_key(book)
			if key in seen:
				continue
			seen.add(key)
			collected.append({**book, "source": "rakuten:" + " ".join(keywords)})

	empty_queries = []
	for keywords in queries:
		books = search(keywords, 0)
		if books is None:
			continue
		if books:
			add(keywords, books)
		else:
			empty_queries.append(keywords)
	for keywords in empty_queries:
		if len(collected) >= ENOUGH_CANDIDATES:
			logger.info("[INFO] v2 skipped OR search for %s (%d candidates already)", keywords, len(collected))
			continue
		add(keywords, search(keywords, 1) or [])

	# 内容紹介のある本を先に（同じ中では検索順を保つ）
	collected.sort(key=lambda b: 0 if _caption_length(b) >= CAPTION_MIN_CHARS else 1)
	collected = collected[:CANDIDATE_LIMIT]
	for i, book in enumerate(collected, 1):
		book["candidate_id"] = i
	return collected


def validate_picks(picks: List[Pick], candidates: List[dict]) -> List[dict]:
	"""選んだ ID が候補にあるか検証し、ないものと重複を捨てる。最大3冊。枠は不正なら空いている枠を当てる。"""
	by_id = {c["candidate_id"]: c for c in candidates}
	result: List[dict] = []
	used_ids = set()
	used_slots: List[str] = []
	for pick in picks:
		if pick.id not in by_id or pick.id in used_ids:
			logger.warning("[WARNING] v2 select returned an unknown or duplicate id: %s", pick.id)
			continue
		slot = pick.slot.strip() if isinstance(pick.slot, str) else ""
		if slot not in SLOTS or slot in used_slots:
			slot = next((s for s in SLOTS if s not in used_slots), SLOTS[-1])
		used_ids.add(pick.id)
		used_slots.append(slot)
		book = _public_book(by_id[pick.id])
		book["recommendation_reason"] = (pick.reason or "").strip()
		book["recommendation_slot"] = slot
		result.append(book)
		if len(result) >= MAX_PICKS:
			break
	return result


def default_pick_message(picks: List[dict]) -> str:
	"""選書できたのに紹介の言葉が空だったときの文。"""
	labels = {"ど真ん中": "ぴったりの1冊", "少し外す": "少し視点を変えた1冊", "意外な1冊": "意外な1冊"}
	parts = [labels.get(p.get("recommendation_slot"), "おすすめの1冊") for p in picks]
	if len(parts) == 1:
		joined = parts[0]
	else:
		joined = "、".join(parts[:-1]) + "、それから" + parts[-1]
	return f"{joined}を選んでみました。気になる本はありますか。"


def select_expression_v2(response_text: str, state: dict) -> str:
	"""表情を、通ったノードと結果で決める。"""
	if response_text in llm_module.FALLBACK_MESSAGES:
		return "sorry"
	path = state.get("path") or []
	if "select" in path:
		return "happy" if state.get("picks") else "sorry"
	return "neutral"


# ---------------------------------------------------------------------------
# グラフ
# ---------------------------------------------------------------------------

def _after_route(state: V2State) -> str:
	return {"search": "crd", "answer": "answer"}.get(state.get("route"), "interview")


def create_graph_v2(options: Optional[_Options] = None):
	nodes = _make_nodes(options or _Options(None, 0.3))
	workflow = StateGraph(V2State)
	for name, fn in nodes.items():
		workflow.add_node(name, fn)
	workflow.set_entry_point("understand")
	workflow.add_edge("understand", "route")
	workflow.add_conditional_edges("route", _after_route, {"interview": "interview", "crd": "crd", "answer": "answer"})
	workflow.add_edge("crd", "plan")
	workflow.add_edge("plan", "search")
	workflow.add_edge("search", "select")
	workflow.add_edge("interview", END)
	workflow.add_edge("answer", END)
	workflow.add_edge("select", END)
	return workflow.compile()


_graph_v2_mermaid_cache: Optional[str] = None


def get_graph_v2_mermaid() -> str:
	"""v2 のグラフ構造を mermaid の文字列で返す（LLM は呼ばない）。"""
	global _graph_v2_mermaid_cache
	if _graph_v2_mermaid_cache is None:
		_graph_v2_mermaid_cache = create_graph_v2().get_graph().draw_mermaid()
	return _graph_v2_mermaid_cache


def llm_chat_v2(
	message: str,
	history: Optional[List[BaseMessage]] = None,
	ai_insight: Optional[str] = None,
	model: Optional[str] = None,
	temperature: float = 0.3,
	conversation_state: Optional[dict] = None,
) -> tuple[str, List[BaseMessage], List[dict], str]:
	"""v2 の1ターン。戻り値は v1 の llm_chat と同じ (応答テキスト, 履歴, 推薦書籍, 表情)。

	conversation_state ({"profile", "last_picks"}) は、応答が定型文でなかったときだけ書き換える。
	"""
	history = list(history or [])
	state_store = conversation_state if conversation_state is not None else {}
	initial: V2State = {
		"message": message,
		"messages": history,
		"user_context": ai_insight or "",
		"profile": normalize_profile(state_store.get("profile")).model_dump(),
		"last_picks": list(state_store.get("last_picks") or []),
		"path": [],
	}
	try:
		app = create_graph_v2(_Options(model, temperature))
		result = app.invoke(initial)
	except Exception as exc:
		llm_module._record_trace_error(exc)
		if is_rate_limit_error(exc):
			logger.warning("[WARNING] Gemini rate limit (429) in llm_chat_v2")
			return llm_module.MESSAGE_BUSY, history, [], "sorry"
		logger.exception("Error in llm_chat_v2")
		return llm_module.MESSAGE_EXCEPTION, history, [], "sorry"

	_record_turn_summary(result)
	response_text = result.get("response_text") or llm_module.MESSAGE_EMPTY_RESPONSE
	picks = list(result.get("picks") or [])
	expression = select_expression_v2(response_text, {**result, "picks": picks})

	if response_text in llm_module.FALLBACK_MESSAGES:
		# 失敗時の定型文は履歴にもプロフィールにも反映しない（v1 と同じ）
		return response_text, history, [], expression

	state_store["profile"] = result.get("profile") or {}
	if picks:
		state_store["last_picks"] = picks
	updated_history = history + [HumanMessage(content=message), AIMessage(content=response_text)]
	return response_text, updated_history, picks, expression
