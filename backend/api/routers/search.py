from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
from backend import PROMPTS_DIR
import requests

# ----------------------------------------------------------------
# ★必要な関数をインポート
# ----------------------------------------------------------------
# calil.py から: 図書館検索 と 在庫確認(ポーリング機能付き)
from backend.search.calil import search_libraries, search_books as check_stock_calil

# rakuten_books.py から: ランダム検索(豪華版) を使う
from backend.search.rakuten_books import rakuten_search_books_random as search_books_random

# Firebase認証 & AIチャット
from firebase_admin import auth
from backend.api.llm import llm_chat as chat_function

logger = logging.getLogger("uvicorn.error")

router = APIRouter(
    prefix="",
    tags=["search"]
)

PROMPT_KEYWORD_SEARCH = PROMPTS_DIR / "keyword_search.md"
oauth2_scheme = HTTPBearer()

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme)) -> str:
    """Firebase Authによる認証"""
    try:
        id_token = credentials.credentials
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token["uid"]
    except Exception as e:
        logger.error(f"[ERROR] Firebase authentication failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")


# ----------------------------------------------------------------
# 1. 書籍検索エンドポイント (豪華版・ランダム表示)
# ----------------------------------------------------------------
@router.get("/books/search")
async def search_books_endpoint(
    q: str, 
    semantic: bool = False, 
    user_id: str = Depends(get_current_user_id)
):
    """
    キーワードで本を検索する。
    「豪華版（人気順・30件・ランダム）」を使用する。
    """
    search_query = q
    
    # AIによるキーワード抽出 (semantic=Trueの場合)
    if semantic:
        try:
            if PROMPT_KEYWORD_SEARCH.exists():
                extracted_keyword, _, _ = chat_function(
                    str(PROMPT_KEYWORD_SEARCH), q, [], ai_insight=""
                )
                extracted_keyword = extracted_keyword.strip()
                if extracted_keyword:
                    search_query = extracted_keyword
                    logger.info(f"[Semantic Search] '{q}' -> '{search_query}'")
        except Exception as e:
            logger.error(f"[ERROR] AI keyword extraction failed: {e}")

    logger.info(f"[Book Search] Query: '{search_query}'")

    try:
        # 全角スペース対応
        keywords = search_query.replace("　", " ").split()
        if not keywords:
            return []
            
        # ★ここで「豪華版（ランダム）」関数を呼び出す
        books = search_books_random(keywords)
        return books
        
    except Exception as e:
        logger.error(f"[ERROR] Rakuten book search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------------
# 2. 図書館検索エンドポイント
# ----------------------------------------------------------------
@router.get("/search/libraries")
async def search_libraries_endpoint(
    pref: str,  # ★フロントから送られてくる住所をそのまま使う（余計な加工なし！）
    limit: int = 5,
    user_id: str = Depends(get_current_user_id)
):
    """
    指定された都道府県(pref)の図書館を探す。
    ユーザーの住所判定はフロントエンド側で行われているため、ここでは受け取ったprefをそのまま使う。
    """
    try:
        return search_libraries(pref, limit)
    except Exception as e:
        logger.error(f"[ERROR] Library search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------------
# 3. 在庫確認エンドポイント (同期関数・calil使用)
# ----------------------------------------------------------------
@router.get("/search/books/availability")
def check_availability_endpoint(
    isbn: str, 
    systemid: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    指定された図書館(systemid)での蔵書状況を確認する。
    calil.py のポーリング機能(time.sleep)を利用するため、async def ではなく def で定義する。
    """
    logger.info(f"[Availability Check] ISBN: {isbn}, Systems: {systemid}")
    
    try:
        # ★calil.py の関数を使って、検索完了まで待機してから結果を返す
        data = check_stock_calil(isbn, systemid)
        return data
        
    except Exception as e:
        logger.error(f"[ERROR] Calil availability check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))