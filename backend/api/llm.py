# Standard Library
import html
import os
import re
import traceback
from datetime import datetime

from typing import Optional, List, Dict, Any, TypedDict, Annotated, Sequence
import logging

# LangChain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# User-defined
from backend import PROMPTS_DIR, LLM_MAX_RETRIES, LLM_HISTORY_LIMIT
from backend.search.rakuten_books import rakuten_search_books, genre_path
from backend.api import llm_usage
from backend.api.llm_usage import is_rate_limit_error
from backend.api.trace_store import current_turn, TraceStep

# Logger
logger = logging.getLogger("uvicorn.error")


# Gemini の内部応答をユーザー向けテキストとして扱わないための定義。
# 正式なツール呼び出しは AIMessage.tool_calls で処理し、ここには現れない。
_INTERNAL_RESPONSE_PATTERN = re.compile(
	r"(?:^|\n)(?:tool_code|thought)\s*(?:\n|$)|default_api\.|"
	r"(?:search_books|recommend_books|update_expression)\s*\(",
	re.IGNORECASE,
)


def extract_user_visible_text(content: Any) -> str:
	"""Gemini/LangChain の応答からユーザー向けテキストだけを取り出す。"""
	if isinstance(content, str):
		return content.strip()

	if not isinstance(content, list):
		return str(content).strip()

	text_parts = []
	for part in content:
		if isinstance(part, str):
			text_parts.append(part)
			continue
		if not isinstance(part, dict):
			continue

		# 思考・ツール・コード実行の部品は表示しない。
		part_type = str(part.get("type", "")).lower()
		if part.get("thought") or part_type in {
			"thinking", "reasoning", "tool_call", "tool_use", "executable_code"
		}:
			continue
		if isinstance(part.get("text"), str):
			text_parts.append(part["text"])

	return "".join(text_parts).strip()


def contains_internal_response(text: str) -> bool:
	"""モデル内部のツール／思考形式がテキストに混入したか判定する。"""
	return bool(_INTERNAL_RESPONSE_PATTERN.search(text))


# 利用者向けの失敗メッセージ（読み上げられるため、内部情報は含めない）。
# 詳細はサーバーログに出力する。
MESSAGE_INTERNAL_FORMAT = "申し訳ございません。応答の生成中にエラーが発生しました。もう一度お試しください。"
MESSAGE_EMPTY_RESPONSE = "申し訳ございません。うまくお答えできませんでした。もう一度お話しいただけますか。"
MESSAGE_EXCEPTION = "申し訳ございません。ただいま応答できません。少し時間をおいてお試しください。"
MESSAGE_BUSY = "ただいま混雑しています。少し時間をおいてお試しください。"
FALLBACK_MESSAGES = (MESSAGE_INTERNAL_FORMAT, MESSAGE_EMPTY_RESPONSE, MESSAGE_EXCEPTION, MESSAGE_BUSY)


def select_expression(
	response_text: str,
	messages: Sequence[BaseMessage],
	recommended_books: Sequence[dict],
) -> str:
	"""処理結果から暫定的な表情を決定する。"""
	# TODO: 最終回答を軽量モデルで分類し、会話内容に応じた表情を選択する。
	# Candidate: gemini-2.5-flash-lite
	if response_text in FALLBACK_MESSAGES:
		return "sorry"

	search_messages = [
		message
		for message in messages
		if isinstance(message, ToolMessage) and message.name == "search_books"
	]
	if any(
		"見つかりませんでした" in str(message.content)
		or "エラーが発生しました" in str(message.content)
		for message in search_messages
	):
		return "sorry"

	if recommended_books:
		return "happy"
	if search_messages:
		return "thinking"
	return "neutral"

# LangChainのデバッグログを有効化（環境変数で制御）
if os.getenv("LANGCHAIN_DEBUG", "false").lower() == "true":
	import langchain
	langchain.debug = True
	logger.info("[DEBUG] LangChain debug mode enabled")


# State Definition

