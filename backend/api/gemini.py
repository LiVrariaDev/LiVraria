# Standard Library
import os
import pprint
from pathlib import Path
# Third Party
from google import genai
from google.genai import types
# user-defined
from backend import PROMPTS_DIR, PROMPT_DEBUG
from backend.search.google_books import google_search_books
# 実行する際は、ProjectRootで`python -m backend.api.gemini`

def search_books(keywords: list[list[str]], count: int = 4) -> list[dict]:
	integrated_results = {
		"search_result": []
	}
	seen_ids = set()
	for i, item in enumerate(keywords):
		books = google_search_books(item, count)
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
	"description": "Google Books APIを用いて、指定されたキーワードで書籍や資料を検索し、タイトル、著者、出版社、出版年などの情報を取得します。",
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

	client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

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
			response_text = final_response.text
	else:
		response_text = re.sub(r'<thought>.*?</thought>', '', response.text, flags=re.DOTALL).strip()
		

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

	client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

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

	return response.text

if __name__ == "__main__":
	import json
	test_query_sets = [["ミステリー", "傑作"], ["感動", "泣ける"]]

	data = search_books(test_query_sets)
	pprint.pprint(data)