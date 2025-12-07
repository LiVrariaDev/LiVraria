from backend import PROJECT_ROOT
import os
import requests
import json
from pathlib import Path

import pprint

RAKUTEN_BOOKTOTAL_ENDPOINT = "https://app.rakuten.co.jp/services/api/BooksTotal/Search/20170404"
RAKUTEN_BOOK_ENDPOINT = "https://app.rakuten.co.jp/services/api/BooksBook/Search/20170404"

RAKUTEN_BOOK_GENRE_FLATLIST = Path(PROJECT_ROOT, "backend", "search", "rakuten_books_genre", "rakuten_genres_flat.json")
RAKUTEN_BOOK_GENRE_TREELIST = Path(PROJECT_ROOT, "backend", "search", "rakuten_books_genre", "rakuten_genres_hierarchy.json")

def genreid_to_genre(genre_id: str) -> str:
    with open(RAKUTEN_BOOK_GENRE_FLATLIST, "r") as f:
        genre_list = json.load(f)
        for genre in genre_list:
            if genre["booksGenreId"] == genre_id:
                return genre["fullPath"]
        return ""

def rakuten_search_books(keywords: list[str], count: int = 4, genre_id: str = "001") -> list[dict]:
    headers = {}

    params = {
        "applicationId": os.getenv("RAKUTEN_APP_ID"),
        "booksGenreId": genre_id,
        "format": "json",
        "formatVersion": "2",
        "keyword": " ".join(keywords),
        "hits": min(count, 30),
        "page": 1,
    }

    response = requests.get(RAKUTEN_BOOKTOTAL_ENDPOINT, headers=headers, params=params)
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
        genre = item.get("booksGenreId")

        book_info = {
            "title": title,
            "authors": authors,
            "publisher": publisher,
            "published_date": published_date,
            "isbn": isbn,
            "genre": genre
        }
        book_list.append(book_info)

    return book_list

def rakuten_search_info(isbn: str) -> dict:
    headers = {}
    params = {
        "applicationId": os.getenv("RAKUTEN_APP_ID"),
        "format": "json",
        "formatVersion": "2",
        "isbn": isbn,
        "hits": 1,
        "page": 1,
    }

    response = requests.get(RAKUTEN_BOOK_ENDPOINT, headers=headers, params=params)
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
        "category": category,
        "review": review,
        "review_count": review_count,
        "thumbnail_url": thumbnail_url,
        "preview_url": preview_url
    }

    return info_data

if __name__ == "__main__":
    books = rakuten_search_books(["鬼滅の刃"])
    pprint.pprint(books)
    