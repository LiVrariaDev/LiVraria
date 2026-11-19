"""CiNii Books クライアントの検証。

レスポンスは CiNii Books OpenSearch(JSON-LD) の形式を想定した手書きのサンプル。
appid 取得後に実レスポンスで項目名を確認し、必要ならこのサンプルも合わせて更新すること。
"""

import pytest

from backend.search import cinii

SEARCH_RESPONSE = {
	"@graph": [{
		"opensearch:totalResults": "1",
		"items": [{
			"@id": "https://ci.nii.ac.jp/ncid/BA12345678",
			"title": "機械学習入門",
			"dc:creator": "山田太郎",
			"dc:publisher": ["技術評論社"],
			"dc:pubDate": "2020",
			"dcterms:hasPart": [{"@id": "urn:isbn:9784000000001"}],
			"cinii:ownerCount": "42",
		}],
	}]
}

HOLDER_RESPONSE = {
	"@graph": [{
		"items": [
			{"@id": "https://ci.nii.ac.jp/library/FA000001", "title": "東京大学 附属図書館"},
			{"@id": "https://ci.nii.ac.jp/library/FA000002", "title": "早稲田大学 図書館"},
		],
	}]
}


class _Response:
	def __init__(self, data):
		self.data = data

	def raise_for_status(self):
		pass

	def json(self):
		return self.data


@pytest.fixture
def requests_log(monkeypatch):
	monkeypatch.setenv("CINII_APPID", "test-appid")
	calls = []

	def fake_get(url, params, timeout):
		calls.append((url, params))
		return _Response(HOLDER_RESPONSE if url == cinii.CINII_HOLDER_ENDPOINT else SEARCH_RESPONSE)

	monkeypatch.setattr(cinii.requests, "get", fake_get)
	return calls


def test_search_parses_books(requests_log):
	books = cinii.search_university_books(isbn="978-4-00-000000-1")

	assert books == [{
		"ncid": "BA12345678",
		"title": "機械学習入門",
		"author": "山田太郎",
		"publisher": "技術評論社",
		"published_date": "2020",
		"isbns": ["9784000000001"],
		"owner_count": 42,
		"url": "https://ci.nii.ac.jp/ncid/BA12345678",
	}]
	url, params = requests_log[0]
	assert params["isbn"] == "9784000000001"
	assert params["appid"] == "test-appid"
	assert params["format"] == "json"


def test_holders_with_prefecture(requests_log):
	holders = cinii.search_holders("BA12345678", pref="東京都")

	assert [h["fano"] for h in holders] == ["FA000001", "FA000002"]
	assert requests_log[0][1]["pref"] == "13"


@pytest.mark.parametrize("value, expected", [("東京都", "13"), ("東京", "13"), ("北海道", "01"), ("1", "01"), ("沖縄県", "47"), ("", None), ("unknown", None)])
def test_pref_code(value, expected):
	assert cinii.pref_code(value) == expected


def test_not_configured(monkeypatch):
	monkeypatch.delenv("CINII_APPID", raising=False)
	with pytest.raises(cinii.CiNiiNotConfigured):
		cinii.search_university_books(keywords=["Python"])


def test_empty_response_is_empty_list(monkeypatch):
	monkeypatch.setenv("CINII_APPID", "x")
	monkeypatch.setattr(cinii.requests, "get", lambda *a, **k: _Response({"@graph": [{}]}))
	assert cinii.search_university_books(keywords=["存在しない本"]) == []
