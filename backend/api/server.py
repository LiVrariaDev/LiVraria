# Geminiを用いたチャットができるAPIサーバー

# Standard Library
from enum import Enum
from datetime import datetime
import json
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid

from fastapi import FastAPI, HTTPException
import uvicorn
from pathlib import Path

# user-defined
from .gemini import gemini_chat

app = FastAPI()

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
DATA_DIR = Path(__file__).resolve().parent / "data"
USERS_FILE = DATA_DIR / "users.json"
CONV_FILE = DATA_DIR / "conversations.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"

# Enum
class ChatStatus(str, Enum):
    active = "active"
    closed = "closed"

# Request/Response Models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str

# Data Models
class Message(BaseModel):
    role: str = Field(description="user or assistant")
    content: str = Field(description="message content")

class NfcUser(BaseModel):
    nfc_id: str = Field(alias="_id", description="NFC ID")
    user_id: str = Field(description="User ID")

class BookData(BaseModel):
    isbn: str = Field(alias="_id", description="ISBN")
    title: str
    ncid: Optional[str] = Field(None, description="NCID")
    author: Optional[str] = None
    publisher: Optional[str] = None
    pub_date: Optional[str] = None

class RecommendationLogEntry(BaseModel):
    reason: str = Field(description="Reason for recommendation")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of recommendation")
    book_data: BookData = Field(description="Recommended book data")

class User(BaseModel):
    user_id: str = Field(alias="_id", description="User ID")
    ai_insights : str = Field("", description="AI Insights about the user")
    personal: Dict[str, Any] = Field(default_factory=dict, description="Personal information (gender, age ...)")
    active_session: Optional[str] = Field(default=None, description="Active chat session ID")
    old_session: List[str] = Field(default_factory=list, description="Old chat session IDs")
    recommend_log: List[RecommendationLogEntry] = Field(default_factory=list, description="Recommendation log")
    lastlogin: datetime = Field(default_factory=datetime.now, description="Last login time")

    class Config:
        populate_by_name = True

class Conversation(BaseModel):
    session_id: str = Field(alias="_id", description="Session ID")
    user_id: str = Field(description="User ID")
    status: ChatStatus = Field(default=ChatStatus.active, description="Chat status")
    messages: List[Message] = Field(default_factory=list, description="Chat messages")
    summary: Optional[str] = Field(None, description="AI-generated summary at session end")

    class Config:
        populate_by_name = True

