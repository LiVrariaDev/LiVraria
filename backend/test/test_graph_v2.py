"""会話グラフ v2（backend/api/graph_v2.py）の検証。LLM・楽天・レファ協はすべて差し替え、実際には呼ばない。"""

import threading

import pytest
import requests
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.config import get_config

import backend.api.graph_v2 as graph_v2
import backend.api.llm as llm
import backend.api.server as server_module
import backend.search.crd as crd
from backend import PROMPT_DEFAULT
from backend.api import llm_usage, trace_store
from backend.api.datastore import DataStore
from backend.api.models import Personal
from conftest import clear_data_dir


# ---------------------------------------------------------------------------
# 偽の LLM
# ---------------------------------------------------------------------------

class _RateLimitError(Exception):
	code = 429


DEFAULT_DRAFT = "（使われない下書き）"


def _current_node():
	try:
		return get_config().get("metadata", {}).get("langgraph_node")
	except RuntimeError:
		return None


class FakeLLMs:
	"""get_llm の差し替え。schema 名（または "text" / "draft"）ごとに、返す値を順に並べておく。

	値には pydantic のインスタンス、dict、None（読み取れない）、例外、文字列（text / draft 用）を使える。
	文章の呼び出しのうち、聞き取りの下書き（interview_draft ノード）は "draft"、それ以外は "text"。
	下書きは毎ターン並列に呼ばれるので、"draft" を並べていなければ DEFAULT_DRAFT を返す。
	呼び出しは calls に (role, kind, messages) で記録する。
	"""

	def __init__(self, **scripts):
		self.scripts = {key: list(values) for key, values in scripts.items()}
		self.calls = []
		self._lock = threading.Lock()

	def _next(self, kind):
		with self._lock:
			values = self.scripts.get(kind)
			if kind == "draft" and "draft" not in self.scripts:
				return DEFAULT_DRAFT
			if not values:
				raise AssertionError(f"unexpected LLM call: {kind}")
			value = values.pop(0)
		if isinstance(value, BaseException):
			raise value
		return value

	def get_llm(self, role="chat", **kwargs):
		fakes = self

		class _Structured:
			def __init__(self, schema):
				self.schema = schema

			def invoke(self, messages):
				with fakes._lock:
					fakes.calls.append((role, self.schema.__name__, messages))
				parsed = fakes._next(self.schema.__name__)
				return {"raw": AIMessage(content=""), "parsed": parsed, "parsing_error": None}

		class _LLM:
			def with_structured_output(self, schema, include_raw=False):
				return _Structured(schema)

			def invoke(self, messages):
				kind = "draft" if _current_node() == "interview_draft" else "text"
				with fakes._lock:
					fakes.calls.append((role, kind, messages))
				return AIMessage(content=fakes._next(kind))

			def bind_tools(self, tools):
				raise AssertionError("v1 should not run")

		return _LLM()

	def kinds(self, include_draft=False):
		"""呼び出しの (role, kind)。下書きは並列なので順序が決まらず、既定では除く。"""
		return [(role, kind) for role, kind, _ in self.calls if include_draft or kind != "draft"]

	def main_calls(self):
		"""下書きを除いた呼び出し（順序が決まる）。"""
		return [call for call in self.calls if call[1] != "draft"]

	def messages_of(self, kind):
		return [messages for _role, k, messages in self.calls if k == kind]


def understood(intent, queries=(), **profile):
	return graph_v2.UnderstandOutput(profile=graph_v2.ReadingProfile(**profile), intent=intent,
	                                 queries=[graph_v2.SearchQuery(keywords=list(q)) for q in queries])


def plan_of(*queries):
	return graph_v2.PlanOutput(queries=[graph_v2.SearchQuery(keywords=list(q)) for q in queries])


def select_of(picks, response="ぴったりの1冊と、少し視点を変えた1冊です。"):
	return graph_v2.SelectOutput(picks=[graph_v2.Pick(**p) for p in picks], response=response)


def book(n, caption="とても面白い本です。" * 5, **extra):
	return {
		"title": f"本{n}",
		"authors": [f"著者{n}"],
		"isbn": f"978000000000{n}",
		"genre": "001001001",
		"itemCaption": caption,
		"reviewAverage": "4.0",
		"reviewCount": 3,
		"image_url": f"https://example.com/{n}.jpg",
		**extra,
	}


@pytest.fixture(autouse=True)
def v2_env(monkeypatch):
	monkeypatch.setenv("LIVRARIA_GRAPH", "v2")
	llm_usage.reset()
	crd.clear_cache()
	# 既定ではレファ協は0件にしておく（個別のテストで差し替える）
	monkeypatch.setattr(graph_v2.crd, "search_crd_hints", lambda words, limit=5, field="question": [])
	yield
	crd.clear_cache()


@pytest.fixture
def rakuten(monkeypatch):
	"""楽天検索の差し替え。keywords（空白区切り）→ 本のリスト。呼び出しを記録する。"""
	results = {}
	calls = []

	def fake(keywords, count=10, orflag=0, **kwargs):
		calls.append((tuple(keywords), orflag))
		return list(results.get(" ".join(keywords), []))

	monkeypatch.setattr(llm, "rakuten_search_books", fake)
	fake.results = results
	fake.calls = calls
	return fake


def run(fakes, monkeypatch, message, history=None, state=None, user_context=""):
	monkeypatch.setattr(llm, "get_llm", fakes.get_llm)
	return llm.llm_chat(str(PROMPT_DEFAULT), message, history or [], ai_insight=user_context, conversation_state=state)


