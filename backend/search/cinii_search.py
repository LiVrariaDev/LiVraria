import os
import requests

from dotenv import load_dotenv
import pprint

load_dotenv()

END_POINT = "https://ci.nii.ac.jp/books/opensearch/search"
BOOK_COUNT = 4

def search_books(keywords: list[str], pages: int = 1) -> list[dict]:
	headers = {}

	# CiNii APIを使って検索
	# qでフリーワード(部分一致検索)
	# スペース区切り: AND検索 / OR検索をしたい場合、" OR "で繋ぐ
	query = ' '.join(keywords)
	params = {
		"api_key": os.getenv("CINII_API_KEY"),
		"q": query,
		"format": "json",
		"count" : BOOK_COUNT,
		"p": pages
	}

	response = requests.get(END_POINT, headers=headers, params=params)
	json_data = response.json()

	# 書籍情報の抽出
	graph_element = json_data.get('@graph', [{}])[0]
	book_data = graph_element.get('items', [])
	book_list = []

	for item in book_data:
		# 解析
		title = item.get('title')
		author = item.get('dc:creator')
		publisher = item.get('dc:publisher')
		pub_date = item.get('dc:date')
		ncid = item.get('@id')
		isbn = item.get('dcterms:hasPart', [{}])[0].get('@id', '').replace('urn:isbn:', '')
		if isbn == '':
			isbn = None
		
		# まとめる
		book_info = {
			"タイトル": title,
			"著者/編者": author,
			"出版社": publisher,
			"出版年": pub_date,
			"NCID": ncid,
			"ISBN": isbn
		}
		book_list.append(book_info)

	return book_list
# end def

if __name__ == "__main__":
	keywords = ["人工知能", "機械学習"]
	books = search_books(keywords)
	pprint.pprint(books)