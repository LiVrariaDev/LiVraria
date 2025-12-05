import backend
import os
import requests
import time
import urllib.parse

LIBRARY_END_POINT = "https://api.calil.jp/library"
BOOK_END_POINT = "https://api.calil.jp/check"


# Search libraries close to pref
def search_libraries(pref: str, limit: int = 1) -> list[dict]:
	headers = {}

	params = {
		'appkey': os.getenv("CALIL_API_KEY"),
		'pref': pref,
		'format': 'json',
		'limit': limit,
		'callback': ''
	}

	response = requests.get(LIBRARY_END_POINT, headers=headers, params=params)
	json_data = response.json()

	return json_data

# Search books by ISBN, and library systemid
def search_books(isbn: str, systemid: str) -> dict:
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

	while json_data.get('continue', False):
		param = {
			'appkey': os.getenv("CALIL_API_KEY"),
			'session': json_data.get('session'),
			'format': 'json',
		}
		time.sleep(2) # required more than 2 sec interval
		response = requests.get(BOOK_END_POINT, headers=headers, params=param)
		json_data = response.json()
	
	return json_data

if __name__ == "__main__":
	# Example usage
	pref = "静岡県"
	libraries = search_libraries(pref, limit=3)
	pprint.pprint(libraries)

	# isbn = "9784065197280"
	# systemid = "tokyo"
	# book_info = search_books(isbn, systemid)
	# print("Book Info:", book_info)
	while json_data.get('continue', False):
		param = {
			'appkey': os.getenv("CALIL_API_KEY"),
			'session': json_data.get('session'),
			'format': 'json',
		}
		time.sleep(2) # required more than 2 sec interval
		response = requests.get(BOOK_END_POINT, headers=headers, params=param)
		json_data = response.json()
	
	return json_data