class AgentState(TypedDict):
	"""エージェントの状態"""
	messages: Annotated[Sequence[BaseMessage], add_messages]
	search_results: Dict[int, dict]  # 検索結果（番号 → 書籍データ）
	recommended_books: List[dict]  # 推薦された書籍


# LLM Initialization

LLM_ROLES = ("chat", "summary", "light")

DEFAULT_GEMINI_MODELS = {
	"chat": "gemini-3.5-flash-lite",
	"summary": "gemini-4-hydrogen",
	"light": "gemini-3.5-flash-lite",
}
MODEL_ENV = {"chat": "GEMINI_CHAT_MODEL", "summary": "GEMINI_SUMMARY_MODEL", "light": "GEMINI_LIGHT_MODEL"}

# サンプリングの値が固定されているモデル（langchain-google-genai の一覧と同じ）。
# temperature を渡すと「uses fixed sampling defaults」の UserWarning が出て、値は無視される。
FIXED_SAMPLING_MODELS = frozenset({
	"gemini-3.5-flash-lite",
	"gemini-3.6-flash",
	"gemini-4-carbon",
	"gemini-4-hydrogen",
	"gemini-4-neon",
})


# 思考の段階（Gemini 3 以降の thinking_level）。None はモデルの既定のまま（引数を渡さない）。
# - summary（gemini-4-hydrogen）: low。このモデルは minimal に対応していない
# - chat / light（gemini-3.5-flash-lite）: 指定しない。このモデルの既定は minimal
THINKING_LEVELS = ("minimal", "low", "medium", "high", "xhigh")
DEFAULT_THINKING_LEVELS = {"chat": None, "summary": "low", "light": None}
THINKING_ENV = {"chat": "GEMINI_CHAT_THINKING", "summary": "GEMINI_SUMMARY_THINKING", "light": "GEMINI_LIGHT_THINKING"}
_GEMINI_MAJOR_VERSION = re.compile(r"gemini-(\d+)")


def get_thinking_level(role: str) -> Optional[str]:
	"""役割に対応する thinking_level を返す。環境変数があればそれを優先する。

	環境変数に "default" を指定すると、役割の既定値も使わずモデルの既定に任せる（None）。
	不正な値は警告を出して役割の既定値を使う。
	"""
	if role not in LLM_ROLES:
		raise ValueError(f"Unknown LLM role: {role}")
	raw = (os.getenv(THINKING_ENV[role]) or "").strip().lower()
	if not raw:
		return DEFAULT_THINKING_LEVELS[role]
	if raw == "default":
		return None
	if raw not in THINKING_LEVELS:
		logger.warning("[WARNING] Unknown %s=%r, using %r", THINKING_ENV[role], raw, DEFAULT_THINKING_LEVELS[role])
		return DEFAULT_THINKING_LEVELS[role]
	return raw


def is_gemini_3_or_later(model_name: str) -> bool:
	"""thinking_level を使える Gemini 3 以降のモデルか（2.5 系は thinking_budget を使う）。"""
	match = _GEMINI_MAJOR_VERSION.search(model_name.lower())
	return bool(match) and int(match.group(1)) >= 3


def uses_fixed_sampling(model_name: str) -> bool:
	"""temperature を渡してはいけないモデルか。"models/..." の接頭辞と "-001" のような版の接尾辞は無視する。"""
	name = model_name.lower().rsplit("/", 1)[-1]
	name = re.sub(r"-\d{3}$", "", name)
	return name in FIXED_SAMPLING_MODELS


def get_gemini_model(role: str) -> str:
	"""役割に対応する Gemini のモデル名を返す。環境変数があればそれを優先する。"""
	if role not in LLM_ROLES:
		raise ValueError(f"Unknown LLM role: {role}")
	return os.getenv(MODEL_ENV[role]) or DEFAULT_GEMINI_MODELS[role]


