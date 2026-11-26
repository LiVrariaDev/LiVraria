"""Gemini の役割別モデル、429 対応、使用量記録、要約と Insights の一括生成、デモアカウント管理の検証。"""

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import backend.api.datastore as datastore_module
import backend.api.llm as llm
from backend import DATA_DIR, PROMPT_DEFAULT, PROMPT_SUMMARY, USERS_FILE
from backend.api import llm_usage
from backend.api.models import Personal
from backend.tools import demo_account


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
	for name in ("GEMINI_CHAT_MODEL", "GEMINI_SUMMARY_MODEL", "GEMINI_LIGHT_MODEL",
	             "GEMINI_API_MAX_RETRIES", "GEMINI_API_TIMEOUT"):
		monkeypatch.delenv(name, raising=False)
	llm_usage.reset()


class _RateLimitError(Exception):
	code = 429


class ResourceExhausted(Exception):
	pass


# 1. get_gemini_model

def test_get_gemini_model_defaults_and_env(monkeypatch):
	assert llm.get_gemini_model("chat") == "gemini-3.5-flash-lite"
	assert llm.get_gemini_model("summary") == "gemini-4-hydrogen"
	assert llm.get_gemini_model("light") == "gemini-2.5-flash-lite"
	monkeypatch.setenv("GEMINI_CHAT_MODEL", "my-chat")
	assert llm.get_gemini_model("chat") == "my-chat"
	with pytest.raises(ValueError):
		llm.get_gemini_model("unknown")


# 2. get_llm

class _FakeGemini:
	instances = []

	def __init__(self, **kwargs):
		self.kwargs = kwargs
		_FakeGemini.instances.append(self)


def test_get_llm_arguments(monkeypatch):
	monkeypatch.setattr(llm, "ChatGoogleGenerativeAI", _FakeGemini)

	chat = llm.get_llm(role="chat", backend="gemini")
	assert chat.kwargs["model"] == "gemini-3.5-flash-lite"
	assert "thinking_budget" not in chat.kwargs
	assert chat.kwargs["max_retries"] == 1

	monkeypatch.setenv("GEMINI_LIGHT_MODEL", "gemini-2.5-flash-lite")
	monkeypatch.setenv("GEMINI_API_MAX_RETRIES", "3")
	light = llm.get_llm(role="light", backend="gemini")
	assert light.kwargs["thinking_budget"] == 0
	assert light.kwargs["max_retries"] == 3


# 3. is_rate_limit_error

def test_is_rate_limit_error():
	assert llm.is_rate_limit_error(_RateLimitError("x"))
	assert llm.is_rate_limit_error(ResourceExhausted("x"))
	assert llm.is_rate_limit_error(RuntimeError("RESOURCE_EXHAUSTED: quota"))
	try:
		try:
			raise _RateLimitError("inner")
		except _RateLimitError as e:
			raise RuntimeError("wrapped") from e
	except RuntimeError as wrapped:
		assert llm.is_rate_limit_error(wrapped)
	assert not llm.is_rate_limit_error(RuntimeError("boom"))


# 4. llm_chat の 429

class _RaisingLLM:
	def __init__(self, exc):
		self.exc = exc

	def bind_tools(self, tools):
		return self

	def invoke(self, messages):
		raise self.exc


def test_chat_rate_limit_returns_busy_message(monkeypatch):
	llm_usage.reset()
	monkeypatch.setattr(llm, "get_llm", lambda **kwargs: _RaisingLLM(_RateLimitError("429 quota")))
	history = [HumanMessage("こんにちは"), AIMessage("こんにちは！")]

	text, new_history, books, expression = llm.llm_chat(str(PROMPT_DEFAULT), "本を探して", history)

	assert text == llm.MESSAGE_BUSY
	assert new_history == history
	assert books == []
	assert expression == "sorry"
	assert llm_usage.snapshot()["roles"]["chat"]["rate_limited"] == 1


# 5. 使用量

class _OkLLM:
	def invoke(self, messages):
		return AIMessage(
			content="ok",
			usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
		)


def test_usage_recorded_on_success(monkeypatch):
	llm_usage.reset()
	monkeypatch.setattr(llm, "get_llm", lambda **kwargs: _OkLLM())

	assert llm.llm_summary(str(PROMPT_SUMMARY), "text", role="light") == "ok"

	light = llm_usage.snapshot()["roles"]["light"]
	assert light["calls"] == 1
	assert (light["input_tokens"], light["output_tokens"], light["total_tokens"]) == (10, 5, 15)