# server._build_user_context と同じ形（シナリオ17）
USER_CONTEXT = (
	"## ユーザー情報\nニックネーム: はなさん（会話の中で親しみを込めて呼びかけてください）\n性別: female\n年齢: 20歳"
	"\n\n## AI Insights（過去の会話から学習）\nミステリーとSFが好き。長編より短編を好む。"
)


# ---------------------------------------------------------------------------
# 1. 振り分け（意図ごと）
# ---------------------------------------------------------------------------

FULL = graph_v2.ReadingProfile(interests=["猫"])
EMPTY = graph_v2.ReadingProfile()
PICKED = [{"title": "本1"}]


@pytest.mark.parametrize("intent, profile, last_picks, expected", [
	("chit_chat", FULL, [], "interview"),
	("need_more", FULL, [], "interview"),
	("ready", FULL, [], "search"),
	("ready", EMPTY, [], "interview"),                      # 手がかりがなければ聞き取りに戻る
	("ready", graph_v2.ReadingProfile(mood="疲れている"), [], "search"),
	("ready", graph_v2.ReadingProfile(formats=["絵本"]), [], "search"),         # 形式だけでも探せる
	("refine", FULL, PICKED, "search"),
	("lookup_title", graph_v2.ReadingProfile(mentioned_books=["青い鳥の話"]), [], "crd"),  # レファ協 → plan を通る
	("ready", graph_v2.ReadingProfile(interests=["戦国"], purpose="調べ物"), [], "crd"),
	("refine", graph_v2.ReadingProfile(interests=["戦国"], purpose="調べ物"), PICKED, "crd"),
	("ready", graph_v2.ReadingProfile(interests=["戦国"], purpose="学び"), [], "search"),
	("lookup_title", graph_v2.ReadingProfile(mood="懐かしい"), [], "interview"),
	("ask_book", FULL, PICKED, "answer"),
	("ask_book", FULL, [], "interview"),                    # 紹介した本がなければ答えられない
])
def test_decide_route(intent, profile, last_picks, expected):
	assert graph_v2.decide_route(intent, profile, last_picks) == expected


@pytest.mark.parametrize("intent", ["chit_chat", "need_more"])
def test_interview_turn(monkeypatch, rakuten, intent):
	fakes = FakeLLMs(UnderstandOutput=[understood(intent, interests=["猫"])], draft=["最近はどんなふうに過ごしていますか。"])
	state = {}

	text, history, books, expression = run(fakes, monkeypatch, "こんにちは", state=state)

	assert text == "最近はどんなふうに過ごしていますか。"
	assert books == [] and expression == "neutral"
	# 聞き取りのターンは、理解と下書きの2回だけ（下書きをそのまま返す）
	assert sorted(fakes.kinds(include_draft=True)) == [("chat", "draft"), ("light", "UnderstandOutput")]
	assert rakuten.calls == []
	assert history[-2:] == [HumanMessage("こんにちは"), AIMessage("最近はどんなふうに過ごしていますか。")]
	assert state["profile"]["interests"] == ["猫"]


def test_search_turn(monkeypatch, rakuten):
	rakuten.results["猫 小説"] = [book(1), book(2)]
	rakuten.results["猫"] = [book(2), book(3)]  # 本2は重複
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", [["猫", "小説"], ["猫"]], interests=["猫"], purpose="楽しみ")],
		SelectOutput=[select_of([
			{"id": 1, "slot": "ど真ん中", "reason": "猫好きにぴったり"},
			{"id": 3, "slot": "意外な1冊", "reason": "猫の視点で読める"},
		])],
	)
	state = {}

	text, history, books, expression = run(fakes, monkeypatch, "猫の小説を探して", state=state)

	# レファ協を引かないときは plan を通らず、understand のキーワードで検索する（LLM は2回）
	assert fakes.kinds() == [("light", "UnderstandOutput"), ("chat", "SelectOutput")]
	assert rakuten.calls == [(("猫", "小説"), 0), (("猫",), 0)]
	assert text == "ぴったりの1冊と、少し視点を変えた1冊です。"
	assert expression == "happy"
	assert [b["title"] for b in books] == ["本1", "本3"]
	# v1 と同じ楽天の項目に、理由と枠を足した形。内部用の項目は出さない
	assert books[0]["recommendation_reason"] == "猫好きにぴったり"
	assert books[0]["recommendation_slot"] == "ど真ん中"
	assert books[0]["image_url"] == "https://example.com/1.jpg"
	assert "candidate_id" not in books[0] and "source" not in books[0]
	assert state["last_picks"] == books
	# 下書きは並列に作られたが、検索するターンでは捨てる
	assert ("chat", "draft") in fakes.kinds(include_draft=True) and text != DEFAULT_DRAFT

	# 候補リストは重複を除き、内容紹介・ジャンル・レビューを載せている
	select_prompt = fakes.main_calls()[1][2][-1].content
	assert select_prompt.count("『本2』") == 1
	assert "レビュー: 4.0（3件）" in select_prompt and "内容: " in select_prompt


def test_search_puts_books_without_caption_last(monkeypatch, rakuten):
	rakuten.results["猫"] = [book(1, caption=""), book(2), book(3, caption="短い")]
	candidates = graph_v2.collect_candidates([["猫"]])
	assert [c["title"] for c in candidates] == ["本2", "本1", "本3"]
	assert [c["candidate_id"] for c in candidates] == [1, 2, 3]
	assert candidates[0]["source"] == "rakuten:猫"


