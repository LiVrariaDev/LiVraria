"""API の権限・入力検証・会話フローの検証（Firebase と LLM は差し替える）。"""

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

import backend.api.datastore as datastore_module
import backend.api.routers.search as search_router
import backend.api.server as server_module
from backend.api.auth import get_current_user_id
from backend.api.datastore import DataStore
from backend.api.models import Personal
from conftest import clear_data_dir


@pytest.fixture
def client(monkeypatch):
	clear_data_dir()
	store = DataStore()
	monkeypatch.setattr(server_module.server, "data_store", store)

	def fake_llm_chat(prompt_file, message, history, ai_insight="", **kwargs):
		new_history = history + [HumanMessage(message), AIMessage(f"echo:{message}")]
		return f"echo:{message}", new_history, [], "neutral"

	monkeypatch.setattr(server_module, "llm_chat", fake_llm_chat)
	# ログアウトで始まる要約も差し替え、実際の Gemini を呼ばない
	monkeypatch.setattr(datastore_module, "summary_function", lambda *a, **k: "<summary>要約</summary>")
	current = {"uid": "alice"}
	server_module.app.dependency_overrides[get_current_user_id] = lambda: current["uid"]
	with TestClient(server_module.app) as test_client:
		test_client.store = store
		test_client.current = current
		for uid in ("alice", "bob"):
			store.create_user(uid, Personal(name=uid, gender="other", age=20))
		yield test_client
	server_module.app.dependency_overrides.clear()


def test_put_user_rejects_non_profile_fields(client):
	response = client.put("/users/alice", json={"active_session": "x", "ai_insights": "injected"})
	assert response.status_code == 422
	assert client.store.users["alice"].ai_insights == ""


def test_put_user_updates_profile(client):
	response = client.put("/users/alice", json={"personal": {"name": "アリス"}})
	assert response.status_code == 200
	assert client.store.users["alice"].personal.name == "アリス"
	assert client.store.users["alice"].personal.age == 20


def test_cannot_read_other_users_session(client):
	client.current["uid"] = "bob"
	bob_session = client.post("/sessions/new/messages", json={"message": "秘密"}).json()["session_id"]
	client.current["uid"] = "alice"
	assert client.get(f"/sessions/{bob_session}").status_code == 404
	assert client.post(f"/sessions/{bob_session}/messages", json={"message": "hi"}).status_code == 404


def test_chat_continues_session_and_restarts_after_close(client):
	first = client.post("/sessions/new/messages", json={"message": "1"}).json()["session_id"]
	second = client.post(f"/sessions/{first}/messages", json={"message": "2"}).json()["session_id"]
	assert first == second
	assert len(client.store.get_history(first)) == 4

	assert client.post("/users/alice/logout").status_code == 200
	# クローズ済みセッションに送ると新しいセッションが始まる
	third = client.post(f"/sessions/{first}/messages", json={"message": "3"}).json()["session_id"]
	assert third != first
	assert len(client.store.get_history(first)) == 4


def test_unknown_mode_is_rejected(client):
	assert client.post("/sessions/new/messages?mode=librarian", json={"message": "hi"}).status_code == 400


def test_nfc_auth_requires_device_key(client, monkeypatch):
	client.store.register_nfc("CARD1", "alice")

	monkeypatch.delenv("LIVRARIA_DEVICE_KEY", raising=False)
	assert client.post("/nfc/auth", json={"nfc_id": "CARD1"}).status_code == 503

	monkeypatch.setenv("LIVRARIA_DEVICE_KEY", "kiosk-secret")
	assert client.post("/nfc/auth", json={"nfc_id": "CARD1"}).status_code == 403
	assert client.post("/nfc/auth", json={"nfc_id": "CARD1"}, headers={"X-Device-Key": "wrong"}).status_code == 403

	monkeypatch.setattr(server_module.auth, "create_custom_token", lambda uid: b"token-" + uid.encode())
	response = client.post("/nfc/auth", json={"nfc_id": "CARD1"}, headers={"X-Device-Key": "kiosk-secret"})
	assert response.status_code == 200
	assert response.json() == {"custom_token": "token-alice", "user_id": "alice"}


def test_semantic_search_uses_extracted_keywords(client, monkeypatch):
	monkeypatch.setattr(search_router, "llm_summary", lambda *a, **k: "宇宙 SF\n")
	monkeypatch.setattr(search_router, "search_books_random", lambda keywords: [{"keywords": keywords}])
	response = client.get("/books/search", params={"q": "宇宙の話が読みたい", "semantic": "true"})
	assert response.json() == [{"keywords": ["宇宙", "SF"]}]


def test_cors_does_not_allow_arbitrary_origin(client):
	response = client.options(
		"/users/alice",
		headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
	)
	assert "access-control-allow-origin" not in response.headers


def test_university_search_without_appid_is_503(client, monkeypatch):
	monkeypatch.delenv("CINII_APPID", raising=False)
	assert client.get("/search/university/books", params={"q": "Python"}).status_code == 503
	assert client.get("/search/university/books").status_code == 400
