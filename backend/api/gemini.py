# Standard Library
import os
import pprint
# Third Party
from google import genai
from google.genai import types
from dotenv import load_dotenv
# user-defined
from backend.search.cinii_search import search_books
# 実行する際は、ProjectRootで`python -m backend.api.gemini`

load_dotenv()

search_books_declaration = {
    "name": "search_books",
    "description": "CiNii APIを用いて、指定されたキーワードで書籍や資料を検索し、タイトル、著者、出版社、出版年などの情報を取得します。キーワードはAND検索されます。",
    "parameters": {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "検索に使用するキーワードのリスト。例: ['Python', '機械学習'] これらのキーワードはAND検索されます。"
            },
            "pages": {
                "type": "integer",
                "description": "検索結果のページ番号。結果をページ送りにしたい場合に使用します。デフォルトは1です。",
                "default": 1
            },
        },
        "required": ["keywords"],
    },
}

def load_prompt_text(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def gemini_chat(prompt_file, message, history):
    # プロンプト読込 (markdownを推奨)
    prompt = load_prompt_text(prompt_file)
    
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

    tools = types.Tool(function_declarations=[search_books_declaration])

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    configs = types.GenerateContentConfig(
        temperature=0.5,
        top_p=0.95,
        max_output_tokens=512,
        response_modalities=["text"],
        safety_settings=safety_settings,
        system_instruction=[types.Part(text=prompt)], # システム指示でpromptを与える]
        tools=[tools]
    )

    chat = client.chats.create(
        model="gemini-2.0-flash",
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

        args = getattr(function_call_part, 'args', function_call_part.arguments)
        print(f"Arguments: {pprint.pformat(args)}\n")

        if function_call_part.name == "search_books":
            try:
                result = search_books(**args)
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
        response_text = response.text

    new_history = chat.get_history()

    return response_text, new_history
# end def