def test_search_falls_back_to_or_search_and_skips_failures(monkeypatch):
	calls = []

	def fake(keywords, count=10, orflag=0, **kwargs):
		calls.append((tuple(keywords), orflag))
		if keywords == ["壊れる"]:
			raise requests.ConnectionError("down")
		return [book(1)] if orflag == 1 else []

	monkeypatch.setattr(llm, "rakuten_search_books", fake)
	candidates = graph_v2.collect_candidates([["壊れる"], ["猫", "宇宙"]])
	assert [c["title"] for c in candidates] == ["本1"]
	assert calls == [(("壊れる",), 0), (("猫", "宇宙"), 0), (("猫", "宇宙"), 1)]


def test_search_skips_or_retry_when_other_queries_found_enough(monkeypatch, rakuten):
	rakuten.results["猫"] = [book(i) for i in range(1, graph_v2.ENOUGH_CANDIDATES + 1)]
	# 「猫 宇宙」は AND で0件。ほかの組で十分集まったので OR ではやり直さない
	candidates = graph_v2.collect_candidates([["猫", "宇宙"], ["猫"]])
	assert len(candidates) == graph_v2.ENOUGH_CANDIDATES
	assert rakuten.calls == [(("猫", "宇宙"), 0), (("猫",), 0)]


def test_search_retries_with_or_when_not_enough(monkeypatch, rakuten):
	rakuten.results["猫"] = [book(1), book(2)]
	candidates = graph_v2.collect_candidates([["猫", "宇宙"], ["猫"]])
	# AND を全組やってから、0件だった組だけ OR でやり直す
	assert rakuten.calls == [(("猫", "宇宙"), 0), (("猫",), 0), (("猫", "宇宙"), 1)]
	assert len(candidates) == 2


def test_ask_book_answers_from_last_picks(monkeypatch, rakuten):
	last = [dict(book(7, caption="北欧の森で暮らす猫の一年を描いた物語。"), recommendation_reason="静かな話", recommendation_slot="ど真ん中")]
	fakes = FakeLLMs(UnderstandOutput=[understood("ask_book", interests=["猫"])], text=["北欧の森で暮らす猫のお話ですよ。"])
	state = {"profile": {"interests": ["猫"]}, "last_picks": last}

	text, _history, books, expression = run(fakes, monkeypatch, "1冊目はどんな話？", state=state)

	assert text == "北欧の森で暮らす猫のお話ですよ。"
	assert books == [] and expression == "neutral"
	assert rakuten.calls == []
	answer_system = fakes.main_calls()[1][2][0].content
	assert "『本7』" in answer_system and "北欧の森で暮らす猫の一年" in answer_system
	assert state["last_picks"] == last  # 答えただけでは選んだ本は変わらない


def test_refine_excludes_previous_picks(monkeypatch, rakuten):
	rakuten.results["猫"] = [book(1), book(2)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("refine", [["猫"]], interests=["猫"])],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "別の猫の本"}])],
	)
	state = {"profile": {"interests": ["猫"]}, "last_picks": [book(1)]}

	_text, _history, books, _expression = run(fakes, monkeypatch, "別のがいい", state=state)

	assert [b["title"] for b in books] == ["本2"]
	assert state["last_picks"][0]["title"] == "本2"


def test_lookup_title_uses_crd_anywhere_with_mentioned_books(monkeypatch, rakuten):
	hints = [{"question": "青い鳥が出てくる絵本", "keywords": ["青い鳥"], "ndc": ["726"], "process": "回答に書名あり"}]
	seen = []
	monkeypatch.setattr(graph_v2.crd, "search_crd_hints",
	                    lambda words, limit=5, field="question": seen.append((words, field)) or hints)
	rakuten.results["青い鳥"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("lookup_title", interests=["鳥"], mentioned_books=["青い鳥", "森の小人", "三冊目"])],
		PlanOutput=[plan_of(["青い鳥"])],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "書名が一致"}], response="この本でしょうか。")],
	)
	text, _history, books, _expression = run(fakes, monkeypatch, "青い鳥がどうとかいう本", state={})

	assert text == "この本でしょうか。" and books[0]["title"] == "本1"
	# 興味ではなく会話に出た本の言葉（先頭2つ）で、事例全体を検索する
	assert seen == [(["青い鳥", "森の小人"], "anywhere")]
	assert "回答に書名あり" in fakes.main_calls()[1][2][0].content  # 手がかりは検索方針に渡る


def test_lookup_title_without_mentioned_books_skips_crd(monkeypatch, rakuten):
	monkeypatch.setattr(graph_v2.crd, "search_crd_hints", lambda *a, **k: pytest.fail("crd should not be called"))
	rakuten.results["鳥"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("lookup_title", interests=["鳥"])],
		PlanOutput=[plan_of(["鳥"])],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "a"}])],
	)
	_text, _history, books, _expression = run(fakes, monkeypatch, "鳥の本の題名が思い出せない", state={})
	assert books[0]["title"] == "本1"


# ---------------------------------------------------------------------------
# 1b. 理解と聞き取りの下書きの並列実行
# ---------------------------------------------------------------------------

def test_understand_and_draft_run_in_parallel(monkeypatch, rakuten):
	"""どちらも相手が呼ばれるまで待つ。順番に動いていたら Barrier がタイムアウトする。"""
	barrier = threading.Barrier(2, timeout=5)
	threads = {}
	fakes = FakeLLMs(UnderstandOutput=[understood("need_more", interests=["猫"])], draft=["猫はお好きですか。"])
	original = fakes._next

	def waiting_next(kind):
		if kind in ("UnderstandOutput", "draft"):
			threads[kind] = threading.get_ident()
			barrier.wait()
		return original(kind)

	monkeypatch.setattr(fakes, "_next", waiting_next)
	text, _h, _b, _e = run(fakes, monkeypatch, "こんにちは", state={})

	assert text == "猫はお好きですか。"
	assert not barrier.broken
	assert threads["UnderstandOutput"] != threads["draft"]


