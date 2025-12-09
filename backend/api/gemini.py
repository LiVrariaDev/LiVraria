# Standard Library
import os
import pprint
from pathlib import Path
import re
import threading
# Third Party
from google import genai
from google.genai import types
# user-defined
from backend import PROMPTS_DIR, PROMPT_DEBUG, GEMINI_API_KEY_RATE
from backend.search.rakuten_books import rakuten_search_books
# 実行する際は、ProjectRootで`python -m backend.api.gemini`

_chat_lock = threading.Lock()
API_KEY_NUMBER = 1
API_KEY_USES = 0
def api_key_chat():
	global API_KEY_USES, API_KEY_NUMBER
	with _chat_lock:
		API_KEY_USES += 1
		if API_KEY_USES > GEMINI_API_KEY_RATE:
			API_KEY_NUMBER += 1
			API_KEY_USES = 0
		API_KEY = os.getenv(f"GEMINI_API_KEY_{API_KEY_NUMBER}", "none")
		if API_KEY == "none":
			logger.error("API Key not found")
			exit()
		return API_KEY

_summary_lock = threading.Lock()
API_KEY_SUMMARY_NUMBER = 1
API_KEY_SUMMARY_USES = 0
def api_key_summary():
	global API_KEY_SUMMARY_USES, API_KEY_SUMMARY_NUMBER
	with _summary_lock:
		API_KEY_SUMMARY_USES += 1
		if API_KEY_SUMMARY_USES > GEMINI_API_KEY_RATE:
			API_KEY_SUMMARY_NUMBER += 1
			API_KEY_SUMMARY_USES = 0
		API_KEY = os.getenv(f"GEMINI_API_KEY_{API_KEY_SUMMARY_NUMBER}", "none")
		if API_KEY == "none":
			logger.error("API Key not found")
			exit()
		return API_KEY

def search_books(keywords: list[list[str]], count: int = 4) -> list[dict]:
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



search_books_declaration = {
	"name": "search_books",
	"description": "Rakuten Books APIを用いて、指定されたキーワードで書籍や資料を検索し、タイトル、著者、出版社、出版年、レビュー、レビュー数、ジャンルなどの情報を取得します。",
	"parameters": {
		"type": "object",
		"properties": {
			"keywords": {
				"type": "array",
				"items": {
					"type": "array",
					"items": {
						"type": "string"
					}
				},
				"description": "検索クエリのリスト。各内部リストのキーワードはAND検索され、それぞれの検索結果を統合して返します。例: [['Python', '機械学習'], ['Python', '人工知能']] → 'Python AND 機械学習'と'Python AND 人工知能'の両方を検索して結果を統合"
			},
			"count": {
				"type": "integer",
				"description": "検索結果の数。デフォルトは4です。",
				"default": 4
			},
		},
		"required": ["keywords"],
	},
}

safety_settings = [types.SafetySetting(
	category="HARM_CATEGORY_HATE_SPEECH",
	threshold="BLOCK_ONLY_HIGH"
), types.SafetySetting(
	category="HARM_CATEGORY_DANGEROUS_CONTENT",
	threshold="BLOCK_ONLY_HIGH"
), types.SafetySetting(
	category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
	threshold="BLOCK_ONLY_HIGH"
), types.SafetySetting(
	category="HARM_CATEGORY_HARASSMENT",
	threshold="BLOCK_ONLY_HIGH"
)]

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

def load_prompt_text(filepath):
	with open(filepath, "r", encoding="utf-8") as f:
		return f.read()