def get_llm(role: str = "chat", backend: Optional[str] = None, temperature: float = 0.3, max_tokens: int = 1024, system_prompt: Optional[str] = None):
	"""
	LLMインスタンスを取得
	
	Args:
		role: 用途（'chat' / 'summary' / 'light'）。Gemini のモデル選択に使う
		backend: LLMバックエンド（'gemini' または 'ollama'）
		temperature: 温度パラメータ
		max_tokens: 最大トークン数
		system_prompt: システムプロンプト（オプション）
		
	Returns:
		LangChain LLMインスタンス
	"""
	if backend is None:
		backend = os.getenv("LLM_BACKEND", "gemini")
	
	if backend == "gemini":
		model_name = get_gemini_model(role)
		kwargs = {
			"model": model_name,
			"max_tokens": max_tokens,
			"google_api_key": os.getenv("GEMINI_API_KEY"),
			# SDK 内のリトライが多いと、429 のとき端末が長く固まる
			"max_retries": int(os.getenv("GEMINI_API_MAX_RETRIES", "1")),
			"timeout": float(os.getenv("GEMINI_API_TIMEOUT", "30")),
		}
		if not uses_fixed_sampling(model_name):
			kwargs["temperature"] = temperature
		thinking_level = get_thinking_level(role)
		if thinking_level and is_gemini_3_or_later(model_name):
			kwargs["thinking_level"] = thinking_level
		if model_name.startswith("gemini-2.5-"):
			# 2.5 系の動的思考が出力枠を使い切り、最終テキストが
			# 空になることを防ぐ。Gemini 3 以降は thinking_budget ではなく上の thinking_level を使う。
			kwargs["thinking_budget"] = 0
		return ChatGoogleGenerativeAI(**kwargs)
	else:  # ollama
		return ChatOllama(
			model=os.getenv("OLLAMA_MODEL", "llama3.2"),
			base_url=os.getenv("OLLAMA_API_URL", "http://localhost:11434"),
			temperature=temperature,
			num_predict=max_tokens
		)


# Prompt Management

def load_prompt_text(filepath: str) -> str:
	"""プロンプトファイルを読み込む"""
	with open(filepath, 'r', encoding='utf-8') as f:
		return f.read()


def create_system_prompt(base_prompt: str, ai_insight: Optional[str] = None) -> str:
	"""
	システムプロンプトを作成
	
	Args:
		base_prompt: ベースとなるプロンプト
		ai_insight: ユーザー情報（オプション）
		
	Returns:
		完成したシステムプロンプト
	"""
	# 書籍推薦の指示を追加
	recommendation_instruction = """

## 書籍推薦の手順

1. ユーザーの要望を理解し、適切なキーワードで `search_books` を実行（**20冊以上**検索すること）
2. 検索結果から、ユーザーに最適な本を3冊程度選択
3. `recommend_books` ツールを使って、選んだ本の番号と推薦理由を送信
4. 推薦理由を**簡潔に**説明（1冊あたり1文程度）。詳細は画面に表示されるので不要です。

**重要**: 書籍情報（タイトル、著者など）は検索結果の番号で参照してください。
書籍の詳細情報を自分で作成したり、変更したりしないでください。
"""
	
	full_prompt = base_prompt + recommendation_instruction
	
	if ai_insight and ai_insight.strip():
		full_prompt += f"""

## ユーザー情報
以下は、これまでの会話から学習したユーザーの傾向です。

{ai_insight}
"""
	
	return full_prompt

# 検索結果の候補リスト

CAPTION_MAX_CHARS = 150  # 候補リストに載せる内容紹介の最大文字数
_HTML_TAG_RE = re.compile(r"<[^>]*>")


def clean_caption(caption: Optional[str], limit: int = CAPTION_MAX_CHARS) -> str:
	"""楽天の itemCaption から HTML タグを除き、空白をまとめて limit 文字に切り詰める。"""
	if not caption:
		return ""
	text = html.unescape(_HTML_TAG_RE.sub(" ", str(caption)))
	text = re.sub(r"\s+", " ", text).strip()
	if len(text) > limit:
		text = text[:limit].rstrip() + "…"
	return text


def format_review(average: Any, count: Any) -> str:
	"""レビュー平均と件数を「4.3（12件）」の形にする。レビューがなければ「なし」。"""
	try:
		count_num = int(count or 0)
		average_num = float(average or 0)
	except (TypeError, ValueError):
		return "なし"
	if count_num <= 0:
		return "なし"
	return f"{average_num:.1f}（{count_num}件）"


