from backend import PROJECT_ROOT
import logging
import os
import requests
import random
import json
import threading
import time
from pathlib import Path

import pprint

logger = logging.getLogger("uvicorn.error")

# 外部APIが応答しない場合に端末を待たせ続けないためのタイムアウト（秒）
HTTP_TIMEOUT = 10

# 楽天 API の呼び出し間隔の制御（プロセス全体で共通）
RAKUTEN_MIN_INTERVAL = 1.0   # 前の呼び出しから空ける秒数
RAKUTEN_RETRY_WAIT = 2.0     # 429 のときにやり直すまで待つ秒数（Retry-After があればそれを使う）
RAKUTEN_RETRY_WAIT_MAX = 5.0
_rakuten_lock = threading.Lock()
_rakuten_last_call = None    # 前の呼び出しが終わった時刻（time.monotonic）
# テストで差し替えるために参照を持つ
_sleep = time.sleep
_monotonic = time.monotonic


def _retry_wait(response) -> float:
    try:
        value = float((getattr(response, "headers", None) or {}).get("Retry-After", ""))
    except (TypeError, ValueError):
        return RAKUTEN_RETRY_WAIT
    return min(max(value, RAKUTEN_MIN_INTERVAL), RAKUTEN_RETRY_WAIT_MAX)


def rakuten_get(url: str, headers: dict, params: dict):
    """楽天 API を呼ぶ。プロセス全体で1本ずつにし、前の呼び出しから RAKUTEN_MIN_INTERVAL 秒以上空ける。

    429 が返ったら少し待って1回だけやり直す。2回目も 429 ならそのレスポンスを返す
    （呼び出し側の raise_for_status で例外になる）。
    """
    global _rakuten_last_call
    with _rakuten_lock:
        for attempt in range(2):
            if _rakuten_last_call is not None:
                wait = _rakuten_last_call + RAKUTEN_MIN_INTERVAL - _monotonic()
                if wait > 0:
                    _sleep(wait)
            try:
                response = requests.get(url, headers=headers, params=params, timeout=HTTP_TIMEOUT)
            finally:
                _rakuten_last_call = _monotonic()
            if getattr(response, "status_code", None) == 429 and attempt == 0:
                wait = _retry_wait(response)
                logger.warning("[WARNING] Rakuten API returned 429, retrying in %.1fs", wait)
                _sleep(wait)
                continue
            return response


def reset_rate_limit() -> None:
    """テスト用: 前の呼び出しの時刻を忘れる。"""
    global _rakuten_last_call
    with _rakuten_lock:
        _rakuten_last_call = None

RAKUTEN_BOOKTOTAL_ENDPOINT = "https://openapi.rakuten.co.jp/services/api/BooksTotal/Search/20170404"
RAKUTEN_BOOK_ENDPOINT = "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404"

RAKUTEN_BOOK_GENRE_FLATLIST = Path(PROJECT_ROOT, "backend", "search", "rakuten_books_genre", "rakuten_genres_flat.json")
RAKUTEN_BOOK_GENRE_TREELIST = Path(PROJECT_ROOT, "backend", "search", "rakuten_books_genre", "rakuten_genres_hierarchy.json")

def genreid_to_genre(genre_id: str) -> str:
    genre_id = genre_id[0:-3]

    with open(RAKUTEN_BOOK_GENRE_FLATLIST, "r") as f:
        genre_list = json.load(f)
        for genre in genre_list:
            if genre["booksGenreId"] == genre_id:
                return genre["fullPath"]
        return ""

_genre_paths: dict[str, str] | None = None

def genre_path(genre_id: str | None) -> str:
    """楽天のジャンルID（"001004008001/001017005" のように複数のこともある）を「本 > 小説・エッセイ > ...」の形に変換する。

    ジャンル一覧は3階層目までしかないため、見つからなければ末尾3桁ずつ削って上位のジャンルを探す。
    複数のIDがあるときは先頭を使う。見つからなければ空文字を返す。
    """
    global _genre_paths
    if not genre_id:
        return ""
    if _genre_paths is None:
        try:
            with open(RAKUTEN_BOOK_GENRE_FLATLIST, "r", encoding="utf-8") as f:
                _genre_paths = {g["booksGenreId"]: g["fullPath"] for g in json.load(f)}
        except (OSError, ValueError, KeyError):
            _genre_paths = {}
    first_id = str(genre_id).split("/")[0].strip()
    while first_id:
        if first_id in _genre_paths:
            return _genre_paths[first_id]
        first_id = first_id[:-3]
    return ""

