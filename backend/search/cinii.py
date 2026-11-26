"""
CiNii Books（大学図書館の総合目録）検索クライアント。

- 書誌検索: https://ci.nii.ac.jp/books/opensearch/search
- 所蔵館検索: https://ci.nii.ac.jp/books/opensearch/holder

- 図書館詳細: https://ci.nii.ac.jp/library/{FA番号}.json

どちらも NII に申請して発行される appid（環境変数 CINII_APPID）が必要。
仕様: https://support.nii.ac.jp/ja/cib/api/b_opensearch
      https://support.nii.ac.jp/ja/cib/api/b_opensearch_hold

所蔵館検索は所蔵館を全件返し、地域で絞り込むパラメータがない。
都道府県は図書館詳細（cinii:prefcode）にしかないため、詳細を取得して判定し、
DATA_DIR/cinii_libraries.json にキャッシュする（所在地はほぼ変わらないため）。
"""

import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

import requests

from backend import DATA_DIR

logger = logging.getLogger("uvicorn.error")

CINII_SEARCH_ENDPOINT = "https://ci.nii.ac.jp/books/opensearch/search"
CINII_HOLDER_ENDPOINT = "https://ci.nii.ac.jp/books/opensearch/holder"
CINII_LIBRARY_ENDPOINT = "https://ci.nii.ac.jp/books/opensearch/library"
# 図書館検索は name が必須のため、ほぼ全館に当たる語の OR で一覧を取る
ALL_LIBRARIES_QUERY = "図書館 OR 室 OR センター OR 文庫 OR 大学 OR 研究所"
HTTP_TIMEOUT = 10
# 図書館詳細を並列取得するときの同時接続数（CiNii に負荷をかけすぎない）
DETAIL_WORKERS = 4
LIBRARY_CACHE_FILE = DATA_DIR / "cinii_libraries.json"

