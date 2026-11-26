"""レファレンス協同データベース（レファ協）API のクライアント。

会話グラフ v2 で、似た相談の事例から検索の手がかり（キーワード、NDC、回答プロセスの要点）を
取り出すために使う。事例の文章や事例に出てくる本は、利用者向けにそのまま見せない（内部の参考のみ）。

- API 仕様: https://crd.ndl.go.jp/jp/help/general/help_07_api_2.html
- 利用条件: 営利を目的としない場合に限り利用できる。API を使っていることをアプリ内に明示する。
"""

import logging
import threading
import xml.etree.ElementTree as ET
from typing import Optional

import requests

logger = logging.getLogger("uvicorn.error")

CRD_ENDPOINT = "https://crd.ndl.go.jp/api/refsearch"
CRD_TIMEOUT = 3  # 秒。会話の応答を待たせないため短くする
CRD_RESULTS_NUM = 5
CRD_PROCESS_MAX_CHARS = 150
CRD_QUESTION_MAX_CHARS = 80
CRD_CACHE_LIMIT = 256

_cache: dict[str, list[dict]] = {}
_cache_lock = threading.Lock()


def _text(element: Optional[ET.Element]) -> str:
	return (element.text or "").strip() if element is not None else ""


def _truncate(text: str, limit: int) -> str:
	text = " ".join(text.split())
	return text if len(text) <= limit else text[:limit].rstrip() + "…"


def build_query(words: list[str]) -> str:
	"""質問文にすべての語を含む事例を探す CQL を作る。語の中の " は取り除く。"""
	cleaned = [w.replace('"', "").strip() for w in words]
	cleaned = [w for w in cleaned if w]
	return f'question all "{" ".join(cleaned)}"'


def parse_response(xml_text: str, limit: int = CRD_RESULTS_NUM) -> list[dict]:
	"""API の XML から、事例ごとの手がかり {question, keywords, ndc, process} を取り出す。"""
	root = ET.fromstring(xml_text)
	hints = []
	for reference in root.iter("reference"):
		keywords = [_text(k) for k in reference.findall("keyword") if _text(k)]
		ndc = [_text(c) for c in reference.findall("class") if c.get("type") == "NDC" and _text(c)]
		hints.append({
			"question": _truncate(_text(reference.find("question")), CRD_QUESTION_MAX_CHARS),
			"keywords": keywords,
			"ndc": ndc,
			"process": _truncate(_text(reference.find("ans-proc")), CRD_PROCESS_MAX_CHARS),
		})
		if len(hints) >= limit:
			break
	return hints


def search_crd_hints(words: list[str], limit: int = CRD_RESULTS_NUM) -> list[dict]:
	"""語のリストで公共図書館の事例を検索し、手がかりのリストを返す。

	0件・失敗・タイムアウトのときは空のリストを返す（呼び出し側はそのまま先へ進めばよい）。
	成功した結果は同じ検索語ごとにメモリにキャッシュする（失敗はキャッシュしない）。
	"""
	words = [w.strip() for w in words if w and w.strip()]
	if not words:
		return []
	key = " ".join(words)
	with _cache_lock:
		if key in _cache:
			return list(_cache[key])

	params = {
		"type": "reference",
		"query": build_query(words),
		"lib-group": "public",
		"results_num": limit,
		"sort": "fit",
	}
	try:
		response = requests.get(CRD_ENDPOINT, params=params, timeout=CRD_TIMEOUT)
		response.raise_for_status()
		hints = parse_response(response.text, limit)
	except Exception as exc:
		logger.warning("[WARNING] CRD search failed (%s): %s", type(exc).__name__, exc)
		return []

	with _cache_lock:
		if len(_cache) >= CRD_CACHE_LIMIT:
			_cache.pop(next(iter(_cache)))
		_cache[key] = hints
	return list(hints)


def clear_cache() -> None:
	"""テスト用。"""
	with _cache_lock:
		_cache.clear()