def rakuten_search_books(keywords: list[str], count: int = 10, genre_id: str = "001", orflag: int = 0) -> list[dict]:
    headers = {
        "accessKey": os.getenv("RAKUTEN_ACCESS_KEY"),
    }

    params = {
        "applicationId": os.getenv("RAKUTEN_APP_ID"),
        "booksGenreId": genre_id,
        "format": "json",
        "formatVersion": "2",
        "keyword": " ".join(keywords),
        "hits": min(count, 30),
        "orFlag": orflag,
        "page": 1,
    }

    response = rakuten_get(RAKUTEN_BOOKTOTAL_ENDPOINT, headers, params)
    response.raise_for_status()
    json_data = response.json().get("Items", [])
    
    book_list = []
    for item in json_data:
        # 楽天Books APIのレスポンス構造に合わせる
        title = item.get("title")
        author = item.get("author")  # 楽天は単一のauthor文字列
        authors = [author] if author else []  # リスト形式に変換
        publisher = item.get("publisherName")
        published_date = item.get("salesDate")  # YYYY-MM-DD形式
        isbn = item.get("isbn")
        image_url = item.get("largeImageUrl") # 200x200商品画像
        item_url = item.get("itemUrl")
        genre = item.get("booksGenreId")
        item_caption = item.get("itemCaption", "")
        item_price = item.get("itemPrice", 0)
        review_average = item.get("reviewAverage")  # レビュー平均（"4.25" のような文字列のこともある）
        review_count = item.get("reviewCount", 0)  # レビュー件数

        book_info = {
            "title": title,
            "authors": authors,
            "publisher": publisher,
            "published_date": published_date,
            "isbn": isbn,
            "image_url": image_url,
            "item_url": item_url,
            "genre": genre,
            "itemCaption": item_caption,
            "itemPrice": item_price,
            "reviewAverage": review_average,
            "reviewCount": review_count,
        }
        book_list.append(book_info)

    return book_list

def rakuten_search_info(isbn: str) -> dict:
    headers = {
        "accessKey": os.getenv("RAKUTEN_ACCESS_KEY")
    }
    params = {
        "applicationId": os.getenv("RAKUTEN_APP_ID"),
        "format": "json",
        "formatVersion": "2",
        "isbn": isbn,
        "hits": 1,
        "page": 1,
    }

    response = rakuten_get(RAKUTEN_BOOK_ENDPOINT, headers, params)
    response.raise_for_status()
    items = response.json().get("Items", [])
    
    if not items:
        return {}
    
    item = items[0]
    
    # 楽天Books APIのレスポンス構造に合わせる
    category = item.get("booksGenreId")  # ジャンルID
    review = item.get("reviewAverage")  # レビュー平均
    review_count = item.get("reviewCount")  # レビュー数
    thumbnail_url = item.get("largeImageUrl")  # 画像URL
    preview_url = item.get("itemUrl")  # 商品ページURL
    
    info_data = {
        "category": genreid_to_genre(category),
        "review": review,
        "review_count": review_count,
        "thumbnail_url": thumbnail_url,
        "preview_url": preview_url
    }

    return info_data

def rakuten_search_books_random(keywords: list[str], count: int = 30) -> list[dict]:
    """
    【蔵書検索用】
    - 人気順(sales)で最大30件取得
    - 結果をシャッフルして返す
    - Vueで表示しやすい形式（mediumImageUrlなど）に整形済み
    """

    headers = {
        "accessKey": os.getenv("RAKUTEN_ACCESS_KEY")
    }
    keyword_str = " ".join(keywords)
    
    params = {
        "applicationId": os.getenv("RAKUTEN_APP_ID"),
        "title": keyword_str,    # タイトルや著者名
        "format": "json",
        "formatVersion": "2",
        "hits": 30,              # 最大30件
        "sort": "sales",         # 売上順
        "outOfStockFlag": 1,     # 品切れも含める
    }

    try:
        response = rakuten_get(RAKUTEN_BOOK_ENDPOINT, headers, params)
        response.raise_for_status()
        json_data = response.json().get("Items", [])
        
        book_list = []
        for item in json_data:
            # 必要な情報を安全に取り出す
            # Vue側で表示しやすいキー名に変換しておく
            medium_image_url = item.get("mediumImageUrl", "").replace("?_ex=120x120", "?_ex=200x200")
            
            book_info = {
                "title": item.get("title", ""),
                "author": item.get("author", ""), # 文字列のまま
                "publisher": item.get("publisherName", ""),
                "published_date": item.get("salesDate", ""),
                "isbn": item.get("isbn", ""),
                "price": item.get("itemPrice", 0),
                "description": item.get("itemCaption", ""),
                "url": item.get("itemUrl", ""),
                "mediumImageUrl": medium_image_url, 
                "largeImageUrl": item.get("largeImageUrl", "")
            }
            book_list.append(book_info)

        # ランダムにシャッフル！
        random.shuffle(book_list)

        return book_list

    except Exception as e:
        print(f"[ERROR] Rakuten random search failed: {e}")
        return []

if __name__ == "__main__":
    books = rakuten_search_books(["Rust", "プログラミング"])
    pprint.pprint(books)