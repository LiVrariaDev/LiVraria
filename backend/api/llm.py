# Standard Library
import os
import json
import re
import pprint
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

# Third Party
import requests

# user-defined
from backend import PROMPTS_DIR
from backend.search.rakuten_books import rakuten_search_books

# Ollama APIのエンドポイント（デフォルト）
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


def remove_markdown_formatting(text: str) -> str:
	"""
	Markdown記号を除去してプレーンテキストに変換
	
	Args:
		text: Markdown形式のテキスト
		
	Returns:
		プレーンテキスト
	"""
	if not text:
		return text
	
	# コードブロックを除去（```で囲まれた部分）
	text = re.sub(r'```[a-z]*\n.*?\n```', '', text, flags=re.DOTALL)
	
	# インラインコードを除去（`で囲まれた部分）
	text = re.sub(r'`([^`]+)`', r'\1', text)
	
	# 太字を除去（**または__で囲まれた部分）
	text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
	text = re.sub(r'__([^_]+)__', r'\1', text)
	
	# イタリックを除去（*または_で囲まれた部分）
	text = re.sub(r'\*([^*]+)\*', r'\1', text)
	text = re.sub(r'_([^_]+)_', r'\1', text)
	
	# 見出し記号を除去（#で始まる行）
	text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
	
	# リンクを除去（[テキスト](URL)形式）
	text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
	
	# リストマーカーを除去（-、*、+で始まる行）
	text = re.sub(r'^[\-\*\+]\s+', '', text, flags=re.MULTILINE)
	
	# 番号付きリストマーカーを除去（1.で始まる行）
	text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
	
	# 引用記号を除去（>で始まる行）
	text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
	
	# 水平線を除去（---または***）
	text = re.sub(r'^[\-\*]{3,}$', '', text, flags=re.MULTILINE)
	
	# 余分な空行を削除
	text = re.sub(r'\n{3,}', '\n\n', text)
	
	return text.strip()

def search_books(keywords: list[list[str]], count: int = 4) -> list[dict]:
	"""
	楽天Books APIを使って書籍を検索
	
	Args:
		keywords: 検索キーワードのリスト（各内部リストはAND検索）
		count: 取得する書籍数
		
	Returns:
		検索結果の辞書
	"""
	integrated_results = {
		"search_result": []
	}
	seen_ids = set()
	for i, item in enumerate(keywords):
		books = rakuten_search_books(item, count)
		current_context_result = {
			"context_query": ", ".join(item),
			"books": []
		}

		for j, book in enumerate(books):
			book_id = book.get("isbn")
			if book_id not in seen_ids:
				seen_ids.add(book_id)
				index = {
					"index": i*100 + j
				}
				book.update(index)
				current_context_result["books"].append(book)

		if current_context_result["books"]:
			integrated_results["search_result"].append(current_context_result)

	return integrated_results


def load_prompt_text(filepath: str) -> str:
	"""プロンプトファイルを読み込む"""
	with open(filepath, "r", encoding="utf-8") as f:
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
	prompt = base_prompt
	
	# Function calling用の指示を追加
	prompt += """

---
## 書籍検索機能の使用方法

書籍検索が必要な場合、他のテキストは一切含めず、以下のJSON形式のみを出力すること。
複数の検索クエリを送信する場合は、各クエリを配列の要素として含めること。

```json
{
  "tool_call": "search_books",
  "keywords": [["キーワード1", "キーワード2"], ["キーワード3"]],
  "count": 4
}
```

例：
- Pythonと機械学習に関する本を検索: `{"tool_call": "search_books", "keywords": [["Python", "機械学習"]], "count": 4}`
- ミステリーと感動する本を別々に検索: `{"tool_call": "search_books", "keywords": [["ミステリー", "傑作"], ["感動", "泣ける"]], "count": 4}`

検索結果を受け取った後は、通常の会話形式でユーザーに推薦を提示すること。
"""
	
	# ai_insightがある場合は追加
	if ai_insight:
		prompt += "\n\n---\nユーザー情報 (ai_insights):\n"
		prompt += ai_insight
	
	return prompt