def test_draft_uses_previous_profile_and_is_returned(monkeypatch, rakuten):
	fakes = FakeLLMs(UnderstandOutput=[understood("need_more", interests=["猫", "宇宙"])], draft=["猫のどんなところが好きですか。"])
	state = {"profile": {"interests": ["猫"]}}

	text, _h, books, expression = run(fakes, monkeypatch, "宇宙も好き", state=state)

	assert text == "猫のどんなところが好きですか。"
	assert books == [] and expression == "neutral"
	assert ("chat", "text") not in fakes.kinds()  # 聞き取りは下書きを使い、LLM を呼び直さない
	draft_system = fakes.messages_of("draft")[0][0].content
	assert '"猫"' in draft_system and "宇宙" not in draft_system  # 前のターンのプロフィールで作る
	assert state["profile"]["interests"] == ["猫", "宇宙"]  # プロフィールは understand の結果


def test_failed_draft_reinterviews_with_current_profile(monkeypatch, rakuten):
	fakes = FakeLLMs(UnderstandOutput=[understood("need_more", interests=["猫", "宇宙"])],
	                 draft=["", ""], text=["宇宙と猫、どちらの話が読みたいですか。"])
	text, _h, _b, _e = run(fakes, monkeypatch, "宇宙も好き", state={"profile": {"interests": ["猫"]}})

	assert text == "宇宙と猫、どちらの話が読みたいですか。"
	interview_system = fakes.messages_of("text")[0][0].content
	assert "宇宙" in interview_system  # 今のターンのプロフィールで呼び直す


def test_draft_rate_limit_does_not_stop_search_turn(monkeypatch, rakuten):
	rakuten.results["猫"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", [["猫"]], interests=["猫"])],
		draft=[_RateLimitError("429 Resource exhausted")],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "a"}], response="この本はいかがですか。")],
	)
	text, _h, books, _e = run(fakes, monkeypatch, "猫の本", state={})
	assert text == "この本はいかがですか。" and books[0]["title"] == "本1"
	assert llm_usage.snapshot()["roles"]["chat"]["rate_limited"] == 1


def test_draft_rate_limit_on_interview_turn_returns_busy(monkeypatch, rakuten):
	fakes = FakeLLMs(UnderstandOutput=[understood("chit_chat")],
	                 draft=[_RateLimitError("429")], text=[_RateLimitError("429")])
	text, _h, _b, expression = run(fakes, monkeypatch, "こんにちは", state={})
	assert text == llm.MESSAGE_BUSY and expression == "sorry"


def test_parallel_nodes_are_traced_and_counted(monkeypatch, rakuten):
	"""並列に動いた understand と下書きが、トレースと使用量の両方に残る（contextvar がスレッドに引き継がれる）。"""
	clear_data_dir()
	monkeypatch.setenv("LIVRARIA_DEBUG", "true")
	trace_store.reset_trace_store()
	store = DataStore()
	monkeypatch.setattr(server_module.server, "data_store", store)
	store.create_user("alice", Personal(name="alice", gender="other", age=20))
	fakes = FakeLLMs(UnderstandOutput=[understood("chit_chat")], draft=["こんにちは、今日はどんな一日でしたか。"])
	monkeypatch.setattr(llm, "get_llm", fakes.get_llm)
	try:
		response = server_module.server.chat_prompt("こんにちは", None, str(PROMPT_DEFAULT), "alice")
		turn = trace_store.get_trace_store().get_turn(response.trace_id)
	finally:
		trace_store.reset_trace_store()

	assert response.response == "こんにちは、今日はどんな一日でしたか。"
	nodes = [s["node"] for s in turn["steps"]]
	assert sorted(nodes[:2]) == ["interview_draft", "understand"]
	assert nodes[2:] == ["route", "interview"]
	assert sorted(turn["path"][:2]) == ["interview_draft", "understand"] and turn["path"][2:] == ["route", "interview"]
	draft_step = next(s for s in turn["steps"] if s["node"] == "interview_draft")
	assert draft_step["ai_text"] == "こんにちは、今日はどんな一日でしたか。"
	usage = llm_usage.snapshot()["roles"]
	assert usage["light"]["calls"] == 1 and usage["chat"]["calls"] == 1


# ---------------------------------------------------------------------------
# 1c. AI Insights とニックネーム
# ---------------------------------------------------------------------------

def test_nickname_and_insights_are_extracted():
	assert graph_v2.nickname_of(USER_CONTEXT) == "はな"
	assert graph_v2.insights_of(USER_CONTEXT) == "ミステリーとSFが好き。長編より短編を好む。"
	# 会員情報がなければ AI Insights の本文だけが渡る
	assert graph_v2.insights_of("ミステリーが好き") == "ミステリーが好き"
	assert graph_v2.nickname_of("ミステリーが好き") == ""
	only_user = "## ユーザー情報\nニックネーム: たろうさん（会話の中で親しみを込めて呼びかけてください）"
	assert graph_v2.insights_of(only_user) == "" and graph_v2.nickname_of(only_user) == "たろう"
	assert graph_v2.insights_of("") == "" and graph_v2.nickname_of(None) == ""


def test_persona_mentions_nickname_only_when_known():
	assert "「はな」さん" in graph_v2.persona_text("はな") and "毎回は呼ばない" in graph_v2.persona_text("はな")
	assert "ニックネーム" not in graph_v2.persona_text("")
	for name in ("interview", "select", "answer"):
		prompt = graph_v2.load_v2_prompt(name, nickname="はな", profile="{}", picks="", user_context="")
		assert "「はな」さん" in prompt