def format_book_candidate(number: int, book: dict) -> str:
	"""search_books が LLM に返す候補1件分の文字列を作る。"""
	title = book.get("title") or "不明"
	authors = book.get("authors") or []
	author = authors[0] if authors else "不明"
	lines = [f"{number}. 『{title}』 - {author}"]
	genre = genre_path(book.get("genre"))
	if genre:
		lines.append(f"   ジャンル: {genre}")
	lines.append(f"   レビュー: {format_review(book.get('reviewAverage'), book.get('reviewCount'))}")
	caption = clean_caption(book.get("itemCaption"))
	if caption:
		lines.append(f"   内容: {caption}")
	return "\n".join(lines)


# LangGraph Workflow

def create_agent_workflow(llm, tools):
	"""エージェントワークフローを作成"""
	
	# ツールをLLMにバインド
	llm_with_tools = llm.bind_tools(tools)
	
	def agent_node(state: AgentState):
		"""エージェントノード: LLMで応答を生成"""
		messages = state["messages"]
		logger.info(f"[DEBUG] agent_node: Received {len(messages)} messages")
		if not messages:
			logger.error("[ERROR] agent_node: Empty messages list!")
			raise ValueError("Messages list is empty in agent_node")

		try:
			response = llm_with_tools.invoke(messages)
		except Exception as exc:
			llm_usage.record_error("chat", exc)
			raise
		llm_usage.record_success("chat", response)
		return {"messages": [response]}

	def force_tool_node(state: AgentState):
		"""強制的にツール呼び出しを促すノード"""
		logger.info("[DEBUG] force_tool_node: Enforcing recommend_books call")
		message = HumanMessage(content="検索結果から本を選んで、必ず `recommend_books` を呼び出してください。もし推薦する本がない場合は、空のリスト `[]` を引数にしてください。")
		return {"messages": [message]}
	
	def should_continue(state: AgentState):
		"""次のノードを決定"""
		messages = state["messages"]
		last_message = messages[-1]
		
		# ツール呼び出しがある場合
		if hasattr(last_message, "tool_calls") and last_message.tool_calls:
			return "tools"
			
		# 直前が検索結果(ToolMessage)で、今回ツール呼び出しをしなかった場合
		if len(messages) >= 2:
			second_last = messages[-2]
			# ToolMessageかつ、search_booksの結果である場合（nameはToolNodeが設定する）
			if isinstance(second_last, ToolMessage) and second_last.name == "search_books":
				# 検索結果が0件（エラーメッセージ）の場合は、強制しない
				if "申し訳ございません" in str(second_last.content):
					return "end"
				return "force_tool"
				
		return "end"
	
	# グラフ構築
	workflow = StateGraph(AgentState)
	
	# ノード追加
	workflow.add_node("agent", agent_node)
	workflow.add_node("tools", ToolNode(tools))
	workflow.add_node("force_tool", force_tool_node)
	
	# エントリーポイント設定
	workflow.set_entry_point("agent")
	
	# エッジ追加
	workflow.add_conditional_edges(
		"agent",
		should_continue,
		{
			"tools": "tools",
			"force_tool": "force_tool",
			"end": END
		}
	)
	workflow.add_edge("tools", "agent")
	workflow.add_edge("force_tool", "agent")
	
	return workflow.compile()


# Trace

TRACE_CONTENT_LIMIT = 2000


