"""会話グラフ v2（backend/api/graph_v2.py）の検証。LLM・楽天・レファ協はすべて差し替え、実際には呼ばない。"""

import pytest
import requests
from langchain_core.messages import AIMessage, HumanMessage

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


class FakeLLMs:
	"""get_llm の差し替え。schema 名（または "text"）ごとに、返す値を順に並べておく。

	値には pydantic のインスタンス、dict、None（読み取れない）、例外、文字列（text 用）を使える。
	呼び出しは calls に (role, kind, messages) で記録する。
	"""

	def __init__(self, **scripts):
		self.scripts = {key: list(values) for key, values in scripts.items()}
		self.calls = []

	def _next(self, kind):
		values = self.scripts.get(kind)
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
				fakes.calls.append((role, self.schema.__name__, messages))
				parsed = fakes._next(self.schema.__name__)
				return {"raw": AIMessage(content=""), "parsed": parsed, "parsing_error": None}

		class _LLM:
			def with_structured_output(self, schema, include_raw=False):
				return _Structured(schema)

			def invoke(self, messages):
				fakes.calls.append((role, "text", messages))
				return AIMessage(content=fakes._next("text"))

			def bind_tools(self, tools):
				raise AssertionError("v1 should not run")

		return _LLM()

	def kinds(self):
		return [(role, kind) for role, kind, _ in self.calls]


def understood(intent, **profile):
	return graph_v2.UnderstandOutput(profile=graph_v2.ReadingProfile(**profile), intent=intent)


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
	monkeypatch.setattr(graph_v2.crd, "search_crd_hints", lambda words, limit=5: [])
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


def run(fakes, monkeypatch, message, history=None, state=None):
	monkeypatch.setattr(llm, "get_llm", fakes.get_llm)
	return llm.llm_chat(str(PROMPT_DEFAULT), message, history or [], ai_insight="", conversation_state=state)


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
	("refine", FULL, PICKED, "search"),
	("lookup_title", graph_v2.ReadingProfile(mentioned_books=["青い鳥の話"]), [], "search"),
	("lookup_title", graph_v2.ReadingProfile(mood="懐かしい"), [], "interview"),
	("ask_book", FULL, PICKED, "answer"),
	("ask_book", FULL, [], "interview"),                    # 紹介した本がなければ答えられない
])
def test_decide_route(intent, profile, last_picks, expected):
	assert graph_v2.decide_route(intent, profile, last_picks) == expected


@pytest.mark.parametrize("intent", ["chit_chat", "need_more"])
def test_interview_turn(monkeypatch, rakuten, intent):
	fakes = FakeLLMs(UnderstandOutput=[understood(intent, interests=["猫"])], text=["最近はどんなふうに過ごしていますか。"])
	state = {}

	text, history, books, expression = run(fakes, monkeypatch, "こんにちは", state=state)

	assert text == "最近はどんなふうに過ごしていますか。"
	assert books == [] and expression == "neutral"
	assert fakes.kinds() == [("light", "UnderstandOutput"), ("chat", "text")]  # 聞き取りのターンは2回
	assert rakuten.calls == []
	assert history[-2:] == [HumanMessage("こんにちは"), AIMessage("最近はどんなふうに過ごしていますか。")]
	assert state["profile"]["interests"] == ["猫"]


def test_search_turn(monkeypatch, rakuten):
	rakuten.results["猫 小説"] = [book(1), book(2)]
	rakuten.results["猫"] = [book(2), book(3)]  # 本2は重複
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", interests=["猫"], purpose="楽しみ")],
		PlanOutput=[plan_of(["猫", "小説"], ["猫"])],
		SelectOutput=[select_of([
			{"id": 1, "slot": "ど真ん中", "reason": "猫好きにぴったり"},
			{"id": 3, "slot": "意外な1冊", "reason": "猫の視点で読める"},
		])],
	)
	state = {}

	text, history, books, expression = run(fakes, monkeypatch, "猫の小説を探して", state=state)

	assert fakes.kinds() == [("light", "UnderstandOutput"), ("light", "PlanOutput"), ("chat", "SelectOutput")]  # 3回
	assert text == "ぴったりの1冊と、少し視点を変えた1冊です。"
	assert expression == "happy"
	assert [b["title"] for b in books] == ["本1", "本3"]
	# v1 と同じ楽天の項目に、理由と枠を足した形。内部用の項目は出さない
	assert books[0]["recommendation_reason"] == "猫好きにぴったり"
	assert books[0]["recommendation_slot"] == "ど真ん中"
	assert books[0]["image_url"] == "https://example.com/1.jpg"
	assert "candidate_id" not in books[0] and "source" not in books[0]
	assert state["last_picks"] == books

	# 候補リストは重複を除き、内容紹介・ジャンル・レビューを載せている
	select_prompt = fakes.calls[2][2][-1].content
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