def gemini_chat(prompt_file: str = None, message: str = "", history: list = None, ai_insight: str = None):
	# プロンプト読込 (markdownを推奨)
	prompt = load_prompt_text(prompt_file)
	# ai_insight が与えられている場合はプロンプトに追記してモデルが文脈として使えるようにする
	if ai_insight:
		# 明示的にユーザー情報であることを示すセクションを追加
		prompt += "\n\n---\nユーザー情報 (ai_insights):\n"
		prompt += ai_insight
	if history is None:
		history = []
	
	tools = types.Tool(function_declarations=[search_books_declaration])

	client = genai.Client(api_key=api_key_chat())

	configs = types.GenerateContentConfig(
		temperature=0.5,
		top_p=0.95,
		max_output_tokens=512,
		response_modalities=["text"],
		safety_settings=safety_settings,
		system_instruction=[types.Part(text=prompt)], # システム指示でpromptを与える
		tools=[tools]
	)

	chat = client.chats.create(
		model="gemini-2.5-flash-lite",
		config=configs,
		history=history
	)

	response = chat.send_message(message)

	function_call_part = None
	if response.candidates and response.candidates[0].content.parts:
		function_call_part = response.candidates[0].content.parts[0].function_call

	response_text = ""

	if function_call_part:
		print("Function call detected:\n")
		print(f"Function Name: {function_call_part.name}")

		args = getattr(function_call_part, "args", None)
		if args is None:
			args = getattr(function_call_part, "arguments", None)
		print("Arguments:")
		pprint.pprint(args)
 
		if function_call_part.name == "search_books":
			try:
				# args が JSON 文字列の場合はパースして dict にする
				if isinstance(args, str):
					import json
					args_parsed = json.loads(args)
				else:
					args_parsed = args or {}
				result = search_books(**args_parsed)
				print(f"Function call result:\n{pprint.pformat(result)}\n")
			except Exception as e:
				print(f"Error occurred while calling function '{function_call_part.name}': {e}")
 
			function_response_part = types.Part.from_function_response(
				name=function_call_part.name,
				response={"result": result},
			)
 
			final_response = chat.send_message([function_response_part])
			response_text = remove_markdown_formatting(final_response.text)
	else:
		response_text = re.sub(r'<thought>.*?</thought>', '', response.text, flags=re.DOTALL).strip()
		response_text = remove_markdown_formatting(response_text)
		

	new_history = chat.get_history()

	return response_text, new_history

def gemini_summary(prompt_file: str = None, message: str = "", ai_insight: str = None):
	# プロンプト読込 (markdownを推奨)
	prompt = load_prompt_text(prompt_file)
	# ai_insight が与えられている場合はプロンプトに追記してモデルが文脈として使えるようにする
	if ai_insight:
		# 明示的にユーザー情報であることを示すセクションを追加
		prompt += "\n\n---\nユーザー情報 (ai_insights):\n"
		prompt += ai_insight
	
	# モデルのセーフティー設定
	safety_settings = [types.SafetySetting(
		category="HARM_CATEGORY_HATE_SPEECH",
		threshold="BLOCK_ONLY_HIGH"
	), types.SafetySetting(
		category="HARM_CATEGORY_DANGEROUS_CONTENT",
		threshold="BLOCK_ONLY_HIGH"
	), types.SafetySetting(
		category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
		threshold="BLOCK_ONLY_HIGH"
	), types.SafetySetting(
		category="HARM_CATEGORY_HARASSMENT",
		threshold="BLOCK_ONLY_HIGH"
	)]

	client = genai.Client(api_key=api_key_summary())

	configs = types.GenerateContentConfig(
		temperature=0.5,
		top_p=0.95,
		max_output_tokens=512,
		response_modalities=["text"],
		safety_settings=safety_settings,
		system_instruction=[types.Part(text=prompt)], # システム指示でpromptを与える
	)

	chat = client.chats.create(
		model="gemini-2.5-flash",
		config=configs,
		history=[]
	)

	response = chat.send_message(message)

	response_text = remove_markdown_formatting(response.text)
	return response_text

if __name__ == "__main__":
	import json
	test_query_sets = [["ミステリー", "傑作"], ["感動", "泣ける"]]

	data = search_books(test_query_sets)
	pprint.pprint(data)