def _record_trace_step(node_name, new_messages, attempt, started, ended) -> None:
	"""ノード1回分の処理をトレースに記録する。失敗しても会話は止めない。"""
	try:
		turn = current_turn.get()
		if turn is None:
			return
		step = TraceStep(
			index=len(turn.steps),
			node=node_name,
			attempt=attempt,
			started_at=started.isoformat(),
			ended_at=ended.isoformat(),
			duration_ms=int((ended - started).total_seconds() * 1000),
		)
		for msg in new_messages:
			if isinstance(msg, AIMessage):
				text = extract_user_visible_text(msg.content)
				step.ai_text = text if step.ai_text is None else step.ai_text + text
				step.tool_calls.extend(
					{"name": call.get("name"), "args": call.get("args")}
					for call in (msg.tool_calls or [])
				)
				usage = getattr(msg, "usage_metadata", None)
				if usage:
					step.usage = dict(usage)
			elif isinstance(msg, ToolMessage):
				step.tool_results.append({
					"name": msg.name,
					"content": str(msg.content)[:TRACE_CONTENT_LIMIT],
				})
		turn.steps.append(step)
	except Exception:
		logger.exception("Failed to record trace step")


def _record_trace_error(exc: BaseException) -> None:
	"""llm_chat 全体で捕まえた例外をトレースに記録する。"""
	try:
		turn = current_turn.get()
		if turn is None:
			return
		turn.error = {
			"type": type(exc).__name__,
			"message": str(exc),
			"traceback": traceback.format_exc(),
		}
	except Exception:
		logger.exception("Failed to record trace error")


_graph_mermaid_cache: Optional[str] = None


def get_graph_mermaid() -> str:
	"""create_agent_workflow の構造を mermaid の文字列で返す(LLM は呼ばない)。"""
	global _graph_mermaid_cache
	if _graph_mermaid_cache is None:
		class _DummyLLM:
			def bind_tools(self, tools):
				return self

			def invoke(self, messages):
				raise RuntimeError("dummy LLM is never invoked")

		@tool
		def search_books(keywords: list[str], count: int = 30) -> str:
			"""ダミー"""
			return ""

		@tool
		def recommend_books(selections: list[dict]) -> str:
			"""ダミー"""
			return ""

		graph = create_agent_workflow(_DummyLLM(), [search_books, recommend_books])
		_graph_mermaid_cache = graph.get_graph().draw_mermaid()
	return _graph_mermaid_cache


# Chat Functions

GRAPH_VERSIONS = ("v1", "v2")


def get_graph_version() -> str:
	"""LIVRARIA_GRAPH の値（"v1" / "v2"）。未設定や不正な値なら v1。"""
	value = (os.getenv("LIVRARIA_GRAPH") or "v1").strip().lower()
	if value not in GRAPH_VERSIONS:
		logger.warning("[WARNING] Unknown LIVRARIA_GRAPH=%r, using v1", value)
		return "v1"
	return value