@pytest.mark.parametrize("intent, queries, has_insights, expected", [
	("ready", [["ミステリー"]], True, "search"),
	("ready", [["ミステリー"]], False, "interview"),  # AI Insights がなければ、空のプロフィールでは探さない
	("ready", [], True, "interview"),                  # キーワードを作れなかった
	("need_more", [["ミステリー"]], True, "interview"),
	("chit_chat", [["ミステリー"]], True, "interview"),
])
def test_decide_route_with_insights(intent, queries, has_insights, expected):
	assert graph_v2.decide_route(intent, EMPTY, [], queries=queries, has_insights=has_insights) == expected


def test_insights_drive_search_and_nickname_reaches_nodes(monkeypatch, rakuten):
	"""シナリオ17の2ターン目: 今の会話に手がかりがなくても、AI Insights から探す。"""
	rakuten.results["ミステリー 短編"] = [book(1)]
	rakuten.results["SF 短編"] = [book(2)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", [["ミステリー", "短編"], ["SF", "短編"]])],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "短編のミステリー"}], response="はなさん、短編はいかがですか。")],
	)
	state = {}
	text, _h, books, _e = run(fakes, monkeypatch, "今日は何かおすすめありますか？", state=state, user_context=USER_CONTEXT)

	assert text == "はなさん、短編はいかがですか。" and books[0]["title"] == "本1"
	assert ("light", "PlanOutput") not in fakes.kinds()
	assert "ミステリーとSFが好き" in fakes.main_calls()[0][2][-1].content  # understand に AI Insights が渡る
	assert "「はな」さん" in fakes.main_calls()[1][2][0].content         # 選書の人格にニックネーム
	assert "「はな」さん" in fakes.messages_of("draft")[0][0].content     # 下書きにも
	assert state["profile"]["interests"] == []  # AI Insights はプロフィールに入れない


def test_insights_are_passed_to_plan(monkeypatch, rakuten):
	rakuten.results["青い鳥"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("lookup_title", mentioned_books=["青い鳥"])],
		PlanOutput=[plan_of(["青い鳥"])],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "a"}])],
	)
	run(fakes, monkeypatch, "青い鳥の本", state={}, user_context=USER_CONTEXT)
	plan_system = fakes.main_calls()[1][2][0].content
	assert "ミステリーとSFが好き" in plan_system


def test_understand_prompt_keeps_insights_out_of_profile():
	prompt = graph_v2.load_v2_prompt("understand")
	assert "プロフィールには入れない" in prompt


# ---------------------------------------------------------------------------
# 2. 選書: 候補にない ID は捨てる
# ---------------------------------------------------------------------------

def test_select_drops_unknown_and_duplicate_ids(monkeypatch, rakuten):
	rakuten.results["猫"] = [book(1), book(2)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", [["猫"]], interests=["猫"])],
		SelectOutput=[select_of([
			{"id": 99, "slot": "ど真ん中", "reason": "存在しない"},
			{"id": 2, "slot": "ど真ん中", "reason": "あり"},
			{"id": 2, "slot": "少し外す", "reason": "重複"},
			{"id": 1, "slot": "謎の枠", "reason": "枠が不正"},
		])],
	)
	_text, _history, books, expression = run(fakes, monkeypatch, "猫の本", state={})

	assert [b["title"] for b in books] == ["本2", "本1"]
	assert [b["recommendation_slot"] for b in books] == ["ど真ん中", "少し外す"]
	assert expression == "happy"


def test_select_all_unknown_ids_returns_no_picks_message(monkeypatch, rakuten):
	rakuten.results["猫"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", [["猫"]], interests=["猫"])],
		SelectOutput=[select_of([{"id": 42, "slot": "ど真ん中", "reason": "幻の本"}], response="『幻の本』がおすすめです。")],
	)
	state = {}
	text, _history, books, expression = run(fakes, monkeypatch, "猫の本", state=state)

	assert text == graph_v2.MESSAGE_NO_PICKS  # 存在しない本を紹介する文は使わない
	assert books == [] and expression == "sorry"
	assert "last_picks" not in state


def test_validate_picks_limits_to_three():
	candidates = [dict(book(i), candidate_id=i) for i in range(1, 6)]
	picks = [graph_v2.Pick(id=i, slot="", reason="r") for i in range(1, 6)]
	result = graph_v2.validate_picks(picks, candidates)
	assert len(result) == 3
	assert [b["recommendation_slot"] for b in result] == list(graph_v2.SLOTS)


def test_select_empty_response_uses_template(monkeypatch, rakuten):
	rakuten.results["猫"] = [book(1), book(2)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", [["猫"]], interests=["猫"])],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "a"}, {"id": 2, "slot": "意外な1冊", "reason": "b"}], response="")],
	)
	text, _h, books, _e = run(fakes, monkeypatch, "猫の本", state={})
	assert text == "ぴったりの1冊、それから意外な1冊を選んでみました。気になる本はありますか。"
	assert len(books) == 2


def test_select_parse_failure_retries_then_falls_back(monkeypatch, rakuten):
	rakuten.results["猫"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", [["猫"]], interests=["猫"])],
		SelectOutput=[None, None],
	)
	history = [HumanMessage("前"), AIMessage("前の返事")]
	state = {}
	text, new_history, books, expression = run(fakes, monkeypatch, "猫の本", history=history, state=state)

	assert text == llm.MESSAGE_EMPTY_RESPONSE and expression == "sorry"
	assert books == [] and new_history == history  # 失敗の定型文は履歴に残さない
	assert state == {}  # プロフィールも更新しない
	assert [k for _r, k in fakes.kinds()].count("SelectOutput") == 2


