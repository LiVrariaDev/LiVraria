import os
import requests
import time
import pprint
from dotenv import load_dotenv

# .envファイルをロード
load_dotenv()

# Calil API endpoints
CALIL_LIBRARY_ENDPOINT = "https://api.calil.jp/library"
CALIL_BOOK_ENDPOINT = "https://api.calil.jp/check"

# デモ用APIキー
DEMO_API_KEY = "bc3d19b6abbd0af9a59d1011e3098e51"

def search_libraries(pref: str, limit: int = 1) -> list[dict]:
    headers = {}
    params = {
        'appkey': os.getenv("CALIL_API_KEY", DEMO_API_KEY),
        'pref': pref,
        'format': 'json',
        'limit': limit,
        'callback': ''
    }

    try:
        response = requests.get(CALIL_LIBRARY_ENDPOINT, headers=headers, params=params)
        response.raise_for_status()
        json_data = response.json()
        return json_data
    except Exception as e:
        print(f"[ERROR] Library Search Failed: {e}")
        return []

def search_books(isbn: str, systemid: str) -> dict:
    headers = {}
    clean_systemid = systemid.strip()

    params = {
        'appkey': os.getenv("CALIL_API_KEY", DEMO_API_KEY),
        'isbn': isbn,
        'systemid': clean_systemid,
        'format': 'json',
        'callback': 'no'
    }

    # ★修正: 絵文字(🔍)を削除しました
    print(f"[Calil] Searching: ISBN={isbn}, System={clean_systemid}")

    try:
        response = requests.get(CALIL_BOOK_ENDPOINT, headers=headers, params=params)
        
        if not response.ok:
            # ★修正: 絵文字(😱, 📝)を削除しました
            print(f"[ERROR] API Error Status: {response.status_code}")
            print(f"[DEBUG] Response Body: {response.text}")
            return {"error": f"API Error {response.status_code}"}

        json_data = response.json()

        retry_count = 0
        while json_data.get('continue', 0) == 1 and retry_count < 10:
            # ★修正: 絵文字(⏳)を削除しました
            print(f"[Calil] Polling... ({retry_count + 1}/10)")
            time.sleep(2)
            
            polling_params = {
                'appkey': os.getenv("CALIL_API_KEY", DEMO_API_KEY),
                'session': json_data.get('session'),
                'format': 'json',
                'callback': 'no'
            }
            
            response = requests.get(CALIL_BOOK_ENDPOINT, headers=headers, params=polling_params)
            response.raise_for_status()
            json_data = response.json()
            retry_count += 1
        
        # ★修正: 絵文字(✅)を削除しました
        print("[Calil] Search Completed!")
        return json_data

    except Exception as e:
        # ★修正: 絵文字(❌)を削除しました
        print(f"[ERROR] Calil Crash: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    print("Testing Calil...")
    pref = "東京都"
    libraries = search_libraries(pref, limit=3)
    pprint.pprint(libraries)