def llm_chat(
	prompt_file: str,
	message: str,
	history: Optional[List[BaseMessage]] = None,
	ai_insight: Optional[str] = None,
	model: Optional[str] = None,
	temperature: float = 0.3,
	max_tokens: int = 1024,
	conversation_state: Optional[dict] = None,
) -> tuple[str, List[BaseMessage], List[dict]]:
	"""
	LangGraphを使ったチャット対話
	
	Args:
		prompt_file: プロンプトファイルのパス
		message: ユーザーメッセージ
		history: 会話履歴 (List[BaseMessage])
		ai_insight: ユーザー情報
		model: 使用するLLMバックエンド
		temperature: 温度パラメータ
		max_tokens: 最大トークン数
		conversation_state: 会話グラフ v2 が読み書きする状態 {"profile", "last_picks"}（v1 では使わない）
		
	Returns:
		(応答テキスト, 更新された履歴(List[BaseMessage]), 推薦された書籍リスト)
	"""
	if get_graph_version() == "v2":
		# v2 は graph_v2.py にまとめている。プロンプトは prompts/v2/ を使い、prompt_file は使わない
		from backend.api.graph_v2 import llm_chat_v2
		return llm_chat_v2(message, history, ai_insight=ai_insight, model=model,
		                   temperature=temperature, conversation_state=conversation_state)

    # ローカルステート初期化 (スレッドセーフかつ複数回検索に対応)
	search_results_state = {}     # 全検索結果の累積 (ID -> BookDict)
	recommended_books_state = []  # 推薦された本のリスト
	
    # ツール定義 (クロージャとして実装することでローカルステートにアクセス)
	
	@tool
	def search_books(keywords: list[str], count: int = 30) -> str:
		"""
		楽天Books APIを使って書籍を検索
		
		検索結果は番号付きリストで返されます。
		推薦する本を選ぶ際は、この番号を使用してください。
		
		Args:
			keywords: 検索キーワードのリスト（例: ["SF", "初心者", "おすすめ"]）
			count: 取得する書籍数（デフォルト: 10, 10冊以上を指定すること）
			
		Returns:
			番号付き書籍リスト
		"""
		try:
			logger.info(f"[DEBUG] search_books called with keywords: {keywords}, count: {count}")
			
			if not keywords or not isinstance(keywords, list):
				logger.error(f"[ERROR] Invalid keywords: {keywords}")
				return "検索キーワードが指定されていません。"
			
			# API呼び出し
			books = rakuten_search_books(keywords, count=max(count, 10), orflag=0)
			
			if not books:
				books = rakuten_search_books(keywords, count=max(count * 2, 20), orflag=1)
				if not books:
					logger.error("No books found for keywords: %s", keywords)
					return "申し訳ございません。該当する書籍が見つかりませんでした。"
				
			# 累積されているIDの続きから番号を振る
			start_id = max(search_results_state.keys()) + 1 if search_results_state else 1
			
			book_list = []
			for i, book in enumerate(books):
				current_id = start_id + i
				# ローカルステートに保存
				search_results_state[current_id] = book
				
				book_list.append(format_book_candidate(current_id, book))
			
			logger.info(f"[DEBUG] Found {len(books)} books. IDs assigned: {start_id} to {start_id + len(books) - 1}")
			return f"検索結果（{len(books)}冊）:\n" + "\n".join(book_list) + "\n\nこれらの結果から、ユーザーに合った本を選び、必ず `recommend_books` を呼び出してください。テキストで検索結果を要約しないでください。もし推薦する本がない場合は、空のリスト `[]` を引数にして `recommend_books` を呼び出してください。"
			
		except Exception as e:
			logger.error(f"[ERROR] search_books error: {e}", exc_info=True)
			return f"検索中にエラーが発生しました: {str(e)}"

	@tool
	def recommend_books(selections: list[dict]) -> str:
		"""
		検索結果から推薦する本を選択
		
		Args:
			selections: 推薦する本のリスト
				各要素は {"number": 番号, "reason": "推薦理由"} の形式
				例: [{"number": 1, "reason": "初心者向けで分かりやすい"}, {"number": 3, "reason": "実践的な内容"}]
			
		Returns:
			推薦完了メッセージ
		"""
		try:
			recommended_temp = []
			
			for selection in selections:
				num = selection.get("number")
				reason = selection.get("reason", "")
				
				# ローカルステートから検索
				if num in search_results_state:
					book = search_results_state[num].copy()
					book["recommendation_reason"] = reason
					recommended_temp.append(book)
			
			# 結果リストに追加（上書きせず追加、ただし今回はリクエストごとなので代入でOKに見えるが、念のためextend）
			# ※仕様として「今回の回答に含まれる推薦本」を返すなら代入でよい。
			# 過去の会話の推薦本は含めないのが通例。
			recommended_books_state.clear()
			recommended_books_state.extend(recommended_temp)
			
			if recommended_temp:
				msg_lines = [f"{len(recommended_temp)}冊の本を推薦リストに追加しました。以下の番号と情報を使って、ユーザーに推薦してください。"]
				for i, book in enumerate(recommended_temp, 1):
					msg_lines.append(f"{i}. 『{book['title']}』 (理由: {book['recommendation_reason']})")
				return "\n".join(msg_lines)
			else:
				return "推薦する本が選択されませんでした。ユーザーに「条件に合う本が見つかりませんでした」と報告してください。"
				
		except Exception as e:
			return f"推薦処理中にエラーが発生しました: {str(e)}"

	
	# プロンプト読み込み
	base_prompt = load_prompt_text(prompt_file)
	system_prompt = create_system_prompt(base_prompt, ai_insight)
	
	# LLM初期化
	llm = get_llm(role="chat", backend=model, temperature=temperature, max_tokens=max_tokens)
	
	# ツール定義
	tools = [search_books, recommend_books]
	
	# ワークフロー作成
	app = create_agent_workflow(llm, tools)
	
	# メッセージ履歴を準備
	if history is None:
		history = []
	
	# メッセージリストを構築
	if not history:
		# Gemini への既存の入力形式を維持する。
		first_message = f"{system_prompt}\n\n---\n\nユーザー: {message}"
		current_message = HumanMessage(content=first_message)
		messages = [current_message]
		logger.info(f"[DEBUG] No history, created first message with system prompt")
	else:
		# 履歴がある場合: システムプロンプトは最初の会話で既に送信済みなので、通常のメッセージのみ
		current_message = HumanMessage(content=message)
		messages = history + [current_message]
		logger.info(f"[DEBUG] With history, messages count: {len(messages)}")
		
		# 履歴が長すぎる場合は最新のメッセージのみを保持（Gemini 2.5 Flashの空レスポンス対策）
		if len(messages) > LLM_HISTORY_LIMIT:
			# 最初のメッセージ（システムプロンプト含む）と最新のN件を保持
			first_message = messages[0]
			recent_messages = messages[-(LLM_HISTORY_LIMIT - 1):]
			messages = [first_message] + recent_messages
			logger.info(f"[INFO] History truncated to {len(messages)} messages (limit: {LLM_HISTORY_LIMIT})")
	
	logger.info(f"[DEBUG] Final messages for LangGraph: {len(messages)} messages")
	
	# ワークフロー実行（リトライロジック付き）
	retry_count = 0
	response_text = ""
	
	try:
		while retry_count < LLM_MAX_RETRIES:
			# 初期ステートに search_results は空で渡すが、
			# 実際のデータ管理はツール内のクロージャ変数が担うため、
			# StateGraph上の search_results は実質ダミーまたはログ用となる
			# stream_mode="updates" の各 update は {ノード名: {"messages": [...]}}。
			# add_messages は新しいメッセージを末尾に足すだけなので、順に足せば invoke の結果と同じ並びになる。
			result_messages = list(messages)
			step_started = datetime.now()
			for update in app.stream({
				"messages": messages,
				"search_results": {},
				"recommended_books": []
			}, stream_mode="updates"):
				step_ended = datetime.now()
				for node_name, node_output in update.items():
					new_messages = (node_output or {}).get("messages") or []
					if not isinstance(new_messages, (list, tuple)):
						new_messages = [new_messages]
					result_messages.extend(new_messages)
					_record_trace_step(node_name, new_messages, retry_count, step_started, step_ended)
				step_started = step_ended
			result = {"messages": result_messages}
			
			# デバッグ: 結果の詳細をログ出力
			logger.info(f"[DEBUG] LangGraph result keys: {list(result.keys())}")
			logger.info(f"[DEBUG] Messages count in result: {len(result.get('messages', []))}")
			if result.get('messages'):
				for idx, msg in enumerate(result['messages']):
					msg_type = type(msg).__name__
					msg_content = getattr(msg, 'content', 'N/A')
					logger.info(f"[DEBUG] Message {idx}: type={msg_type}, content_type={type(msg_content).__name__}, content={msg_content[:100] if isinstance(msg_content, str) else msg_content}")
			
			# 最後のAIメッセージを取得
			ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
			if ai_messages:
				last_message = ai_messages[-1]
				response_text = extract_user_visible_text(last_message.content)

				if contains_internal_response(response_text):
					logger.error("[ERROR] Model returned internal tool or thought text")
					response_text = MESSAGE_INTERNAL_FORMAT
					break
				
				# 空の応答でなければ成功
				if response_text.strip():
					if retry_count > 0:
						logger.info(f"[INFO] Retry succeeded after {retry_count} attempts")
					break
				else:
					logger.error(
						"[ERROR] Empty final AI message: content=%r, tool_calls=%r, response_metadata=%r",
						last_message.content,
						getattr(last_message, "tool_calls", None),
						getattr(last_message, "response_metadata", None),
					)
					retry_count += 1
					if retry_count < LLM_MAX_RETRIES:
						logger.warning(f"[WARNING] Empty response from LLM (attempt {retry_count}/{LLM_MAX_RETRIES}), retrying...")
					else:
						logger.error(f"[ERROR] Empty response from LLM after {LLM_MAX_RETRIES} attempts")
						response_text = MESSAGE_EMPTY_RESPONSE
			else:
				retry_count += 1
				if retry_count < LLM_MAX_RETRIES:
					logger.warning(f"[WARNING] No AI message found (attempt {retry_count}/{LLM_MAX_RETRIES}), retrying...")
				else:
					response_text = MESSAGE_EMPTY_RESPONSE
					logger.error("No AI message found in result after retries: %s", result)
		
		# 正式なツール呼び出しはこのターン内で完結させ、表示用テキストだけを履歴に保存する。
		# 失敗時の定型文は履歴に残さない（以降の会話の文脈を汚さないため）。
		if response_text in FALLBACK_MESSAGES:
			updated_history = list(history)
		else:
			updated_history = history + [current_message, AIMessage(content=response_text)]
		
		# 推薦された書籍を取得 (クロージャ変数から)
		recommended_books = list(recommended_books_state)
		current_expression = select_expression(
			response_text,
			result["messages"],
			recommended_books,
		)
		logger.info(f"[DEBUG] Selected expression from processing result: {current_expression}")
		
		return response_text, updated_history, recommended_books, current_expression
		
	except Exception as exc:
		_record_trace_error(exc)
		if is_rate_limit_error(exc):
			# 上限超過は想定内の事象なので traceback は出さない。
			logger.warning("[WARNING] Gemini rate limit (429) in llm_chat")
			return MESSAGE_BUSY, list(history), [], "sorry"
		# 例外の詳細（APIキーやURLを含みうる）はサーバーログのみに出力する。
		logger.exception("Error in llm_chat")
		return MESSAGE_EXCEPTION, list(history), [], "sorry"


