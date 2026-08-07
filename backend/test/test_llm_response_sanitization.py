"""LLM応答の表示用整形と表情選択の検証。"""

from langchain_core.messages import ToolMessage

from backend.api.llm import (
	contains_internal_response,
	extract_user_visible_text,
	select_expression,
)


def test_extract_user_visible_text_omits_thinking_parts():
	content = [
		{"type": "thinking", "thinking": "表情を決める"},
		{"type": "text", "text": "こんばんは。今日はどのように過ごされましたか？"},
	]

	assert extract_user_visible_text(content) == "こんばんは。今日はどのように過ごされましたか？"


def test_internal_tool_code_is_detected():
	content = "tool_code\nprint(default_api.update_expression(expression_type='happy'))\nthought\n..."

	assert contains_internal_response(extract_user_visible_text(content))


def test_expression_is_happy_when_books_are_recommended():
	messages = [
		ToolMessage(
			content="検索結果（1冊）",
			name="search_books",
			tool_call_id="search-1",
		)
	]

	assert select_expression("本を選びました。", messages, [{"title": "本"}]) == "happy"


def test_expression_is_sorry_when_search_finds_nothing():
	messages = [
		ToolMessage(
			content="申し訳ございません。該当する書籍が見つかりませんでした。",
			name="search_books",
			tool_call_id="search-1",
		)
	]

	assert select_expression("条件に合う本がありませんでした。", messages, []) == "sorry"


def test_expression_defaults_to_neutral_for_conversation():
	assert select_expression("こんばんは。", [], []) == "neutral"
