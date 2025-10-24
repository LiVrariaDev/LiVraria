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
        system_instruction=[types.Part(text=prompt)], # システム指示でpromptを与える
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
        response_text = response.text

    new_history = chat.get_history()

    return response_text, new_history
# end def

if __name__ == "__main__":
    import sys
    from pathlib import Path

    print("Dry-run / debug for backend.api.gemini")

    prompts_dir = Path(__file__).resolve().parent / "prompts"
    default_prompt = prompts_dir / "debug.md"
    print("PROMPTS_DIR:", prompts_dir)
    print("default.md exists:", default_prompt.exists())

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set — skipping live API call. Set env var to run full test.")
        sys.exit(0)

    # 簡易テスト入力
    sample_message = "おすすめのPython入門書を教えてください。"
    history = []

    try:
        print("Calling gemini_chat with prompt:", default_prompt)
        response_text, new_history = gemini_chat(str(default_prompt), sample_message, history)
        print("=== Response ===")
        print(response_text)
        print("=== New history (len) ===", len(new_history))
        pprint.pprint(new_history[:4])
    except Exception as e:
        print("Exception during gemini_chat:")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("Debug finished.")
    sys.exit(0)
# ...existing code...