# JIS X 0401 の都道府県コード順
PREFECTURES = [
	"北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
	"茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
	"新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
	"静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
	"奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
	"徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
	"熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]


class CiNiiNotConfigured(RuntimeError):
	"""CINII_APPID が設定されていない。"""


def is_configured() -> bool:
	return bool(os.getenv("CINII_APPID"))


def pref_code(pref: Optional[str]) -> Optional[str]:
	"""都道府県名（"東京都" / "東京"）または2桁コードを、2桁の都道府県コードにする。"""
	if not pref:
		return None
	pref = pref.strip()
	if pref.isdigit() and 1 <= int(pref) <= 47:
		return f"{int(pref):02d}"
	for index, name in enumerate(PREFECTURES, 1):
		if pref == name or (len(pref) >= 2 and name.startswith(pref)):
			return f"{index:02d}"
	return None


def _get(endpoint: str, params: Optional[dict] = None) -> dict:
	appid = os.getenv("CINII_APPID")
	if not appid:
		raise CiNiiNotConfigured("CINII_APPID is not set")
	response = requests.get(
		endpoint,
		params={**(params or {}), "appid": appid, "format": "json"},
		timeout=HTTP_TIMEOUT,
	)
	response.raise_for_status()
	return response.json()


def _items(data: dict) -> list[dict]:
	"""OpenSearch(JSON-LD) の @graph[0].items を取り出す。"""
	graph = data.get("@graph") or [{}]
	return graph[0].get("items") or []


def _text(value: Any) -> str:
	"""文字列 / {"@value": ...} / それらのリストを1つの文字列にする。"""
	if value is None:
		return ""
	if isinstance(value, list):
		return ", ".join(t for t in (_text(v) for v in value) if t)
	if isinstance(value, dict):
		return _text(value.get("@value") or value.get("@id"))
	return str(value).strip()


def _last_segment(url: str) -> str:
	return url.rstrip("/").rsplit("/", 1)[-1] if url else ""


def _isbns(item: dict) -> list[str]:
	parts = item.get("dcterms:hasPart") or []
	if isinstance(parts, dict):
		parts = [parts]
	isbns = []
	for part in parts:
		ref = part.get("@id", "") if isinstance(part, dict) else str(part)
		if ref.startswith("urn:isbn:"):
			isbns.append(ref.removeprefix("urn:isbn:"))
	return isbns


def _int(value: Any) -> Optional[int]:
	try:
		return int(_text(value))
	except (TypeError, ValueError):
		return None


def _parse_book(item: dict) -> dict:
	url = _text(item.get("@id")) or _text(item.get("link"))
	return {
		"ncid": _last_segment(url),
		"title": _text(item.get("title")),
		"author": _text(item.get("dc:creator")),
		"publisher": _text(item.get("dc:publisher")),
		"published_date": _text(item.get("prism:publicationDate") or item.get("dc:date")),
		"series": _text([part.get("dc:title") for part in item.get("dcterms:isPartOf") or [] if isinstance(part, dict)]),
		"isbns": _isbns(item),
		"owner_count": _int(item.get("cinii:ownerCount")),
		"url": url,
	}


def _parse_holder(item: dict) -> dict:
	url = _text(item.get("@id")) or _text(item.get("link"))
	return {
		"fano": _last_segment(url),
		"name": _text(item.get("title")),
		"url": url,
	}


def search_university_books(
	keywords: Optional[list[str]] = None,
	isbn: Optional[str] = None,
	count: int = 20,
) -> list[dict]:
	"""大学図書館の総合目録から書誌を検索する（キーワードまたは ISBN）。"""
	params: dict[str, Any] = {"count": min(max(count, 1), 200)}
	if isbn:
		params["isbn"] = isbn.replace("-", "").strip()
	if keywords:
		params["q"] = " ".join(keywords)
	if len(params) == 1:
		return []
	return [_parse_book(item) for item in _items(_get(CINII_SEARCH_ENDPOINT, params))]


class _LibraryCache:
	"""図書館詳細（FA番号 → 都道府県コード・住所など）のディスクキャッシュ。"""

	def __init__(self, path):
		self.path = path
		self.lock = threading.Lock()
		self.data: Optional[dict] = None

	def _load(self) -> dict:
		if self.data is None:
			try:
				self.data = json.loads(self.path.read_text(encoding="utf-8"))
			except (FileNotFoundError, json.JSONDecodeError):
				self.data = {}
		return self.data

	def get(self, fano: str) -> Optional[dict]:
		with self.lock:
			return self._load().get(fano)

	def update(self, entries: dict) -> None:
		if not entries:
			return
		with self.lock:
			self._load().update(entries)
			tmp = self.path.with_name(self.path.name + ".tmp")
			tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
			os.replace(tmp, self.path)


library_cache = _LibraryCache(LIBRARY_CACHE_FILE)


def _parse_library_detail(data: dict) -> dict:
	entity = (data.get("@graph") or [{}])[0]
	address = entity.get("v:adr") or {}
	website = ""
	for line in entity.get("dc:description") or []:
		if isinstance(line, str) and line.startswith("URL:"):
			website = line.removeprefix("URL:").split(" ")[0]
			break
	return {
		"prefcode": _text(entity.get("cinii:prefcode")),
		"postal_code": _text(address.get("v:postal-code")),
		"address": _text(address.get("v:label")),
		"website": website,
	}


def get_library_detail(fano: str) -> Optional[dict]:
	"""図書館の所在地などを返す（キャッシュ優先）。取得に失敗した場合は None。"""
	cached = library_cache.get(fano)
	if cached is not None:
		return cached
	try:
		detail = _parse_library_detail(_get(f"https://ci.nii.ac.jp/library/{fano}.json"))
	except CiNiiNotConfigured:
		raise
	except Exception as e:
		logger.warning(f"[WARNING] CiNii library detail failed: {fano}: {e}")
		return None
	library_cache.update({fano: detail})
	return detail


def search_holders(ncid: str, pref: Optional[str] = None) -> list[dict]:
	"""
	NCID の書誌を所蔵している図書館を返す。
	pref（都道府県名 / コード）を指定すると、その都道府県の図書館だけに絞り、所在地も付ける。
	"""
	holders = [_parse_holder(item) for item in _items(_get(CINII_HOLDER_ENDPOINT, {"ncid": ncid}))]
	code = pref_code(pref)
	if not code:
		return holders

	# 未キャッシュの図書館だけ並列取得する（初回は所蔵館数ぶん通信が発生する）
	missing = [h["fano"] for h in holders if h["fano"] and library_cache.get(h["fano"]) is None]
	if missing:
		with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as pool:
			list(pool.map(get_library_detail, missing))

	result = []
	for holder in holders:
		detail = library_cache.get(holder["fano"])
		if detail and detail.get("prefcode") == code:
			result.append({**holder, **{k: v for k, v in detail.items() if k != "prefcode"}})
	return result


def prefetch_library_details(progress=None) -> int:
	"""
	全参加図書館の所在地を取得してキャッシュする（セットアップ時に1回実行）。
	これをしておくと、都道府県での所蔵館の絞り込みが初回から速くなる。
	"""
	fanos = []
	page = 1
	while True:
		data = _get(CINII_LIBRARY_ENDPOINT, {"name": ALL_LIBRARIES_QUERY, "count": 200, "p": page})
		items = _items(data)
		if not items:
			break
		fanos.extend(_parse_holder(item)["fano"] for item in items)
		page += 1

	missing = [fano for fano in dict.fromkeys(fanos) if fano and library_cache.get(fano) is None]
	done = 0
	with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as pool:
		for _ in pool.map(get_library_detail, missing):
			done += 1
			if progress and done % 100 == 0:
				progress(done, len(missing))
	return len(missing)


if __name__ == "__main__":
	# appid 取得後の動作確認用:
	#   python -m backend.search.cinii --isbn 9784003101018 --pref 東京都
	#   python -m backend.search.cinii --q 機械学習 --raw
	import argparse

	parser = argparse.ArgumentParser()
	parser.add_argument("--q")
	parser.add_argument("--isbn")
	parser.add_argument("--pref")
	parser.add_argument("--raw", action="store_true", help="パース前のレスポンスを表示（項目名の確認用）")
	parser.add_argument("--prefetch", action="store_true", help="全図書館の所在地を取得してキャッシュする（数分かかる）")
	args = parser.parse_args()

	if args.prefetch:
		count = prefetch_library_details(lambda done, total: print(f"{done}/{total}"))
		print(f"cached {count} libraries -> {LIBRARY_CACHE_FILE}")
		raise SystemExit

	if args.raw:
		params = {"count": 3, **({"q": args.q} if args.q else {}), **({"isbn": args.isbn} if args.isbn else {})}
		print(json.dumps(_get(CINII_SEARCH_ENDPOINT, params), ensure_ascii=False, indent=2))
	else:
		books = search_university_books(args.q.split() if args.q else None, args.isbn, count=3)
		print(json.dumps(books, ensure_ascii=False, indent=2))
		if books and books[0]["ncid"]:
			holders = search_holders(books[0]["ncid"], args.pref)
			print(json.dumps(holders[:10], ensure_ascii=False, indent=2))
			print(f"... {len(holders)} libraries")
