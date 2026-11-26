"""CiNii Books クライアントの検証（レスポンスは 2026-11 時点の実レスポンスを縮めたもの）。"""

import pytest

from backend.search import cinii

SEARCH_RESPONSE = {
	"@graph": [{
		"@type": "channel",
		"opensearch:totalResults": "1",
		"items": [{
			"title": "吾輩は猫である",
			"link": {"@id": "https://ci.nii.ac.jp/ncid/BN04568944"},
			"@id": "https://ci.nii.ac.jp/ncid/BN04568944",
			"@type": "item",
			"dc:date": "1990",
			"dc:creator": "夏目漱石作",
			"dc:publisher": ["岩波書店"],
			"prism:publicationDate": "1990",
			"dcterms:isPartOf": [{"@id": "https://ci.nii.ac.jp/ncid/BN00015783", "dc:title": "岩波文庫, 緑-10-1"}],
			"dcterms:hasPart": [{"@id": "urn:isbn:4003101014"}],
			"cinii:ownerCount": "211",
		}],
	}]
}

HOLDER_RESPONSE = {
	"@graph": [{
		"opensearch:totalResults": "3",
		"items": [
			{"title": "北海道大学 附属図書館", "@id": "https://ci.nii.ac.jp/library/FA001007"},
			{"title": "東京大学 駒場図書館", "@id": "https://ci.nii.ac.jp/library/FA001798"},
			{"title": "東京外国語大学 附属図書館", "@id": "https://ci.nii.ac.jp/library/FA001878"},
		],
	}]
}


def _library(prefcode, address, url=""):
	return {"@graph": [{
		"cinii:prefcode": prefcode,
		"v:adr": {"@type": "v:Address", "v:postal-code": "000-0000", "v:label": address},
		"dc:description": ["English name", f"URL:{url} (website)"],
	}]}


LIBRARIES = {
	"FA001007": _library("01", "札幌市北区北8条西5丁目", "https://www.lib.hokudai.ac.jp/"),
	"FA001798": _library("13", "東京都目黒区駒場3-8-1", "https://www.lib.u-tokyo.ac.jp/"),
	"FA001878": _library("13", "東京都府中市朝日町3-11-1"),
}


class _Response:
	def __init__(self, data):
		self.data = data

	def raise_for_status(self):
		pass

	def json(self):
		return self.data


@pytest.fixture
def requests_log(monkeypatch, tmp_path):
	monkeypatch.setenv("CINII_APPID", "test-appid")
	monkeypatch.setattr(cinii, "library_cache", cinii._LibraryCache(tmp_path / "libraries.json"))
	calls = []

	def fake_get(url, params, timeout):
		calls.append((url, params))
		if url == cinii.CINII_HOLDER_ENDPOINT:
			return _Response(HOLDER_RESPONSE)
		if url.startswith("https://ci.nii.ac.jp/library/"):
			return _Response(LIBRARIES[url.rsplit("/", 1)[-1].removesuffix(".json")])
		return _Response(SEARCH_RESPONSE)

	monkeypatch.setattr(cinii.requests, "get", fake_get)
	return calls


def test_search_parses_books(requests_log):
	books = cinii.search_university_books(isbn="978-4-00-310101-8")

	assert books == [{
		"ncid": "BN04568944",
		"title": "吾輩は猫である",
		"author": "夏目漱石作",
		"publisher": "岩波書店",
		"published_date": "1990",
		"series": "岩波文庫, 緑-10-1",
		"isbns": ["4003101014"],
		"owner_count": 211,
		"url": "https://ci.nii.ac.jp/ncid/BN04568944",
	}]
	_, params = requests_log[0]
	assert params == {"count": 20, "isbn": "9784003101018", "appid": "test-appid", "format": "json"}


def test_holders_without_prefecture_returns_all(requests_log):
	holders = cinii.search_holders("BN04568944")

	assert [h["fano"] for h in holders] == ["FA001007", "FA001798", "FA001878"]
	assert len(requests_log) == 1


def test_holders_filtered_by_prefecture_and_cached(requests_log):
	holders = cinii.search_holders("BN04568944", pref="東京都")

	assert [h["name"] for h in holders] == ["東京大学 駒場図書館", "東京外国語大学 附属図書館"]
	assert holders[0]["address"] == "東京都目黒区駒場3-8-1"
	assert holders[0]["website"] == "https://www.lib.u-tokyo.ac.jp/"

	requests_log.clear()
	assert len(cinii.search_holders("BN04568944", pref="13")) == 2
	assert len(requests_log) == 1  # 図書館詳細はキャッシュから


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
