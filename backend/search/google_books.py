import os
import requests

import pprint

GOOGLE_BOOKS_ENDPOINT = "https://www.googleapis.com/books/v1/volumes"

def google_search_books(keywords: list[str], count: int = 4) -> list[dict]:
    headers = {}
    params = {
        "q": '+'.join(keywords),
        "maxResults": count
    }

    reponse = requests.get(GOOGLE_BOOKS_ENDPOINT, headers=headers, params=params)
    json_data = reponse.json().get("items", [{}])
    
    book_list = []
    for item in json_data:
        title = item.get("volumeInfo", {}).get("title")
        authors = item.get("volumeInfo", {}).get("authors", [{}])
        publisher = item.get("volumeInfo", {}).get("publisher")
        published_date = item.get("volumeInfo", {}).get("publishedDate")
        isbn = item.get("volumeInfo", {}).get("industryIdentifiers", [{}])[0].get("identifier")

        book_info = {
            "title": title,
            "authors": authors,
            "publisher": publisher,
            "published_date": published_date,
            "isbn": isbn
        }
        book_list.append(book_info)

    return book_list

def google_search_info(isbn: str) -> dict:
    headers = {}
    params = {
        "q": f"isbn:{isbn}",
        "maxResults": 1
    }

    response = requests.get(GOOGLE_BOOKS_ENDPOINT, headers=headers, params=params)
    json_data = response.json().get("items", [{}])[0].get("volumeInfo", {})
    category = json_data.get("categories", [{}]) # volumeInfo.categories[] : list
    review = json_data.get("averageRating") #volumeInfo.averageRating : double
    review_count = json_data.get("ratingsCount") #volumeInfo.ratingsCount : int
    thumbnail_url = json_data.get("imageLinks", {}).get("thumbnail") #volumeInfo.imageLinks.thumbnail : string
    preview_url = json_data.get("previewLink") #volumeInfo.previewLink : string
    
    info_data = {
        "category": category,
        "review": review,
        "review_count": review_count,
        "thumbnail_url": thumbnail_url,
        "preview_url": preview_url
    }

    return info_data

if __name__ == "__main__":
    keywords = ["鬼滅の刃"]
    books = google_search_books(keywords)
    pprint.pprint(books)

