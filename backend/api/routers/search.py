"""
書籍・図書館検索のエンドポイント。

外部 API（楽天・カーリル・CiNii）への同期 HTTP 呼び出しを行うため、
エンドポイントは通常の def で定義し、FastAPI のスレッドプールで実行させる
（async def で同期 I/O を呼ぶとイベントループ全体が止まる）。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend import PROMPTS_DIR
from backend.api.auth import get_current_user_id
from backend.api.llm import llm_summary
# calil.py から: 図書館検索 と 在庫確認(ポーリング機能付き)
from backend.search.calil import search_libraries, search_books as check_stock_calil
# rakuten_books.py から: ランダム検索(豪華版)
from backend.search.rakuten_books import rakuten_search_books_random as search_books_random

logger = logging.getLogger("uvicorn.error")

router = APIRouter(
	prefix="",
	tags=["search"],
	dependencies=[Depends(get_current_user_id)],
)

PROMPT_KEYWORD_SEARCH = PROMPTS_DIR / "keyword_search.md"


def extract_keywords(text: str) -> str:
	"""AI で自然文から検索キーワードを抽出する。失敗時は元の文字列を返す。"""
	if not PROMPT_KEYWORD_SEARCH.exists():
		return text
	extracted = llm_summary(str(PROMPT_KEYWORD_SEARCH), text, max_tokens=64)
	if extracted and extracted.strip():
		# 1行目だけを使う（説明文が付いてきた場合の保険）
		return extracted.strip().splitlines()[0]
	return text


@router.get("/books/search")
def search_books_endpoint(q: str, semantic: bool = False):
	"""
	キーワードで本を検索する（人気順・30件・ランダム）。
	semantic=true の場合は AI がキーワードを抽出してから検索する。
	"""
	search_query = q
	if semantic:
		search_query = extract_keywords(q)
		logger.info(f"[Semantic Search] '{q}' -> '{search_query}'")

	keywords = search_query.replace("　", " ").split()
	if not keywords:
		return []

	try:
		return search_books_random(keywords)
	except Exception as e:
		logger.error(f"[ERROR] Rakuten book search failed: {e}")
		raise HTTPException(status_code=502, detail="Book search failed")


@router.get("/search/libraries")
def search_libraries_endpoint(pref: str, limit: int = 5):
	"""指定された都道府県(pref)の図書館を探す。"""
	try:
		return search_libraries(pref, min(max(limit, 1), 50))
	except Exception as e:
		logger.error(f"[ERROR] Library search failed: {e}")
		raise HTTPException(status_code=502, detail="Library search failed")


@router.get("/search/books/availability")
def check_availability_endpoint(isbn: str, systemid: str):
	"""指定された図書館(systemid)での蔵書状況を確認する（カーリルのポーリング完了まで待つ）。"""
	logger.info(f"[Availability Check] ISBN: {isbn}, Systems: {systemid}")
	try:
		return check_stock_calil(isbn, systemid)
	except Exception as e:
		logger.error(f"[ERROR] Calil availability check failed: {e}")
		raise HTTPException(status_code=502, detail="Availability check failed")