def test_no_candidates_skips_select_llm(monkeypatch, rakuten):
	fakes = FakeLLMs(UnderstandOutput=[understood("ready", [["存在しない話題"]], interests=["存在しない話題"])])
	text, _h, books, expression = run(fakes, monkeypatch, "探して", state={})
	assert text == graph_v2.MESSAGE_NO_CANDIDATES
	assert books == [] and expression == "sorry"
	assert ("chat", "SelectOutput") not in fakes.kinds()


# ---------------------------------------------------------------------------
# 3. レファ協が0件・失敗・タイムアウトでも選書まで進む
# ---------------------------------------------------------------------------

def _crd_raises(error):
	def fake_get(*args, **kwargs):
		raise error
	return fake_get


@pytest.mark.parametrize("make_get", [
	lambda: (lambda *a, **k: type("R", (), {"text": "<result_set><hit_num>0</hit_num></result_set>", "raise_for_status": lambda self: None})()),
	lambda: _crd_raises(requests.ConnectionError("down")),
	lambda: _crd_raises(requests.Timeout("timeout")),
], ids=["zero", "failure", "timeout"])
def test_crd_problems_still_reach_select(monkeypatch, rakuten, make_get):
	monkeypatch.setattr(graph_v2.crd, "search_crd_hints", crd.search_crd_hints)  # 本物のクライアントで、HTTP だけ差し替え
	monkeypatch.setattr(crd.requests, "get", make_get())
	rakuten.results["猫"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", interests=["猫"], purpose="調べ物")],
		PlanOutput=[plan_of(["猫"])],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "a"}])],
	)
	_text, _h, books, expression = run(fakes, monkeypatch, "猫の本", state={})
	assert [b["title"] for b in books] == ["本1"] and expression == "happy"


def test_crd_hints_are_passed_to_plan_only(monkeypatch, rakuten):
	hints = [{"question": "猫の小説", "keywords": ["猫", "日本の小説"], "ndc": ["913"], "process": "件名で検索"}]
	seen = []
	monkeypatch.setattr(graph_v2.crd, "search_crd_hints", lambda words, limit=5, field="question": seen.append((words, field)) or hints)
	rakuten.results["猫"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", interests=["猫", "冬"], purpose="調べ物")],
		PlanOutput=[plan_of(["猫"])],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "a"}])],
	)
	text, _h, _b, _e = run(fakes, monkeypatch, "猫の本", state={})

	assert seen == [(["猫", "冬"], "question")]  # 調べ物は興味で質問文を検索する
	plan_system = fakes.main_calls()[1][2][0].content
	assert "日本の小説" in plan_system and "913" in plan_system and "件名で検索" in plan_system
	select_messages = "".join(m.content for m in fakes.main_calls()[2][2])
	assert "件名で検索" not in select_messages  # 事例は利用者向けの文を作るノードには渡さない


def test_plan_failure_uses_profile_keywords(monkeypatch, rakuten):
	rakuten.results["猫 宇宙"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", interests=["猫", "宇宙"], purpose="調べ物")],
		PlanOutput=[ValueError("broken")],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "a"}])],
	)
	_text, _h, books, _e = run(fakes, monkeypatch, "探して", state={})
	assert rakuten.calls[0] == (("猫", "宇宙"), 0)
	assert books[0]["title"] == "本1"


def test_ready_without_research_skips_crd_and_plan(monkeypatch, rakuten):
	monkeypatch.setattr(graph_v2.crd, "search_crd_hints", lambda *a, **k: pytest.fail("crd should not be called"))
	rakuten.results["戦国"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", [["戦国"]], interests=["戦国"], purpose="学び")],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "a"}])],
	)
	_text, _h, books, _e = run(fakes, monkeypatch, "戦国時代の本", state={})
	assert books[0]["title"] == "本1"
	assert ("light", "PlanOutput") not in fakes.kinds()


def test_understand_without_queries_uses_profile_keywords(monkeypatch, rakuten):
	rakuten.results["猫 宇宙"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", [], interests=["猫", "宇宙"])],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "a"}])],
	)
	_text, _h, books, _e = run(fakes, monkeypatch, "探して", state={})
	assert rakuten.calls[0] == (("猫", "宇宙"), 0)
	assert books[0]["title"] == "本1"
	assert ("light", "PlanOutput") not in fakes.kinds()


def test_understand_prompt_has_keyword_rules():
	prompt = graph_v2.load_v2_prompt("understand")
	assert "queries" in prompt and "避けたいもの（avoid）に当たる語は使わない" in prompt


def test_fallback_queries_use_formats():
	assert graph_v2.fallback_queries(graph_v2.ReadingProfile(formats=["絵本", "図鑑"]), []) == [["絵本"], ["図鑑"]]
	assert graph_v2.fallback_queries(graph_v2.ReadingProfile(interests=["猫", "宇宙"], formats=["絵本"]), []) == [
		["猫", "絵本"], ["猫", "宇宙"], ["猫"], ["宇宙"],
	]


def test_picture_book_only_searches_without_asking(monkeypatch, rakuten):
	"""「絵本ある？」だけで、聞き返さずに探す（シナリオ13）。キーワードが空でも形式から作る。"""
	rakuten.results["絵本"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", [], formats=["絵本"], reader="子ども")],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "寝る前に"}], response="寝る前にどうぞ。")],
	)
	state = {}
	text, _h, books, _e = run(fakes, monkeypatch, "絵本ある？", state=state)
	assert text == "寝る前にどうぞ。" and books[0]["title"] == "本1"
	assert rakuten.calls[0] == (("絵本",), 0)
	assert state["profile"]["formats"] == ["絵本"]