def llm_summary(
	prompt_file: str,
	message: str,
	ai_insight: Optional[str] = None,
	model: Optional[str] = None,
	temperature: float = 0.3,
	max_tokens: int = 2048,
	role: str = "summary"
) -> Optional[str]:
	"""
	ツールを使わない単発の生成（要約・AI Insights・キーワード抽出用）。
	書籍推薦用の指示は付けない。

	Returns:
		生成テキスト。失敗時や空応答時は None（呼び出し側で既存データを保持すること）。
	"""
	system_prompt = load_prompt_text(prompt_file)
	if ai_insight and ai_insight.strip():
		system_prompt += f"\n\n## ユーザー情報\n以下は、これまでの会話から学習したユーザーの傾向です。\n\n{ai_insight}\n"

	llm = get_llm(role=role, backend=model, temperature=temperature, max_tokens=max_tokens)
	messages = [
		SystemMessage(content=system_prompt),
		HumanMessage(content=message)
	]

	try:
		response = llm.invoke(messages)
	except Exception as exc:
		llm_usage.record_error(role, exc)
		if is_rate_limit_error(exc):
			logger.warning("[WARNING] Gemini rate limit (429) in llm_summary")
		else:
			logger.exception("Error in llm_summary")
		return None
	llm_usage.record_success(role, response)

	text = extract_user_visible_text(response.content)
	if not text or contains_internal_response(text):
		logger.warning("[WARNING] llm_summary returned empty or internal text")
		return None
	return text


# Main (for testing)

if __name__ == "__main__":
	from backend import PROMPT_DEFAULT

	response, history, recommended_books, expression = llm_chat(
		prompt_file=str(PROMPT_DEFAULT),
		message="Pythonの機械学習に関する本を教えてください",
		history=[]
	)
	print(f"Response:\n{response}\nExpression: {expression}")
	for book in recommended_books:
		print(f"  - {book.get('title')} ({book.get('recommendation_reason')})")
