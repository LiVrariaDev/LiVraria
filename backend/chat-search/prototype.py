import os
import re
import requests
import urllib.parse
import pprint

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def extract_keywords(article : str) -> list[str]:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    # Set the model to Gemini
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = f"""
    あなたは図書館の検索システムのAIです.
    以下の文章から, 本を検索するために適切なキーワードやフレーズを3~5個, 日本語で抽出してください.
    キーワードは必ず1単語で, スペースを含めないようにしてください.
    文章:
    '{article}'
    出力形式: 半角コンマで区切られたキーワードのリスト
    例: keyword1,keyword2,keyword3

    """

    response = model.generate_content(prompt)
    print("Response:", response)

    # 結果を改行で分割
    result = response.text.split('\n')

    # 空行を削除
    result = [item for item in result if item]

    return result

def search_books(keywords: list[str], max_results: int = 10) -> list[dict]:
    # NDI APIを使って検索
    # SRU, anywhere検索(NDLの簡易検索と同じ)
    query = 'anywhere="' + ' '.join(keywords) + '"'
    encoded_query = urllib.parse.quote(query, safe='="')
    # ex) anywhere="keyword1 keyword2 keyword3"

    print("Query:", query)

    # request
    url = (
        "https://ndlsearch.ndl.go.jp/api/sru"
        f"?operation=searchRetrieve"
        f"&query={encoded_query}"
        f"&maximumRecords={max_results}"
        "&recordSchema=dcndl"
    )

    print("URL:", url)
    
    response = requests.get(url)
    response.raise_for_status()

    # 一旦ここまで
    with open("response.xml", "w", encoding="utf-8") as f:
        f.write(response.text)

def main():
    article = input("検索したい本の内容を入力してください: ")
    keywords = extract_keywords(article)
    pprint.pprint(keywords)
    search_books(keywords, 10)
    

if __name__ == "__main__":
    keyword = ["Python", "AI", "プロンプト"]
    search_books(keyword, 10)