def test_understand_prompt_has_formats():
	prompt = graph_v2.load_v2_prompt("understand")
	assert "formats:" in prompt and "形式は interests ではなくここに書く" in prompt


def test_clean_queries():
	assert graph_v2.clean_queries([["猫", " ", "小説", "冬"], ["猫", "小説"], [], ["宇宙"], ["a"], ["b"], ["c"]]) == [
		["猫", "小説"], ["宇宙"], ["a"], ["b"],
	]


# ---------------------------------------------------------------------------
# 4. understand のやり直しと失敗、空応答、429
# ---------------------------------------------------------------------------

def test_understand_falls_back_to_chat_model(monkeypatch, rakuten):
	fakes = FakeLLMs(UnderstandOutput=[None, understood("chit_chat", mood="眠い")], draft=["眠いときは無理せずに。"])
	state = {}
	run(fakes, monkeypatch, "眠い", state=state)
	assert fakes.kinds()[:2] == [("light", "UnderstandOutput"), ("chat", "UnderstandOutput")]
	assert state["profile"]["mood"] == "眠い"


def test_understand_failure_keeps_profile_and_interviews(monkeypatch, rakuten):
	fakes = FakeLLMs(UnderstandOutput=[ValueError("x"), None], draft=["もう少し教えてください。"])
	state = {"profile": {"interests": ["猫"]}}
	text, _h, _b, _e = run(fakes, monkeypatch, "探して", state=state)
	assert text == "もう少し教えてください。"
	assert state["profile"]["interests"] == ["猫"]
	assert rakuten.calls == []


def test_ask_book_without_picks_becomes_need_more(monkeypatch, rakuten):
	fakes = FakeLLMs(UnderstandOutput=[understood("ask_book")], draft=["どの本のことでしょう。"])
	text, _h, _b, _e = run(fakes, monkeypatch, "その本は？", state={})
	assert text == "どの本のことでしょう。"


def test_empty_text_retries_then_fallback(monkeypatch, rakuten):
	# 下書きが2回とも空 → 聞き取りを今のプロフィールで呼び直し、それも2回とも空
	fakes = FakeLLMs(UnderstandOutput=[understood("chit_chat")], draft=["", "  "], text=["", ""])
	history = [HumanMessage("a"), AIMessage("b")]
	text, new_history, _b, expression = run(fakes, monkeypatch, "こんにちは", history=history, state={})
	assert text == llm.MESSAGE_EMPTY_RESPONSE and expression == "sorry"
	assert new_history == history
	kinds = [k for _r, k in fakes.kinds(include_draft=True)]
	assert kinds.count("draft") == 2 and kinds.count("text") == 2


def test_empty_text_retry_succeeds(monkeypatch, rakuten):
	fakes = FakeLLMs(UnderstandOutput=[understood("chit_chat")], draft=["", "こんにちは！"])
	text, _h, _b, _e = run(fakes, monkeypatch, "こんにちは", state={})
	assert text == "こんにちは！"


def test_internal_text_is_not_shown(monkeypatch, rakuten):
	fakes = FakeLLMs(UnderstandOutput=[understood("chit_chat")], draft=["search_books(keywords=['猫'])", "こんにちは！"])
	text, _h, _b, _e = run(fakes, monkeypatch, "こんにちは", state={})
	assert text == "こんにちは！"


def test_rate_limit_returns_busy(monkeypatch, rakuten):
	fakes = FakeLLMs(UnderstandOutput=[_RateLimitError("429 Resource exhausted")])
	history = [HumanMessage("a"), AIMessage("b")]
	text, new_history, books, expression = run(fakes, monkeypatch, "こんにちは", history=history, state={})
	assert text == llm.MESSAGE_BUSY and expression == "sorry"
	assert new_history == history and books == []
	assert llm_usage.snapshot()["roles"]["light"]["rate_limited"] == 1


def test_normalize_profile_handles_broken_data():
	profile = graph_v2.normalize_profile({"interests": ["猫", "猫", "", 3], "purpose": "宇宙旅行", "reader": None, "mood": None,
	                                      "formats": "絵本"})
	assert profile.interests == ["猫", "3"]
	assert profile.formats == ["絵本"]  # 文字列1つはリストにする
	assert profile.purpose == "不明" and profile.reader == "自分" and profile.mood == ""
	assert graph_v2.normalize_profile(None) == graph_v2.ReadingProfile()


# ---------------------------------------------------------------------------
# 5. プロフィールがターンをまたいで保存される
# ---------------------------------------------------------------------------

def test_profile_persists_across_turns_and_restart(monkeypatch, rakuten):
	clear_data_dir()
	store = DataStore()
	monkeypatch.setattr(server_module.server, "data_store", store)
	store.create_user("alice", Personal(name="alice", gender="other", age=20))
	rakuten.results["猫"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[
			understood("need_more", interests=["猫"]),
			understood("ready", [["猫"]], interests=["猫"], reader="子ども"),
		],
		draft=["猫が好きなんですね。", "（2ターン目の下書き）"],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "a"}])],
	)
	monkeypatch.setattr(llm, "get_llm", fakes.get_llm)

	first = server_module.server.chat_prompt("猫が好き", None, str(PROMPT_DEFAULT), "alice")
	session_id = first.session_id
	assert store.conversations[session_id].profile["interests"] == ["猫"]

	second = server_module.server.chat_prompt("子どもに読ませたい", session_id, str(PROMPT_DEFAULT), "alice")
	assert [b["title"] for b in second.recommended_books] == ["本1"]
	# 2ターン目の understand には、1ターン目のプロフィールが渡っている
	understand_input = fakes.main_calls()[1][2][-1].content
	assert '"猫"' in understand_input
	conv = store.conversations[session_id]
	assert conv.profile["reader"] == "子ども"
	assert conv.last_picks[0]["title"] == "本1"

	# 一時停止（サーバー終了）→ 再起動しても残る
	store.pause_session(session_id)
	reloaded = DataStore()
	assert reloaded.conversations[session_id].profile["reader"] == "子ども"
	assert reloaded.conversations[session_id].last_picks[0]["recommendation_reason"] == "a"


