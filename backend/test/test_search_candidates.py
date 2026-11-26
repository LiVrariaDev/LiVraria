"""search_books が LLM に返す候補リスト（内容紹介・ジャンル・レビュー）と、楽天検索のレビュー取得の検証。"""

import threading
import time

import pytest
import requests
from langchain_core.messages import AIMessage, ToolMessage

import backend.api.llm as llm
import backend.search.rakuten_books as rakuten_books
from backend import PROMPT_DEFAULT


class _Clock:
	"""rakuten_books の時刻と sleep の差し替え。sleep した分だけ時刻を進め、待った秒数を記録する。"""

	def __init__(self):
		self.now = 1000.0
		self.sleeps = []

	def monotonic(self):
		return self.now

	def sleep(self, seconds):
		self.sleeps.append(round(seconds, 3))
		self.now += seconds


@pytest.fixture(autouse=True)
def clock(monkeypatch):
	"""楽天の呼び出し間隔を、実際には待たずに検証する。"""
	fake = _Clock()
	monkeypatch.setattr(rakuten_books, "_monotonic", fake.monotonic)
	monkeypatch.setattr(rakuten_books, "_sleep", fake.sleep)
	rakuten_books.reset_rate_limit()
	yield fake
	rakuten_books.reset_rate_limit()


# 1. rakuten_search_books がレビュー平均と件数を返す

class _FakeResponse:
	def __init__(self, data):
		self._data = data

	def raise_for_status(self):
		pass

	def json(self):
		return self._data


def test_rakuten_search_books_returns_review(monkeypatch):
	item = {
		"title": "テスト本",
		"author": "著者A",
		"booksGenreId": "001004008",
		"itemCaption": "<b>紹介</b>",
		"reviewAverage": "4.25",
		"reviewCount": 12,
	}
	monkeypatch.setattr(rakuten_books.requests, "get", lambda *a, **k: _FakeResponse({"Items": [item, {"title": "レビューなし"}]}))

	books = rakuten_books.rakuten_search_books(["テスト"])

	assert books[0]["reviewAverage"] == "4.25"
	assert books[0]["reviewCount"] == 12
	assert books[0]["genre"] == "001004008"
	assert books[1]["reviewAverage"] is None
	assert books[1]["reviewCount"] == 0


# 2. genre_path

def test_genre_path():
	assert rakuten_books.genre_path("001001001") == "本 > 漫画（コミック） > 少年"
	# 4階層目のIDは一覧にないので、上位のジャンルを返す
	assert rakuten_books.genre_path("001001001007") == "本 > 漫画（コミック） > 少年"
	# 複数のIDは先頭を使う
	assert rakuten_books.genre_path("001001002/001001001") == "本 > 漫画（コミック） > 少女"
	assert rakuten_books.genre_path("999") == ""
	assert rakuten_books.genre_path("") == ""
	assert rakuten_books.genre_path(None) == ""


# 3. 内容紹介とレビューの整形

def test_clean_caption_strips_tags_and_truncates():
	assert llm.clean_caption("<p>一行目<br/>二行目</p>&amp;続き") == "一行目 二行目 &続き"
	assert llm.clean_caption(None) == ""
	long_text = "あ" * 200
	result = llm.clean_caption(long_text)
	assert result == "あ" * 150 + "…"
	assert llm.clean_caption("あ" * 150) == "あ" * 150


def test_format_review():
	assert llm.format_review("4.26", 12) == "4.3（12件）"
	assert llm.format_review(3.0, "5") == "3.0（5件）"
	assert llm.format_review(0, 0) == "なし"
	assert llm.format_review(None, None) == "なし"
	assert llm.format_review("abc", 3) == "なし"


def test_format_book_candidate():
	book = {
		"title": "テスト本",
		"authors": ["著者A"],
		"genre": "001001001",
		"itemCaption": "<b>面白い</b>話",
		"reviewAverage": "4.0",
		"reviewCount": 3,
	}
	assert llm.format_book_candidate(5, book) == (
		"5. 『テスト本』 - 著者A\n"
		"   ジャンル: 本 > 漫画（コミック） > 少年\n"
		"   レビュー: 4.0（3件）\n"
		"   内容: 面白い 話"
	)
	# 情報がない本は、ジャンルと内容の行を省き、レビューは「なし」
	assert llm.format_book_candidate(1, {"title": "X", "authors": []}) == (
		"1. 『X』 - 不明\n"
		"   レビュー: なし"
	)


# 4. llm_chat 内の search_books が候補リストに情報を載せる

class _SearchThenRecommendLLM:
	"""search_books → recommend_books → 最終回答の順に応答する偽の LLM。"""

	def __init__(self):
		self.tool_results = []

	def bind_tools(self, tools):
		return self

	def invoke(self, messages):
		last = messages[-1]
		if isinstance(last, ToolMessage):
			self.tool_results.append(last)
			if last.name == "search_books":
				return AIMessage(content="", tool_calls=[{
					"name": "recommend_books",
					"args": {"selections": [{"number": 1, "reason": "評価が高い"}]},
					"id": "call-2",
				}])
			return AIMessage(content="この本がおすすめです。")
		return AIMessage(content="", tool_calls=[{
			"name": "search_books",
			"args": {"keywords": ["漫画"], "count": 10},
			"id": "call-1",
		}])


