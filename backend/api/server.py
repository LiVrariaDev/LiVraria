# FastAPI Server for LiVraria

import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
import uvicorn
from pathlib import Path

from .models import ChatRequest, ChatResponse, Personal
from .datastore import DataStore
from .gemini import gemini_chat

# ロガー設定
logger = logging.getLogger("uvicorn.error")

# FastAPIアプリケーション
app = FastAPI()

# ファイルパス
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


class Server:
    """
    Server クラス: FastAPI ルートを束ね、DataStore を用いてセッション管理を行う
    """
    def __init__(self, app: FastAPI, data_store: DataStore):
        self.app = app
        self.data_store = data_store
        self._register_routes()

    def _register_routes(self):
        @self.app.get("/")
        async def read_root(name: str = "World"):
            return f"Hello, {name}! The API server is running."

        @self.app.post("/users")
        async def create_user(user_id: str = None, gender: str = None, age: int = None, live_pref: str = None, live_city: str = None):
            """
            ユーザーを作成する。
            """
            if user_id is None:
                raise HTTPException(status_code=400, detail="User ID is required")
            personal = Personal(gender=gender, age=age, live_pref=live_pref, live_city=live_city)
            user = self.data_store.create_user(user_id, personal)
            return {"detail": "User created successfully", "user": user}
        
        @self.app.on_event("shutdown")
        async def shutdown_event():
            """サーバー終了時に全アクティブセッションを一時停止して保存"""
            logger.info("[INFO] Server shutdown: Saving active sessions...")
            session_ids = list(self.data_store.sessions.keys())
            for session_id in session_ids:
                try:
                    self.data_store.pause_session(session_id)
                except Exception as e:
                    logger.error(f"[ERROR] Session save failed: {session_id}, Error: {e}")
            logger.info(f"[SUCCESS] Saved {len(session_ids)} session(s)")

        @self.app.get("/sessions")
        async def get_sessions(user_id: str = None, session_id: str = None):
            """
            セッション情報を取得する。
            user_idとsession_idの両方が必須（セキュリティ強化）。
            """
            # 両方のパラメータが必須
            if user_id is None or session_id is None:
                raise HTTPException(status_code=400, detail="User ID and Session ID are required")
            # user_idとsession_idの組み合わせをチェック（403を避けて404を返す）
            if not self.data_store.has_user_session(user_id, session_id):
                raise HTTPException(status_code=404, detail="Session not found")
            return {"session_id": session_id, "history": self.data_store.get_history(session_id)}

        @self.app.post("/chat/default")
        async def chat_default(request: ChatRequest):
            """
            デフォルトプロンプトでチャットする。
            user_idは必須、session_idはオプショナル（Noneの場合は新規セッション作成）。
            """
            # user_idは必須
            if request.user_id is None:
                raise HTTPException(status_code=400, detail="User ID is required")
            # session_idが存在する場合は認証チェック
            if request.session_id is not None:
                if not self.data_store.has_user_session(request.user_id, request.session_id):
                    raise HTTPException(status_code=404, detail="Session not found")
            prompt_path = PROMPTS_DIR / "default.md"
            if not prompt_path.exists():
                raise HTTPException(status_code=500, detail=f"Prompt file not found: {prompt_path}")
            return await self.chat_prompt(request, str(prompt_path))

        @self.app.post("/chat/librarian")
        async def chat_librarian(request: ChatRequest):
            """
            司書プロンプトでチャットする。
            user_idは必須、session_idはオプショナル（Noneの場合は新規セッション作成）。
            """
            # user_idは必須
            if request.user_id is None:
                raise HTTPException(status_code=400, detail="User ID is required")
            # session_idが存在する場合は認証チェック
            if request.session_id is not None:
                if not self.data_store.has_user_session(request.user_id, request.session_id):
                    raise HTTPException(status_code=404, detail="Session not found")
            prompt_path = PROMPTS_DIR / "librarian.md"
            if not prompt_path.exists():
                raise HTTPException(status_code=500, detail=f"Prompt file not found: {prompt_path}")
            return await self.chat_prompt(request, str(prompt_path))

        @self.app.post("/close_session")
        async def close_session(background_tasks: BackgroundTasks, user_id: str = None, session_id: str = None):
            """
            明示的にセッションをクローズして永続化する。
            user_idとsession_idの両方が必須（セキュリティ強化）。
            summary/ai_insightの生成は非同期で実行される。
            """
            # 両方のパラメータが必須
            if user_id is None or session_id is None:
                raise HTTPException(status_code=400, detail="User ID and Session ID are required")
            # user_idとsession_idの組み合わせをチェック（403を避けて404を返す）
            if not self.data_store.has_user_session(user_id, session_id):
                raise HTTPException(status_code=404, detail="Session not found")
            try:
                # セッションをクローズ（同期処理）
                self.data_store.close_session(session_id)
                # summary/ai_insightの生成をバックグラウンドタスクで実行（非同期処理）
                background_tasks.add_task(self.data_store.generate_summary_and_insights, session_id)
            except KeyError:
                raise HTTPException(status_code=404, detail="Session not found")
            return {"detail": "Session closed and saved", "session_id": session_id}

    async def chat_prompt(self, request: ChatRequest, prompt_file: str) -> ChatResponse:
        # セッション確保
        session_id = request.session_id
        if not session_id:
            # user_id を渡して active_session を in-memory 更新する
            session_id = self.data_store.create_session(getattr(request, "user_id", None))
            history = []
        else:
            if not self.data_store.has_session(session_id):
                raise HTTPException(status_code=404, detail="Session not found")
            history = self.data_store.get_history(session_id)

        # ユーザーの ai_insights を取得して Gemini に渡す
        ai_insight = ""
        user_id = getattr(request, "user_id", None)
        conv = self.data_store.conversations.get(session_id)
        if not user_id and conv is not None:
            try:
                user_id = conv.user_id
            except Exception:
                user_id = None

        if user_id:
            user = self.data_store.get_user(user_id)
            if user:
                ai_insight = getattr(user, "ai_insights", "") or ""

        # Gemini 呼び出し（既存の実装を利用）
        # gemini_chat(prompt_file, message, history, ai_insight=None)
        response_text, new_history = gemini_chat(prompt_file, request.message, history, ai_insight=ai_insight)

        # メモリ上の履歴を更新（ディスク書き込みは close_session 時に行う）
        self.data_store.update_history(session_id, new_history)

        return ChatResponse(response=response_text, session_id=session_id)


# DataStoreインスタンスを作成
data_store = DataStore()

# Server を登録してルートを作成
server = Server(app, data_store)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
