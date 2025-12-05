import backend
import os
import requests
import urllib.parse

LIBRARY_END_POINT = "https://api.calil.jp/library"
BOOK_END_POINT = "https://api.calil.jp/check"


# Search libraries close to geocode
def search_libraries(geocode: str, limit: int = 1) -> list[dict]:
    headers = {}

    params = {
        'appkey': os.getenv("CALIL_API_KEY"),
        'geocode': geocode,
        'format': 'json',
        'limit': limit,
        'callback': ''
    }

    response = requests.get(BOOK_END_POINT, headers=headers, params=params)
    json_data = response.json()

    library_list = []

    return library_list

# Search books by ISBN, and library systemid
# Polling i
def search_books(isbn: list[str], systemid: str) -> dict:
    headers = {}

    params = {
        'appkey': os.getenv("CALIL_API_KEY"),
        'isbn': isbn,
        'systemid': systemid,
        'format': 'json',
        'callback': 'no'
    }

    response = requests.get(BOOK_END_POINT, headers=headers, params=params)
    json_data = response.json()

    if isbn in json_data:
        return json_data[isbn]
    else:
        return {}