def test_old_conversation_without_profile_loads_as_empty():
	from backend.api.models import Conversation
	conv = Conversation(**{"_id": "s1", "user_id": "u1", "messages": []})
	assert conv.profile == {} and conv.last_picks == []


# ---------------------------------------------------------------------------
# 6. LIVRARIA_GRAPH 未設定なら v1
# ---------------------------------------------------------------------------

class _V1LLM:
	def __init__(self):
		self.bound = False

	def bind_tools(self, tools):
		self.bound = True
		return self

	def invoke(self, messages):
		return AIMessage(content="v1 の返事です")


@pytest.mark.parametrize("value", [None, "", "v1", "V1", "v3"])
def test_v1_runs_when_graph_is_not_v2(monkeypatch, value):
	if value is None:
		monkeypatch.delenv("LIVRARIA_GRAPH", raising=False)
	else:
		monkeypatch.setenv("LIVRARIA_GRAPH", value)
	fake = _V1LLM()
	monkeypatch.setattr(llm, "get_llm", lambda **kwargs: fake)
	monkeypatch.setattr(graph_v2, "llm_chat_v2", lambda *a, **k: pytest.fail("v2 should not run"))
	state = {"profile": {"interests": ["猫"]}, "last_picks": []}

	text, _h, _b, _e = llm.llm_chat(str(PROMPT_DEFAULT), "こんにちは", [], conversation_state=state)

	assert text == "v1 の返事です" and fake.bound
	assert llm.get_graph_version() == "v1"
	assert state == {"profile": {"interests": ["猫"]}, "last_picks": []}  # v1 は状態を変えない


def test_v2_selected_by_env(monkeypatch):
	monkeypatch.setenv("LIVRARIA_GRAPH", " V2 ")
	assert llm.get_graph_version() == "v2"


# ---------------------------------------------------------------------------
# 7. トレース（通過経路、プロフィール、crd_hints）
# ---------------------------------------------------------------------------

def test_trace_records_path_profile_and_crd_hints(monkeypatch, rakuten):
	clear_data_dir()
	monkeypatch.setenv("LIVRARIA_DEBUG", "true")
	trace_store.reset_trace_store()
	store = DataStore()
	monkeypatch.setattr(server_module.server, "data_store", store)
	store.create_user("alice", Personal(name="alice", gender="other", age=20))
	hints = [{"question": "猫の小説", "keywords": ["猫"], "ndc": ["913"], "process": "件名で検索"}]
	monkeypatch.setattr(graph_v2.crd, "search_crd_hints", lambda words, limit=5, field="question": hints)
	rakuten.results["猫"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", interests=["猫"], purpose="調べ物")],
		PlanOutput=[plan_of(["猫"])],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "a"}])],
	)
	monkeypatch.setattr(llm, "get_llm", fakes.get_llm)
	try:
		response = server_module.server.chat_prompt("猫の本", None, str(PROMPT_DEFAULT), "alice")
		turn = trace_store.get_trace_store().get_turn(response.trace_id)
	finally:
		trace_store.reset_trace_store()

	assert turn["graph"] == "v2"
	assert turn["intent"] == "ready" and turn["route"] == "crd"
	# understand と interview_draft は並列なので、先頭2つの順序は決まらない
	assert sorted(turn["path"][:2]) == ["interview_draft", "understand"]
	assert turn["path"][2:] == ["route", "crd", "plan", "search", "select"]
	assert sorted(s["node"] for s in turn["steps"]) == sorted(turn["path"])
	assert [s["index"] for s in turn["steps"]] == list(range(len(turn["steps"])))
	assert turn["profile"]["interests"] == ["猫"]
	assert turn["crd_hints"] == hints
	search_step = next(s for s in turn["steps"] if s["node"] == "search")
	assert "『本1』" in search_step["tool_results"][0]["content"]


def test_debug_graph_returns_both_versions(monkeypatch):
	from fastapi.testclient import TestClient
	from fastapi import FastAPI
	from backend.api.server import register_debug_routes

	monkeypatch.setenv("LIVRARIA_DEBUG", "true")
	monkeypatch.setenv("LIVRARIA_ADMIN_KEY", "k")
	app = FastAPI()
	register_debug_routes(app)
	data = TestClient(app).get("/debug/graph", headers={"X-Admin-Key": "k"}).json()
	assert data["version"] == "v2"
	assert data["mermaid"] == data["graphs"]["v2"]
	assert "understand" in data["graphs"]["v2"] and "select" in data["graphs"]["v2"]
	assert "agent" in data["graphs"]["v1"]



# ---------------------------------------------------------------------------
# 8. プロンプトの決まりごと
# ---------------------------------------------------------------------------

def test_understand_prompt_keeps_feelings_out_of_interests():
	prompt = graph_v2.load_v2_prompt("understand")
	assert "題材を表す名詞だけ" in prompt
	assert "「〜な本」" in prompt and "interests に入れない。mood に書く" in prompt


def test_select_prompt_has_no_fixed_phrase():
	prompt = graph_v2.load_v2_prompt("select", profile="{}", user_context="")
	assert "ぴったりの1冊と、少し視点を変えた1冊" not in prompt
	assert "枠の名前や決まった言い回しを使わず、3冊の違いが自然に伝わるように話す" in prompt
