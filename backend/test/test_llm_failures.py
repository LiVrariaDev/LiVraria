"""LLM 失敗時に内部情報を返さず、履歴や AI Insights を汚さないことの検証。"""

from langchain_core.messages import AIMessage, HumanMessage

import backend.api.llm as llm
from backend import PROMPT_DEFAULT, PROMPT_SUMMARY


class _RaisingLLM:
	def bind_tools(self, tools):
		return self

	def invoke(self, messages):
		raise RuntimeError("secret-api-key=XYZ connection refused")


class _ListContentLLM:
	def invoke(self, messages):
		self.messages = messages
		return AIMessage(content=[{"type": "text", "text": "要約です"}])


def test_chat_exception_hides_details_and_keeps_history(monkeypatch):
	monkeypatch.setattr(llm, "get_llm", lambda **kwargs: _RaisingLLM())
	history = [HumanMessage("こんにちは"), AIMessage("こんにちは！")]

	text, new_history, books, expression = llm.llm_chat(str(PROMPT_DEFAULT), "本を探して", history)

	assert "secret" not in text
	assert text == llm.MESSAGE_EXCEPTION
	assert new_history == history
	assert books == []
	assert expression == "sorry"


def test_summary_failure_returns_none(monkeypatch):
	monkeypatch.setattr(llm, "get_llm", lambda **kwargs: _RaisingLLM())

	assert llm.llm_summary(str(PROMPT_SUMMARY), "user: こんにちは") is None


def test_summary_has_no_book_instructions_and_handles_list_content(monkeypatch):
	fake = _ListContentLLM()
	monkeypatch.setattr(llm, "get_llm", lambda **kwargs: fake)

	assert llm.llm_summary(str(PROMPT_SUMMARY), "user: こんにちは") == "要約です"
	assert "search_books" not in fake.messages[0].content
