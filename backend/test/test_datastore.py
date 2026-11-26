"""DataStore の永続化・タイムアウト・所有者チェックの検証。"""

import json
from datetime import datetime, timedelta

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import backend.api.datastore as datastore_module
from backend import CONVERSATIONS_FILE, DATA_DIR, USERS_FILE
from backend.api.models import ChatStatus, Personal, UserStatus
from conftest import clear_data_dir


@pytest.fixture
def summaries(monkeypatch):
	"""LLM を呼ばずに、要約関数へ渡されたテキストを記録する。"""
	calls = []

	def fake_summary(prompt_file, text, ai_insight=None):
		calls.append(text)
		return f"SUMMARY#{len(calls)}"

	monkeypatch.setattr(datastore_module, "summary_function", fake_summary)
	return calls


@pytest.fixture
def store():
	clear_data_dir()
	return datastore_module.DataStore()


def _user(store, user_id="u1"):
	return store.create_user(user_id, Personal(name="テスト", gender="female", age=20))


def test_timeout_keeps_conversation_and_summarizes_it(store, summaries):
	_user(store)
	session_id = store.create_session("u1")
	store.update_history(session_id, [HumanMessage("SFの本ある?"), AIMessage("あります")])
	store.users["u1"].lastlogin = datetime.now() - timedelta(days=1)

	assert store.check_user_timeout() == [session_id]

	saved = json.loads(CONVERSATIONS_FILE.read_text(encoding="utf-8"))[session_id]
	assert saved["status"] == ChatStatus.closed
	assert len(saved["messages"]) == 2
	assert "SFの本ある?" in summaries[0]
	assert store.users["u1"].active_session is None
	assert store.users["u1"].status == UserStatus.logout


def test_empty_conversation_does_not_overwrite_insights(store, summaries):
	_user(store).ai_insights = "SFが好き"
	session_id = store.create_session("u1")
	store.close_session(session_id)

	store.generate_summary_and_insights(session_id)

	assert summaries == []
	assert store.users["u1"].ai_insights == "SFが好き"


def test_failed_summary_keeps_existing_insights(store, monkeypatch):
	monkeypatch.setattr(datastore_module, "summary_function", lambda *a, **k: None)
	_user(store).ai_insights = "SFが好き"
	session_id = store.create_session("u1")
	store.update_history(session_id, [HumanMessage("こんにちは")])
	store.close_session(session_id)

	store.generate_summary_and_insights(session_id)

	assert store.users["u1"].ai_insights == "SFが好き"


def test_session_ownership_uses_conversation_owner(store):
	_user(store, "attacker")
	_user(store, "victim")
	victim_session = store.create_session("victim")
	store.users["attacker"].active_session = victim_session

	assert not store.has_user_session("attacker", victim_session)
	assert store.has_user_session("victim", victim_session)


def test_corrupted_file_is_backed_up_instead_of_wiped(store):
	_user(store)
	USERS_FILE.write_text("[{broken", encoding="utf-8")

	reloaded = datastore_module.DataStore()

	assert reloaded.users == {}
	assert any(p.name.startswith("users.json.corrupt-") for p in DATA_DIR.iterdir())


def test_nfc_card_of_another_user_is_not_taken_over(store):
	_user(store, "owner")
	_user(store, "other")
	store.register_nfc("CARD1", "owner")

	with pytest.raises(PermissionError):
		store.register_nfc("CARD1", "other")
	assert store.get_user_by_nfc("CARD1") == "owner"


def test_update_personal_validates_types(store):
	_user(store)
	with pytest.raises(ValueError):
		store.update_personal("u1", {"age": "二十歳"})
	assert store.update_personal("u1", {"name": "新しい名前"}).personal.name == "新しい名前"
