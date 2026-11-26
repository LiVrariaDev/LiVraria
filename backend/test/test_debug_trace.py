"""LLM トレース記録・管理者キー・デバッグ API の検証（LLM は差し替える。実 API は使わない）。"""

import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

import backend.api.llm as llm
import backend.api.server as server_module
import backend.api.trace_store as trace_store
from backend import PROMPT_DEFAULT
from backend.api.auth import get_current_user_id
from backend.api.datastore import DataStore
from backend.api.models import Personal
from backend.api.routers import debug
from backend.api.trace_store import TraceStore, current_turn


class _TextLLM:
	def bind_tools(self, tools):
		return self

	def invoke(self, messages):
		return AIMessage(content="こんにちは")


class _ToolLLM:
	def __init__(self):
		self.calls = 0

	def bind_tools(self, tools):
		return self

	def invoke(self, messages):
		self.calls += 1
		if self.calls == 1:
			return AIMessage(content="", tool_calls=[{"name": "recommend_books", "args": {"selections": []}, "id": "call1"}])
		return AIMessage(content="該当なしでした")


class _RaisingLLM:
	def bind_tools(self, tools):
		return self

	def invoke(self, messages):
		raise RuntimeError("boom")


@pytest.fixture(autouse=True)
def _isolated_store(monkeypatch, tmp_path):
	monkeypatch.setattr(trace_store, "DATA_DIR", tmp_path)
	trace_store.reset_trace_store()
	yield
	trace_store.reset_trace_store()


def _run_chat(monkeypatch, fake, traced=True):
	monkeypatch.setattr(llm, "get_llm", lambda **kwargs: fake)
	turn = None
	token = None
	if traced:
		turn = TraceStore("unused", 10).start_turn("t" * 32, "s1", "u1", "こんにちは")
		token = current_turn.set(turn)
	try:
		result = llm.llm_chat(str(PROMPT_DEFAULT), "こんにちは", [])
	finally:
		if token is not None:
			current_turn.reset(token)
	return turn, result


def test_trace_records_agent_step(monkeypatch):
	turn, result = _run_chat(monkeypatch, _TextLLM())
	assert [s.node for s in turn.steps] == ["agent"]
	assert turn.steps[0].ai_text == "こんにちは"
	assert turn.steps[0].attempt == 0
	assert turn.error is None


def test_trace_records_tool_calls(monkeypatch):
	turn, _ = _run_chat(monkeypatch, _ToolLLM())
	assert [s.node for s in turn.steps] == ["agent", "tools", "agent"]
	assert turn.steps[0].tool_calls == [{"name": "recommend_books", "args": {"selections": []}}]
	assert turn.steps[1].tool_results and turn.steps[1].tool_results[0]["name"] == "recommend_books"
	assert turn.steps[2].ai_text == "該当なしでした"


def test_trace_records_exception_traceback(monkeypatch):
	turn, result = _run_chat(monkeypatch, _RaisingLLM())
	assert result[0] == llm.MESSAGE_EXCEPTION
	assert turn.error["type"] == "RuntimeError"
	assert "boom" in turn.error["message"]
	assert "Traceback" in turn.error["traceback"]


def test_return_value_unchanged_by_tracing(monkeypatch):
	_, traced = _run_chat(monkeypatch, _TextLLM(), traced=True)
	_, plain = _run_chat(monkeypatch, _TextLLM(), traced=False)
	assert traced[0] == plain[0]
	assert [m.content for m in traced[1]] == [m.content for m in plain[1]]
	assert traced[2:] == plain[2:]


def test_no_debug_routes_without_env(monkeypatch):
	monkeypatch.delenv("LIVRARIA_DEBUG", raising=False)
	assert not any(path.startswith("/debug") for path in server_module.app.openapi()["paths"])
	assert server_module.register_debug_routes(FastAPI()) is False


def test_register_debug_routes_when_enabled(monkeypatch):
	monkeypatch.setenv("LIVRARIA_DEBUG", "true")
	app = FastAPI()
	assert server_module.register_debug_routes(app) is True
	assert any(path.startswith("/debug") for path in app.openapi()["paths"])