def detect_tool_call(response_text: str) -> Optional[Dict[str, Any]]:
	"""
	レスポンスからJSON形式のtool callを検出
	
	Args:
		response_text: LLMのレスポンステキスト
		
	Returns:
		tool callの辞書、検出されない場合はNone
	"""
	# JSONブロックを探す（```json ... ``` または直接JSONオブジェクト）
	json_pattern = r'```json\s*(\{.*?\})\s*```|(\{[^{}]*"tool_call"[^{}]*\})'
	matches = re.findall(json_pattern, response_text, re.DOTALL)
	
	if not matches:
		return None
	
	# マッチした最初のJSONを取得
	json_str = matches[0][0] or matches[0][1]
	
	try:
		tool_call = json.loads(json_str)
		if "tool_call" in tool_call:
			return tool_call
	except json.JSONDecodeError as e:
		print(f"JSON parse error: {e}")
		return None
	
	return None


def call_ollama_api(
	model: str,
	messages: List[Dict[str, str]],
	temperature: float = 0.7,
	max_tokens: int = 512
) -> str:
	"""
	Ollama APIを呼び出す
	
	Args:
		model: 使用するモデル名
		messages: メッセージ履歴
		temperature: 温度パラメータ
		max_tokens: 最大トークン数
		
	Returns:
		LLMのレスポンステキスト
	"""
	payload = {
		"model": model,
		"messages": messages,
		"stream": False,
		"options": {
			"temperature": temperature,
			"num_predict": max_tokens
		}
	}
	
	try:
		response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
		response.raise_for_status()
		result = response.json()
		return result["message"]["content"]
	except requests.exceptions.RequestException as e:
		print(f"Error calling Ollama API: {e}")
		raise