def test_ask_book_answers_from_last_picks(monkeypatch, rakuten):
	last = [dict(book(7, caption="北欧の森で暮らす猫の一年を描いた物語。"), recommendation_reason="静かな話", recommendation_slot="ど真ん中")]
	fakes = FakeLLMs(UnderstandOutput=[understood("ask_book", interests=["猫"])], text=["北欧の森で暮らす猫のお話ですよ。"])
	state = {"profile": {"interests": ["猫"]}, "last_picks": last}

	text, _history, books, expression = run(fakes, monkeypatch, "1冊目はどんな話？", state=state)

	assert text == "北欧の森で暮らす猫のお話ですよ。"
	assert books == [] and expression == "neutral"
	assert rakuten.calls == []
	answer_system = fakes.calls[1][2][0].content
	assert "『本7』" in answer_system and "北欧の森で暮らす猫の一年" in answer_system
	assert state["last_picks"] == last  # 答えただけでは選んだ本は変わらない


def test_refine_excludes_previous_picks(monkeypatch, rakuten):
	rakuten.results["猫"] = [book(1), book(2)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("refine", interests=["猫"])],
		PlanOutput=[plan_of(["猫"])],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "別の猫の本"}])],
	)
	state = {"profile": {"interests": ["猫"]}, "last_picks": [book(1)]}

	_text, _history, books, _expression = run(fakes, monkeypatch, "別のがいい", state=state)

	assert [b["title"] for b in books] == ["本2"]
	assert state["last_picks"][0]["title"] == "本2"


def test_lookup_title_skips_crd(monkeypatch, rakuten):
	monkeypatch.setattr(graph_v2.crd, "search_crd_hints", lambda *a, **k: pytest.fail("crd should not be called"))
	rakuten.results["青い鳥"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("lookup_title", mentioned_books=["青い鳥"])],
		PlanOutput=[plan_of(["青い鳥"])],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "書名が一致"}], response="この本でしょうか。")],
	)
	text, _history, books, _expression = run(fakes, monkeypatch, "青い鳥がどうとかいう本", state={})
	assert text == "この本でしょうか。" and books[0]["title"] == "本1"


# ---------------------------------------------------------------------------
# 2. 選書: 候補にない ID は捨てる
# ---------------------------------------------------------------------------

def test_select_drops_unknown_and_duplicate_ids(monkeypatch, rakuten):
	rakuten.results["猫"] = [book(1), book(2)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", interests=["猫"])],
		PlanOutput=[plan_of(["猫"])],
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
		UnderstandOutput=[understood("ready", interests=["猫"])],
		PlanOutput=[plan_of(["猫"])],
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
		UnderstandOutput=[understood("ready", interests=["猫"])],
		PlanOutput=[plan_of(["猫"])],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "a"}, {"id": 2, "slot": "意外な1冊", "reason": "b"}], response="")],
	)
	text, _h, books, _e = run(fakes, monkeypatch, "猫の本", state={})
	assert text == "ぴったりの1冊、それから意外な1冊を選んでみました。気になる本はありますか。"
	assert len(books) == 2


def test_select_parse_failure_retries_then_falls_back(monkeypatch, rakuten):
	rakuten.results["猫"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", interests=["猫"])],
		PlanOutput=[plan_of(["猫"])],
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
	fakes = FakeLLMs(UnderstandOutput=[understood("ready", interests=["存在しない話題"])], PlanOutput=[plan_of(["存在しない話題"])])
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
		UnderstandOutput=[understood("ready", interests=["猫"])],
		PlanOutput=[plan_of(["猫"])],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "a"}])],
	)
	_text, _h, books, expression = run(fakes, monkeypatch, "猫の本", state={})
	assert [b["title"] for b in books] == ["本1"] and expression == "happy"


def test_crd_hints_are_passed_to_plan_only(monkeypatch, rakuten):
	hints = [{"question": "猫の小説", "keywords": ["猫", "日本の小説"], "ndc": ["913"], "process": "件名で検索"}]
	seen = []
	monkeypatch.setattr(graph_v2.crd, "search_crd_hints", lambda words, limit=5: seen.append(words) or hints)
	rakuten.results["猫"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", interests=["猫", "冬"])],
		PlanOutput=[plan_of(["猫"])],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "a"}])],
	)
	text, _h, _b, _e = run(fakes, monkeypatch, "猫の本", state={})

	assert seen == [["猫", "冬"]]
	plan_system = fakes.calls[1][2][0].content
	assert "日本の小説" in plan_system and "913" in plan_system and "件名で検索" in plan_system
	select_messages = "".join(m.content for m in fakes.calls[2][2])
	assert "件名で検索" not in select_messages  # 事例は利用者向けの文を作るノードには渡さない


