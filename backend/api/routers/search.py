from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
from backend import PROMPTS_DIR
from backend.search.calil import search_libraries, search_books as search_books_calil
from backend.search.rakuten_books import rakuten_search_books as search_books_rakuten
# 循環参照を防ぐため、auth.pyやserver.pyからはインポートせず、ここでFirebase認証を行う
from firebase_admin import auth

# backend.api パッケージから chat_function をインポート
from backend.api.llm import llm_chat as chat_function

logger = logging.getLogger("uvicorn.error")

# ルーターの作成
# prefixを空にして、個別のエンドポイントでパスを完全に制御できるようにします
router = APIRouter(
    prefix="",
    tags=["search"]
)

# キーワード抽出用プロンプトのパス
PROMPT_KEYWORD_SEARCH = PROMPTS_DIR / "keyword_search.md"

# 認証ロジック (Server.pyとの循環参照を避けるためここに定義)
oauth2_scheme = HTTPBearer()

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme)) -> str:
    """
    HTTP Headerに含まれたTokenをFirebase Authで認証し
    認証に成功した場合はUser IDを返す (Server.pyと同じロジック)
    """
    try:
        id_token = credentials.credentials
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token["uid"]
    except Exception as e:
        logger.error(f"[ERROR] Firebase authentication failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")


# 書籍検索エンドポイント (/books/search)
@router.get("/books/search")
async def search_books_endpoint(
    q: str, 
    semantic: bool = False, 
    user_id: str = Depends(get_current_user_id)
):
    """
    キーワードで本を検索する。
    semantic=True の場合、AIを使って曖昧な入力からキーワードを抽出する。
    """
    search_query = q
    
    # AIによるキーワード抽出
    if semantic:
        try:
            if not PROMPT_KEYWORD_SEARCH.exists():
                logger.warning(f"[WARNING] Keyword search prompt not found: {PROMPT_KEYWORD_SEARCH}")
            else:
                extracted_keyword, _, _ = chat_function(
                    str(PROMPT_KEYWORD_SEARCH),
                    q,
                    [], 
                    ai_insight=""
                )
                # AIが変な空白を入れることがあるので除去
                extracted_keyword = extracted_keyword.strip()
                if extracted_keyword:
                    search_query = extracted_keyword
                    logger.info(f"[Semantic Search] Original: '{q}' -> Extracted: '{search_query}'")
                else:
                    logger.warning(f"[Semantic Search] Extracted keyword was empty. Using original: '{q}'")
        except Exception as e:
            logger.error(f"[ERROR] AI keyword extraction failed: {e}")
            # 失敗した場合は元のクエリで検索続行
            pass

    logger.info(f"[Book Search] Query: '{search_query}' (Original: '{q}', Semantic: {semantic})")

    # 楽天ブックスで検索を実行
    try:
        # 全角スペースを半角に変換して分割
        keywords = search_query.replace("　", " ").split()
        if not keywords:
            return []
            
        books = search_books_rakuten(keywords)
        return books
    except Exception as e:
        logger.error(f"[ERROR] Rakuten book search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 図書館検索エンドポイント (/search/libraries)
# 既存の機能があればこちらに残しておきます
@router.get("/search/libraries")
async def search_libraries_endpoint(
    pref: str, 
    limit: int = 5,
    user_id: str = Depends(get_current_user_id)
):
    """
    図書館を検索する
    """
    try:
        return search_libraries(pref, limit)
    except Exception as e:
        logger.error(f"[ERROR] Library search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))