# DataStore: JSONベースの暫定ストレージ（Users, Conversations, Sessions）
class DataStore:
    def __init__(self):
        DATA_DIR.mkdir(exist_ok=True)
        self.users: Dict[str, User] = {}
        self.conversations: Dict[str, Conversation] = {}
        # sessions は Gemini とやり取りする「history」をそのまま保持する辞書（メモリ上）
        self.sessions: Dict[str, Any] = {}
        self._load_from_files()

    def _load_from_files(self):
        if USERS_FILE.exists():
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                try:
                    users_data = json.load(f)
                    for user_dict in users_data:
                        user = User(**user_dict)
                        self.users[user.user_id] = user
                except Exception:
                    self.users = {}

        if CONV_FILE.exists():
            with open(CONV_FILE, "r", encoding="utf-8") as f:
                try:
                    convs_data = json.load(f)
                    for conv_dict in convs_data.values():
                        conv = Conversation(**conv_dict)
                        self.conversations[conv.session_id] = conv
                except Exception:
                    self.conversations = {}

        if SESSIONS_FILE.exists():
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                try:
                    # 古い保存から復元（ただし実運用では起動時のみ読み込む想定）
                    self.sessions = json.load(f)
                except Exception:
                    self.sessions = {}

    def save_file(self):
        """
        users, conversations, (残す場合は sessions) を永続化する。
        現在の方針では sessions はアクティブ中はメモリ上のみ、クローズ時に save_file を呼ぶ。
        """
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump([v.model_dump(by_alias=True) for v in self.users.values()], f, indent=2, default=str, ensure_ascii=False)
        
        with open(CONV_FILE, 'w', encoding='utf-8') as f:
            json.dump({k: v.model_dump(by_alias=True) for k, v in self.conversations.items()}, f, indent=2, default=str, ensure_ascii=False)

        # sessions は必要なら保存する（ここでは conversations に会話を取り込むため空でよい）
        with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.sessions, f, indent=2, default=str, ensure_ascii=False)

    def get_user(self, user_id: str) -> Optional[User]:
        return self.users.get(user_id)

    # Session management (for chat runtime history)
    def create_session(self, user_id: Optional[str] = None) -> str:
        """
        新しいセッションをメモリ上に作成する。ユーザーIDが与えられれば
        in-memory で User.active_session を更新する（永続化は close 時）。
        """
        session_id = str(uuid.uuid4())
        conv = Conversation(**{"_id": session_id, "user_id": user_id or "", "messages": []})
        self.conversations[session_id] = conv
        self.sessions[session_id] = []  # history kept as list (Gemini chat history)
        # In-memory update of user's active_session
        if user_id and user_id in self.users:
            user = self.users[user_id]
            if user.active_session:
                # 移行: 古い active を old_session に退避
                if user.active_session not in user.old_session:
                    user.old_session.append(user.active_session)
            user.active_session = session_id
            user.lastlogin = datetime.now()
        # note: do NOT call self.save_file() here to avoid frequent disk writes
        return session_id

    def has_session(self, session_id: str) -> bool:
        return session_id in self.sessions or session_id in self.conversations

    def get_history(self, session_id: str) -> Any:
        return self.sessions.get(session_id, [])

    def update_history(self, session_id: str, history: Any) -> None:
        """
        メモリ上の履歴だけ更新する（頻繁なディスク書き込みを避ける）。
        永続化は close_session を呼ぶことで行う。
        """
        self.sessions[session_id] = history

    def close_session(self, session_id: str) -> None:
        """
        セッションをクローズして永続化する。
        - history を Conversation.messages に変換して保存
        - Conversation.status を closed にする
        - 該当ユーザーの active_session を解除し old_session に追加
        - sessions の in-memory エントリを削除
        - 最後に save_file() を呼んで disk に書き込む
        """
        if session_id not in self.sessions and session_id not in self.conversations:
            raise KeyError("Session not found")

        history = self.sessions.get(session_id, [])
        messages: List[Message] = []
        # history の形式は可変なので耐性を持って変換する
        for part in history:
            try:
                if isinstance(part, dict) and "role" in part and "content" in part:
                    messages.append(Message(role=part["role"], content=part["content"]))
                elif hasattr(part, "role") and hasattr(part, "content"):
                    messages.append(Message(role=getattr(part, "role"), content=getattr(part, "content")))
                else:
                    # fallback: シリアライズして assistant として格納
                    messages.append(Message(role="assistant", content=str(part)))
            except Exception:
                messages.append(Message(role="assistant", content=str(part)))

        conv = self.conversations.get(session_id)
        if not conv:
            conv = Conversation(**{"_id": session_id, "user_id": "", "messages": []})

        conv.messages = messages
        conv.status = ChatStatus.closed
        # セッション終了時に要約を自動作成する（summary.md を利用）
        try:
            summary_path = PROMPTS_DIR / "summary.md"
            if summary_path.exists():
                # ユーザーの ai_insights を要約の文脈として渡す
                user_insight = ""
                if conv.user_id and conv.user_id in self.users:
                    user_insight = getattr(self.users[conv.user_id], "ai_insights", "") or ""
                # gemini_chat のシグネチャ: gemini_chat(prompt_file, message, history, ai_insight=None)
                summary_text, _ = gemini_chat(str(summary_path), "この会話を日本語で簡潔に要約してください。", history, ai_insight=user_insight)
                conv.summary = summary_text
        except Exception:
            # 要約生成に失敗してもクローズ処理は継続する
            pass

        self.conversations[session_id] = conv

        # ユーザーの active_session を解除して old_session に追加
        user_id = conv.user_id
        if user_id and user_id in self.users:
            user = self.users[user_id]
            if user.active_session == session_id:
                user.active_session = None
            if session_id not in user.old_session:
                user.old_session.append(session_id)

        # in-memory sessions を解放（必要なら残す）
        if session_id in self.sessions:
            del self.sessions[session_id]

        # 永続化（users, conversations, sessions）
        self.save_file()

    def delete_session(self, session_id: str) -> None:
        if session_id in self.sessions:
            del self.sessions[session_id]
        if session_id in self.conversations:
            del self.conversations[session_id]
        self.save_file()

# インスタンス
DATA_STORE = DataStore()

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

        @self.app.get("/sessions")
        async def get_sessions(session_id: str = None):
            if session_id is None:
                raise HTTPException(status_code=400, detail="Session ID is required")
            if not self.data_store.has_session(session_id):
                raise HTTPException(status_code=404, detail="Session not found")
            return {"session_id": session_id, "history": self.data_store.get_history(session_id)}

        @self.app.post("/chat/default")
        async def chat_default(request: ChatRequest):
            prompt_path = PROMPTS_DIR / "default.md"
            if not prompt_path.exists():
                raise HTTPException(status_code=500, detail=f"Prompt file not found: {prompt_path}")
            return await self.chat_prompt(request, str(prompt_path))

        @self.app.post("/chat/librarian")
        async def chat_librarian(request: ChatRequest):
            prompt_path = PROMPTS_DIR / "librarian.md"
            if not prompt_path.exists():
                raise HTTPException(status_code=500, detail=f"Prompt file not found: {prompt_path}")
            return await self.chat_prompt(request, str(prompt_path))

        @self.app.post("/close_session")
        async def close_session(session_id: str = None):
            """
            明示的にセッションをクローズして永続化するエンドポイント（暫定）。
            """
            if session_id is None:
                raise HTTPException(status_code=400, detail="Session ID is required")
            try:
                self.data_store.close_session(session_id)
            except KeyError:
                raise HTTPException(status_code=404, detail="Session not found")
            return {"detail": "Session closed and saved", "session_id": session_id}

        @self.app.delete("/delete_session")
        async def delete_session(session_id: str = None):
            if session_id is None:
                raise HTTPException(status_code=400, detail="Session ID is required")
            if not self.data_store.has_session(session_id) and session_id not in self.data_store.conversations:
                raise HTTPException(status_code=404, detail="Session not found")
            self.data_store.delete_session(session_id)
            return {"detail": "Session deleted successfully"}

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

# Server を登録してルートを作成
_server = Server(app, DATA_STORE)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

