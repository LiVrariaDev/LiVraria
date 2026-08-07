"""LLM応答から内部形式を除外する処理の検証。"""

from backend.api.llm import contains_internal_response, extract_user_visible_text


def test_extract_user_visible_text_omits_thinking_parts():
	content = [
		{"type": "thinking", "thinking": "表情を決める"},
		{"type": "text", "text": "こんばんは。今日はどのように過ごされましたか？"},
	]

	assert extract_user_visible_text(content) == "こんばんは。今日はどのように過ごされましたか？"


def test_internal_tool_code_is_detected():
	content = "tool_code\nprint(default_api.update_expression(expression_type='happy'))\nthought\n..."

	assert contains_internal_response(extract_user_visible_text(content))
