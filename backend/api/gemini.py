# Standard Library
import os
# Third Party
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

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
        model="gemini-2.0-flash",
        config=configs,
        history=history
    )

    response = chat.send_message(message)

    new_history = chat.get_history()

    return response.text, new_history
