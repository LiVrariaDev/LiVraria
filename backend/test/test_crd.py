"""レファ協クライアント（backend/search/crd.py）の検証。実際の API は呼ばない。"""

import pytest
import requests

import backend.search.crd as crd

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<result_set>
	<hit_num>2</hit_num>
	<results_cd>0</results_cd>
	<result>
		<reference>
			<question>猫が出てくる小説を読みたい。</question>
			<answer>『猫のお告げは樹の下で』を提供。</answer>
			<keyword>猫</keyword>
			<keyword>小説</keyword>
			<class type="NDC" version="10">913</class>
			<ans-proc>（ねこ）で件名検索。日本の小説の棚を案内した。</ans-proc>
			<bibl><bibl-desc>猫のお告げは樹の下で</bibl-desc><bibl-isbn>9784800287908</bibl-isbn></bibl>
			<system><lib-name>どこかの図書館</lib-name></system>
		</reference>
	</result>
	<result>
		<reference>
			<question>宇宙の入門書</question>
			<keyword>宇宙</keyword>
		</reference>
	</result>
</result_set>
"""


class _Response:
	def __init__(self, text, status=200):
		self.text = text
		self.status = status

	def raise_for_status(self):
		if self.status >= 400:
			raise requests.HTTPError(f"status {self.status}")


@pytest.fixture(autouse=True)
def clean_cache():
	crd.clear_cache()
	yield
	crd.clear_cache()


def test_build_query():
	assert crd.build_query(["猫", "小説"]) == 'question all "猫 小説"'
	assert crd.build_query(['a"b', " ", "c"]) == 'question all "ab c"'


def test_parse_response_extracts_hints_only():
	hints = crd.parse_response(SAMPLE_XML)
	assert hints[0] == {
		"question": "猫が出てくる小説を読みたい。",
		"keywords": ["猫", "小説"],
		"ndc": ["913"],
		"process": "（ねこ）で件名検索。日本の小説の棚を案内した。",
	}
	# 回答の本文、参考資料、提供館名は取り出さない
	assert "answer" not in hints[0] and "bibl" not in hints[0]
	assert hints[1] == {"question": "宇宙の入門書", "keywords": ["宇宙"], "ndc": [], "process": ""}
	assert len(crd.parse_response(SAMPLE_XML, limit=1)) == 1


def test_search_sends_params_and_caches(monkeypatch):
	calls = []

	def fake_get(url, params=None, timeout=None):
		calls.append((url, params, timeout))
		return _Response(SAMPLE_XML)

	monkeypatch.setattr(crd.requests, "get", fake_get)

	first = crd.search_crd_hints(["猫", "小説"])
	second = crd.search_crd_hints(["猫", "小説"])

	assert first == second and len(first) == 2
	assert len(calls) == 1
	url, params, timeout = calls[0]
	assert url == crd.CRD_ENDPOINT
	assert timeout == 3
	assert params["type"] == "reference"
	assert params["lib-group"] == "public"
	assert params["query"] == 'question all "猫 小説"'


@pytest.mark.parametrize("error", [requests.Timeout("timeout"), requests.ConnectionError("down")])
def test_search_failure_returns_empty_and_is_not_cached(monkeypatch, error):
	calls = []

	def fake_get(*args, **kwargs):
		calls.append(1)
		raise error

	monkeypatch.setattr(crd.requests, "get", fake_get)
	assert crd.search_crd_hints(["猫"]) == []
	assert crd.search_crd_hints(["猫"]) == []
	assert len(calls) == 2


def test_search_http_error_and_broken_xml(monkeypatch):
	monkeypatch.setattr(crd.requests, "get", lambda *a, **k: _Response("", status=503))
	assert crd.search_crd_hints(["猫"]) == []
	monkeypatch.setattr(crd.requests, "get", lambda *a, **k: _Response("<not-xml"))
	assert crd.search_crd_hints(["犬"]) == []


def test_search_zero_hits(monkeypatch):
	monkeypatch.setattr(crd.requests, "get", lambda *a, **k: _Response("<result_set><hit_num>0</hit_num></result_set>"))
	assert crd.search_crd_hints(["元気が出る"]) == []


def test_search_empty_words_does_not_call(monkeypatch):
	monkeypatch.setattr(crd.requests, "get", lambda *a, **k: pytest.fail("should not be called"))
	assert crd.search_crd_hints([]) == []
	assert crd.search_crd_hints(["", " "]) == []