def test_admin_key_and_debug_api(monkeypatch):
	app = FastAPI()
	app.include_router(debug.router)
	client = TestClient(app)

	monkeypatch.delenv("LIVRARIA_ADMIN_KEY", raising=False)
	assert client.get("/debug/graph").status_code == 503

	monkeypatch.setenv("LIVRARIA_ADMIN_KEY", "admin-secret")
	assert client.get("/debug/graph").status_code == 401
	assert client.get("/debug/graph", headers={"X-Admin-Key": "wrong"}).status_code == 403

	headers = {"X-Admin-Key": "admin-secret"}
	response = client.get("/debug/graph", headers=headers)
	assert response.status_code == 200
	mermaid = response.json()["mermaid"]
	assert "agent" in mermaid and "tools" in mermaid
	assert client.get("/debug/usage", headers=headers).status_code == 200
	# LIVRARIA_DEBUG 未設定ではストアがないので、一覧は空、ターンは 404
	assert client.get("/debug/sessions", headers=headers).json() == {"sessions": []}
	assert client.get("/debug/turns/none", headers=headers).status_code == 404


def test_trace_store_lifecycle(tmp_path):
	store = TraceStore(tmp_path, 2)
	for i in range(3):
		turn = store.start_turn(f"id{i}", "s1" if i < 2 else "s2", "u1", f"msg{i}")
		turn.response_text = f"res{i}"
		store.finish_turn(turn)

	# limit=2 なので最古の id0 は消える
	assert store.get_turn("id0") is None
	assert store.get_turn("id2")["user_message"] == "msg2"
	sessions = store.list_sessions()
	assert [s["session_id"] for s in sessions] == ["s2", "s1"]
	assert sessions[1]["turns"] == 1
	assert [t["trace_id"] for t in store.list_turns("s1")] == ["id1"]

	files = list((tmp_path / "traces").glob("*.jsonl"))
	assert len(files) == 1
	lines = files[0].read_text(encoding="utf-8").splitlines()
	assert len(lines) == 3
	assert json.loads(lines[0])["trace_id"] == "id0"


def test_trace_id_log_filter():
	logger = logging.getLogger("test_trace_filter")
	trace_store.install_log_filter("test_trace_filter")
	trace_store.install_log_filter("test_trace_filter")
	assert sum(isinstance(f, trace_store.TraceIdFilter) for f in logger.filters) == 1

	record = logging.LogRecord("x", logging.INFO, __file__, 1, "hello", None, None)
	token = trace_store.current_trace_id.set("abcdef0123456789")
	try:
		flt = trace_store.TraceIdFilter()
		assert flt.filter(record) is True
		flt.filter(record)
	finally:
		trace_store.current_trace_id.reset(token)
	assert record.msg == "[trace=abcdef01] hello"
	assert record.trace_id == "abcdef0123456789"


def test_chat_response_has_trace_id(monkeypatch):
	store = DataStore()
	monkeypatch.setattr(server_module.server, "data_store", store)

	def fake_llm_chat(prompt_file, message, history, ai_insight="", **kwargs):
		return "ok", history + [HumanMessage(message), AIMessage("ok")], [], "neutral"

	monkeypatch.setattr(server_module, "llm_chat", fake_llm_chat)
	monkeypatch.setenv("LIVRARIA_DEBUG", "true")
	server_module.app.dependency_overrides[get_current_user_id] = lambda: "alice"
	try:
		store.create_user("alice", Personal(name="alice", gender="other", age=20))
		with TestClient(server_module.app) as client:
			data = client.post("/sessions/new/messages", json={"message": "hi"}).json()
		assert len(data["trace_id"]) == 32
		assert data["failed"] is False
		recorded = trace_store.get_trace_store().get_turn(data["trace_id"])
		assert recorded["user_message"] == "hi" and recorded["response_text"] == "ok"
	finally:
		server_module.app.dependency_overrides.clear()