def test_plan_failure_uses_profile_keywords(monkeypatch, rakuten):
	rakuten.results["猫 宇宙"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", interests=["猫", "宇宙"])],
		PlanOutput=[ValueError("broken")],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "a"}])],
	)
	_text, _h, books, _e = run(fakes, monkeypatch, "探して", state={})
	assert rakuten.calls[0] == (("猫", "宇宙"), 0)
	assert books[0]["title"] == "本1"


def test_clean_queries():
	assert graph_v2.clean_queries([["猫", " ", "小説", "冬"], ["猫", "小説"], [], ["宇宙"], ["a"], ["b"], ["c"]]) == [
		["猫", "小説"], ["宇宙"], ["a"], ["b"],
	]


# ---------------------------------------------------------------------------
# 4. understand のやり直しと失敗、空応答、429
# ---------------------------------------------------------------------------

def test_understand_falls_back_to_chat_model(monkeypatch, rakuten):
	fakes = FakeLLMs(UnderstandOutput=[None, understood("chit_chat", mood="眠い")], text=["眠いときは無理せずに。"])
	state = {}
	run(fakes, monkeypatch, "眠い", state=state)
	assert fakes.kinds()[:2] == [("light", "UnderstandOutput"), ("chat", "UnderstandOutput")]
	assert state["profile"]["mood"] == "眠い"


def test_understand_failure_keeps_profile_and_interviews(monkeypatch, rakuten):
	fakes = FakeLLMs(UnderstandOutput=[ValueError("x"), None], text=["もう少し教えてください。"])
	state = {"profile": {"interests": ["猫"]}}
	text, _h, _b, _e = run(fakes, monkeypatch, "探して", state=state)
	assert text == "もう少し教えてください。"
	assert state["profile"]["interests"] == ["猫"]
	assert rakuten.calls == []


def test_ask_book_without_picks_becomes_need_more(monkeypatch, rakuten):
	fakes = FakeLLMs(UnderstandOutput=[understood("ask_book")], text=["どの本のことでしょう。"])
	text, _h, _b, _e = run(fakes, monkeypatch, "その本は？", state={})
	assert text == "どの本のことでしょう。"


def test_empty_text_retries_then_fallback(monkeypatch, rakuten):
	fakes = FakeLLMs(UnderstandOutput=[understood("chit_chat")], text=["", "  "])
	history = [HumanMessage("a"), AIMessage("b")]
	text, new_history, _b, expression = run(fakes, monkeypatch, "こんにちは", history=history, state={})
	assert text == llm.MESSAGE_EMPTY_RESPONSE and expression == "sorry"
	assert new_history == history
	assert [k for _r, k in fakes.kinds()].count("text") == 2


def test_empty_text_retry_succeeds(monkeypatch, rakuten):
	fakes = FakeLLMs(UnderstandOutput=[understood("chit_chat")], text=["", "こんにちは！"])
	text, _h, _b, _e = run(fakes, monkeypatch, "こんにちは", state={})
	assert text == "こんにちは！"


def test_internal_text_is_not_shown(monkeypatch, rakuten):
	fakes = FakeLLMs(UnderstandOutput=[understood("chit_chat")], text=["search_books(keywords=['猫'])", "こんにちは！"])
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
	profile = graph_v2.normalize_profile({"interests": ["猫", "猫", "", 3], "purpose": "宇宙旅行", "reader": None, "mood": None})
	assert profile.interests == ["猫", "3"]
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
			understood("ready", interests=["猫"], reader="子ども"),
		],
		text=["猫が好きなんですね。"],
		PlanOutput=[plan_of(["猫"])],
		SelectOutput=[select_of([{"id": 1, "slot": "ど真ん中", "reason": "a"}])],
	)
	monkeypatch.setattr(llm, "get_llm", fakes.get_llm)

	first = server_module.server.chat_prompt("猫が好き", None, str(PROMPT_DEFAULT), "alice")
	session_id = first.session_id
	assert store.conversations[session_id].profile["interests"] == ["猫"]

	second = server_module.server.chat_prompt("子どもに読ませたい", session_id, str(PROMPT_DEFAULT), "alice")
	assert [b["title"] for b in second.recommended_books] == ["本1"]
	# 2ターン目の understand には、1ターン目のプロフィールが渡っている
	understand_input = fakes.calls[2][2][-1].content
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
	monkeypatch.setattr(graph_v2.crd, "search_crd_hints", lambda words, limit=5: hints)
	rakuten.results["猫"] = [book(1)]
	fakes = FakeLLMs(
		UnderstandOutput=[understood("ready", interests=["猫"])],
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
	assert turn["intent"] == "ready" and turn["route"] == "search"
	assert turn["path"] == ["understand", "route", "crd", "plan", "search", "select"]
	assert [s["node"] for s in turn["steps"]] == turn["path"]
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