def test_usage_recorded_on_errors(monkeypatch):
	llm_usage.reset()
	# 他のテストのバックグラウンド要約が "summary" の集計に混ざりうるので "light" を使う。
	monkeypatch.setattr(llm, "get_llm", lambda **kwargs: _RaisingLLM(RuntimeError("boom")))
	assert llm.llm_summary(str(PROMPT_SUMMARY), "text", role="light") is None
	monkeypatch.setattr(llm, "get_llm", lambda **kwargs: _RaisingLLM(_RateLimitError("limit")))
	assert llm.llm_summary(str(PROMPT_SUMMARY), "text", role="light") is None

	light = llm_usage.snapshot()["roles"]["light"]
	assert light["calls"] == 2, light
	assert light["errors"] == 2
	assert light["rate_limited"] == 1


# 6. parse_summary_and_insights

def test_parse_summary_and_insights():
	parse = datastore_module.parse_summary_and_insights
	assert parse("<summary>\n要約\n</summary>\n<ai_insights>\nSF好き\n複数行\n</ai_insights>") == ("要約", "SF好き\n複数行")
	assert parse("<summary>要約</summary>") == ("要約", None)
	assert parse("タグなしの要約") == ("タグなしの要約", None)
	assert parse(None) == (None, None)
	assert parse("") == (None, None)


# 7. generate_summary_and_insights

@pytest.fixture
def store():
	for path in DATA_DIR.iterdir():
		path.unlink()
	return datastore_module.DataStore()


def _make_session(store, user_id="u1", insights="SFが好き"):
	store.create_user(user_id, Personal(name="テスト", gender="female", age=20)).ai_insights = insights
	session_id = store.create_session(user_id)
	store.update_history(session_id, [HumanMessage("歴史小説を探してる")])
	store.close_session(session_id)
	return session_id


def test_generate_updates_summary_and_insights_with_one_call(store, monkeypatch):
	calls = []

	def fake(prompt_file, text, ai_insight=None):
		calls.append(text)
		return "<summary>歴史小説の相談</summary><ai_insights>SF、歴史小説</ai_insights>"

	monkeypatch.setattr(datastore_module, "summary_function", fake)
	session_id = _make_session(store)

	store.generate_summary_and_insights(session_id)

	assert len(calls) == 1
	assert store.conversations[session_id].summary == "歴史小説の相談"
	assert store.users["u1"].ai_insights == "SF、歴史小説"


def test_learning_disabled_skips_llm(store, monkeypatch):
	calls = []
	monkeypatch.setattr(datastore_module, "summary_function", lambda *a, **k: calls.append(a) or "x")
	session_id = _make_session(store)
	store.users["u1"].learning_enabled = False

	store.generate_summary_and_insights(session_id)

	assert calls == []
	assert store.users["u1"].ai_insights == "SFが好き"
	assert store.conversations[session_id].summary is None
	saved = json.loads(datastore_module.CONVERSATIONS_FILE.read_text(encoding="utf-8"))[session_id]
	assert len(saved["messages"]) == 1


def test_summary_only_keeps_existing_insights(store, monkeypatch):
	monkeypatch.setattr(datastore_module, "summary_function", lambda *a, **k: "<summary>要約だけ</summary>")
	session_id = _make_session(store)

	store.generate_summary_and_insights(session_id)

	assert store.conversations[session_id].summary == "要約だけ"
	assert store.users["u1"].ai_insights == "SFが好き"


# 8. demo_account

def _write_users(learning=True):
	user = {"_id": "u1", "ai_insights": "旧", "personal": {"name": "デモ", "gender": "female", "age": 20}, "learning_enabled": learning}
	USERS_FILE.write_text(json.dumps([user], ensure_ascii=False), encoding="utf-8")


def test_demo_account_learning_toggle():
	_write_users()
	assert demo_account.main(["learning", "u1", "off"]) == 0
	assert json.loads(USERS_FILE.read_text(encoding="utf-8"))[0]["learning_enabled"] is False
	assert demo_account.main(["learning", "u1", "on"]) == 0
	assert json.loads(USERS_FILE.read_text(encoding="utf-8"))[0]["learning_enabled"] is True


def test_demo_account_set_insights(tmp_path):
	_write_users()
	insights = tmp_path / "insights.txt"
	insights.write_text("読書傾向:\n- 歴史小説", encoding="utf-8")

	assert demo_account.main(["set-insights", "u1", str(insights)]) == 0
	assert json.loads(USERS_FILE.read_text(encoding="utf-8"))[0]["ai_insights"] == "読書傾向:\n- 歴史小説"


def test_demo_account_unknown_user_returns_1():
	_write_users()
	assert demo_account.main(["show", "nobody"]) == 1