def test_llm_chat_search_candidates_include_details(monkeypatch):
	fake = _SearchThenRecommendLLM()
	monkeypatch.setattr(llm, "get_llm", lambda **kwargs: fake)
	books = [
		{
			"title": "本その1",
			"authors": ["著者A"],
			"genre": "001001001",
			"itemCaption": "<p>" + "い" * 300 + "</p>",
			"reviewAverage": "4.50",
			"reviewCount": 20,
		},
		{"title": "本その2", "authors": ["著者B"], "genre": None, "itemCaption": "", "reviewAverage": None, "reviewCount": 0},
	]
	monkeypatch.setattr(llm, "rakuten_search_books", lambda keywords, count=10, orflag=0: books)

	text, _history, recommended, _expression = llm.llm_chat(str(PROMPT_DEFAULT), "漫画を探して", [])

	search_result = next(m for m in fake.tool_results if m.name == "search_books").content
	assert "1. 『本その1』 - 著者A" in search_result
	assert "ジャンル: 本 > 漫画（コミック） > 少年" in search_result
	assert "レビュー: 4.5（20件）" in search_result
	assert "内容: " + "い" * 150 + "…" in search_result
	assert "<p>" not in search_result
	assert "2. 『本その2』 - 著者B\n   レビュー: なし" in search_result
	assert text == "この本がおすすめです。"
	assert recommended[0]["title"] == "本その1"
	assert recommended[0]["reviewCount"] == 20


# 5. 楽天 API の呼び出し間隔と 429 のやり直し

class _HttpResponse:
	def __init__(self, status_code=200, headers=None, data=None):
		self.status_code = status_code
		self.headers = headers or {}
		self._data = data or {"Items": []}

	def raise_for_status(self):
		if self.status_code >= 400:
			raise requests.HTTPError(f"status {self.status_code}")

	def json(self):
		return self._data


def test_rakuten_calls_are_spaced_by_one_second(monkeypatch, clock):
	calls = []

	def fake_get(url, headers=None, params=None, timeout=None):
		calls.append(clock.now)
		clock.now += 0.3  # 通信に 0.3 秒かかる
		return _HttpResponse()

	monkeypatch.setattr(rakuten_books.requests, "get", fake_get)
	rakuten_books.rakuten_search_books(["a"])
	rakuten_books.rakuten_search_books(["b"])
	clock.now += 5  # 十分に時間が空けば待たない
	rakuten_books.rakuten_search_books(["c"])

	assert clock.sleeps == [1.0]  # 前の呼び出しの終わりから1秒
	assert calls[1] - (calls[0] + 0.3) == pytest.approx(1.0)
	assert len(calls) == 3


def test_rakuten_retries_once_after_429(monkeypatch, clock):
	responses = [_HttpResponse(429), _HttpResponse(200, data={"Items": [{"title": "本"}]})]
	monkeypatch.setattr(rakuten_books.requests, "get", lambda *a, **k: responses.pop(0))

	books = rakuten_books.rakuten_search_books(["猫"])

	assert [b["title"] for b in books] == ["本"]
	assert clock.sleeps == [rakuten_books.RAKUTEN_RETRY_WAIT]  # 429 のあとの待ちだけ（間隔の待ちはそれに含まれる）


def test_rakuten_retry_wait_uses_retry_after(monkeypatch, clock):
	responses = [_HttpResponse(429, headers={"Retry-After": "3"}), _HttpResponse(200)]
	monkeypatch.setattr(rakuten_books.requests, "get", lambda *a, **k: responses.pop(0))
	rakuten_books.rakuten_search_books(["猫"])
	assert clock.sleeps == [3.0]

	responses[:] = [_HttpResponse(429, headers={"Retry-After": "600"}), _HttpResponse(200)]
	clock.now += 10
	rakuten_books.rakuten_search_books(["猫"])
	assert clock.sleeps[-1] == rakuten_books.RAKUTEN_RETRY_WAIT_MAX  # 長すぎる指定は上限で切る


def test_rakuten_gives_up_after_second_429(monkeypatch, clock):
	calls = []

	def fake_get(*args, **kwargs):
		calls.append(1)
		return _HttpResponse(429)

	monkeypatch.setattr(rakuten_books.requests, "get", fake_get)
	with pytest.raises(requests.HTTPError):
		rakuten_books.rakuten_search_books(["猫"])
	assert len(calls) == 2  # やり直しは1回だけ


def test_rakuten_lock_serializes_threads(monkeypatch):
	"""複数のスレッドから呼んでも、楽天への通信は同時に1本だけ。"""
	monkeypatch.setattr(rakuten_books, "_sleep", lambda seconds: None)
	active = []
	peak = []
	lock = threading.Lock()

	def fake_get(*args, **kwargs):
		with lock:
			active.append(1)
			peak.append(len(active))
		time.sleep(0.02)
		with lock:
			active.pop()
		return _HttpResponse()

	monkeypatch.setattr(rakuten_books.requests, "get", fake_get)
	threads = [threading.Thread(target=rakuten_books.rakuten_search_books, args=([str(i)],)) for i in range(5)]
	for t in threads:
		t.start()
	for t in threads:
		t.join()
	assert len(peak) == 5 and max(peak) == 1