def llm_chat(
	prompt_file: str,
	message: str,
	history: Optional[List[Dict[str, str]]] = None,
	ai_insight: Optional[str] = None,
	model: Optional[str] = None,
	temperature: float = 0.3,  # 0.7から0.3に下げて指示に従いやすく
	max_tokens: int = 512
) -> Tuple[str, List[Dict[str, str]]]:
	"""
	ローカルLLMとチャット（function calling対応）
	
	Args:
		prompt_file: プロンプトファイルのパス
		message: ユーザーメッセージ
		history: 会話履歴
		ai_insight: ユーザー情報
		model: 使用するモデル名（Noneの場合は環境変数から取得）
		temperature: 温度パラメータ
		max_tokens: 最大トークン数
		
	Returns:
		(レスポンステキスト, 新しい会話履歴)
	"""
	# プロンプト読込
	base_prompt = load_prompt_text(prompt_file)
	system_prompt = create_system_prompt(base_prompt, ai_insight)
	
	# モデル名の決定
	if model is None:
		model = OLLAMA_MODEL
	
	# 履歴の初期化
	if history is None:
		history = []
	
	# 履歴がMessageオブジェクトのリストの場合は辞書形式に変換
	converted_history = []
	for item in history:
		if hasattr(item, 'role') and hasattr(item, 'content'):
			# Messageオブジェクトの場合
			role = item.role
			# "model"を"assistant"に変換
			if role == "model":
				role = "assistant"
			converted_history.append({
				"role": role,
				"content": item.content
			})
		elif isinstance(item, dict):
			# すでに辞書形式の場合
			role = item.get("role", "user")
			# "model"を"assistant"に変換
			if role == "model":
				role = "assistant"
			converted_history.append({
				"role": role,
				"content": item.get("content", "")
			})
		else:
			# その他の場合はスキップ
			print(f"Warning: Skipping unknown history item type: {type(item)}")
			continue
	
	# デバッグ: 変換後の履歴を確認
	if history and not converted_history:
		print(f"Warning: History conversion failed. Original history length: {len(history)}")
		print(f"First item type: {type(history[0]) if history else 'N/A'}")
	
	# メッセージリストの構築
	messages = [{"role": "system", "content": system_prompt}]
	messages.extend(converted_history)
	messages.append({"role": "user", "content": message})
	
	# LLM呼び出し
	response_text = call_ollama_api(model, messages, temperature, max_tokens)
	
	# Tool callの検出
	tool_call = detect_tool_call(response_text)
	
	if tool_call and tool_call.get("tool_call") == "search_books":
		print("Tool call detected:")
		pprint.pprint(tool_call)
		
		# 書籍検索を実行
		try:
			keywords = tool_call.get("keywords", [])
			count = tool_call.get("count", 4)
			search_result = search_books(keywords, count)
			print(f"Search result:\n{pprint.pformat(search_result)}\n")
			
			# 検索結果をLLMに渡して最終レスポンスを生成
			result_message = f"検索結果:\n{json.dumps(search_result, ensure_ascii=False, indent=2)}"
			messages.append({"role": "assistant", "content": response_text})
			messages.append({"role": "user", "content": result_message})
			
			final_response = call_ollama_api(model, messages, temperature, max_tokens)
			
			# Markdown記号を除去
			final_response_clean = remove_markdown_formatting(final_response)
			
			# 履歴を更新
			new_history = history + [
				{"role": "user", "content": message},
				{"role": "assistant", "content": response_text},
				{"role": "user", "content": result_message},
				{"role": "assistant", "content": final_response_clean}
			]
			
			return final_response_clean, new_history
			
		except Exception as e:
			error_msg = f"書籍検索中にエラーが発生しました: {e}"
			print(error_msg)
			return error_msg, history
	
	# 通常のレスポンス
	# Markdown記号を除去
	response_text_clean = remove_markdown_formatting(response_text)
	
	new_history = history + [
		{"role": "user", "content": message},
		{"role": "assistant", "content": response_text_clean}
	]
	
	return response_text_clean, new_history


def llm_summary(
	prompt_file: str,
	message: str,
	ai_insight: Optional[str] = None,
	model: Optional[str] = None,
	temperature: float = 0.3,  # 0.5から0.3に下げて一貫性を向上
	max_tokens: int = 512
) -> str:
	"""
	ローカルLLMで要約生成（履歴なし）
	
	Args:
		prompt_file: プロンプトファイルのパス
		message: ユーザーメッセージ
		ai_insight: ユーザー情報
		model: 使用するモデル名
		temperature: 温度パラメータ
		max_tokens: 最大トークン数
		
	Returns:
		要約テキスト
	"""
	# プロンプト読込
	base_prompt = load_prompt_text(prompt_file)
	
	# ai_insightがある場合は追加
	if ai_insight:
		base_prompt += "\n\n---\nユーザー情報 (ai_insights):\n"
		base_prompt += ai_insight
	
	# モデル名の決定
	if model is None:
		model = OLLAMA_MODEL
	
	# メッセージリストの構築
	messages = [
		{"role": "system", "content": base_prompt},
		{"role": "user", "content": message}
	]
	
	# LLM呼び出し
	response_text = call_ollama_api(model, messages, temperature, max_tokens)
	
	# Markdown記号を除去
	response_text_clean = remove_markdown_formatting(response_text)
	
	return response_text_clean


if __name__ == "__main__":
	# テスト用
	test_message = "Pythonの機械学習に関する本を教えてください"
	
	# プロンプトファイルのパスを設定（適宜変更）
	from backend import PROMPT_LIBRARIAN
	
	print("Testing LLM chat...")
	response, history = llm_chat(
		prompt_file=str(PROMPT_LIBRARIAN),
		message=test_message,
		history=[]
	)
	
	print(f"\nResponse:\n{response}")
	print(f"\nHistory length: {len(history)}")
