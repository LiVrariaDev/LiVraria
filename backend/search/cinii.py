"""
CiNii Books（大学図書館の総合目録）検索クライアント。

- 書誌検索: https://ci.nii.ac.jp/books/opensearch/search
- 所蔵館検索: https://ci.nii.ac.jp/books/opensearch/holder

どちらも NII に申請して発行される appid（環境変数 CINII_APPID）が必要。

注意: レスポンス項目名は公式ドキュメントで最終確認していない（開発時に参照できなかった）。
appid 取得後に `python -m backend.search.cinii --isbn 9784...` で実レスポンスを確認し、
_parse_book / _parse_holder の項目名を合わせること。
"""

import os
from typing import Any, Optional

import requests

CINII_SEARCH_ENDPOINT = "https://ci.nii.ac.jp/books/opensearch/search"
CINII_HOLDER_ENDPOINT = "https://ci.nii.ac.jp/books/opensearch/holder"
HTTP_TIMEOUT = 10

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


def _get(endpoint: str, params: dict) -> dict:
	appid = os.getenv("CINII_APPID")
	if not appid:
		raise CiNiiNotConfigured("CINII_APPID is not set")
	response = requests.get(
		endpoint,
		params={**params, "appid": appid, "format": "json"},
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
		"published_date": _text(item.get("dc:pubDate") or item.get("prism:publicationDate") or item.get("dc:date")),
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


def search_holders(ncid: str, pref: Optional[str] = None, count: int = 50) -> list[dict]:
	"""NCID の書誌を所蔵している図書館を返す。pref で都道府県を絞り込む。"""
	params: dict[str, Any] = {"ncid": ncid, "count": min(max(count, 1), 200)}
	code = pref_code(pref)
	if code:
		params["pref"] = code
	return [_parse_holder(item) for item in _items(_get(CINII_HOLDER_ENDPOINT, params))]


if __name__ == "__main__":
	# appid 取得後の動作確認用:
	#   python -m backend.search.cinii --isbn 9784003101018 --pref 東京都
	#   python -m backend.search.cinii --q 機械学習 --raw
	import argparse
	import json

	import backend  # noqa: F401  .env を読み込む

	parser = argparse.ArgumentParser()
	parser.add_argument("--q")
	parser.add_argument("--isbn")
	parser.add_argument("--pref")
	parser.add_argument("--raw", action="store_true", help="パース前のレスポンスを表示（項目名の確認用）")
	args = parser.parse_args()

	if args.raw:
		params = {"count": 3, **({"q": args.q} if args.q else {}), **({"isbn": args.isbn} if args.isbn else {})}
		print(json.dumps(_get(CINII_SEARCH_ENDPOINT, params), ensure_ascii=False, indent=2))
	else:
		books = search_university_books(args.q.split() if args.q else None, args.isbn, count=3)
		print(json.dumps(books, ensure_ascii=False, indent=2))
		if books and books[0]["ncid"]:
			holders = search_holders(books[0]["ncid"], args.pref, count=10)
			print(json.dumps(holders, ensure_ascii=False, indent=2))
