# Geminiを用いたチャットができるAPIサーバー

# Standard Library
from enum import Enum
from datetime import datetime
import json
import logging
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid

from fastapi import FastAPI, HTTPException, BackgroundTasks
import uvicorn
from pathlib import Path

# user-defined
from .gemini import gemini_chat

# ロガー設定
logger = logging.getLogger("uvicorn.error")

app = FastAPI()

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
DATA_DIR = Path(__file__).resolve().parent / "data"
USERS_FILE = DATA_DIR / "users.json"
CONV_FILE = DATA_DIR / "conversations.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"

# Enum
class ChatStatus(str, Enum):
    active = "active"
    pause = "pause"
    closed = "closed"

class UserStatus(str, Enum):
    activate = "activate"
    logout = "logout"
    chatting = "chatting"

# Request/Response Models
class ChatRequest(BaseModel):
    message: str
    session_id: str = None
    user_id: str = None

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

class Personal(BaseModel):
    gender: str = Field(description="Gender")
    age: int = Field(description="Age")
    live_pref: Optional[str] = Field(None, description="Living preference")
    live_city: Optional[str] = Field(None, description="Living city")

class User(BaseModel):
    user_id: str = Field(alias="_id", description="User ID")
    ai_insights : str = Field("", description="AI Insights about the user")
    personal: Personal = Field(default_factory=Personal, description="Personal information (gender, age ...)")
    status: UserStatus = Field(default=UserStatus.logout, description="User status (activate/logout/chatting)")
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

    # def __del__(self):
    #     for user in self.users.values():
    #         active = user.active_session
    #         if active:
    #             self.close_session(active)

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

    def create_user(self, user_id: str, personal: Personal) -> User:
        if user_id not in self.users:
            self.users[user_id] = User(**{
                "_id": user_id, 
                "lastlogin": datetime.now(), 
                "personal": personal,
                "status": UserStatus.activate
            })
        return self.users[user_id]

    def get_user(self, user_id: str) -> User:
        if user_id not in self.users:
            return None
        else:
            return self.users[user_id]

    def update_user(self, user_id: str, **kwargs) -> User:
        """
        ユーザー情報を更新する。
        ai_insights, status, personal などのフィールドを更新可能。
        """
        if user_id not in self.users:
            raise KeyError(f"User not found: {user_id}")
        
        user = self.users[user_id]
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
            else:
                raise ValueError(f"Invalid field: {key}")
        
        return user

    def add_recommendation(self, user_id: str, book_data: BookData, reason: str) -> None:
        """
        ユーザーの推薦ログに新しい書籍推薦を追加する。
        """
        if user_id not in self.users:
            raise KeyError(f"User not found: {user_id}")
        
        user = self.users[user_id]
        entry = RecommendationLogEntry(book_data=book_data, reason=reason)
        user.recommend_log.append(entry)

    # Session management (for chat runtime history)
    def create_session(self, user_id: str) -> str:
        """
        新しいセッションをメモリ上に作成する。ユーザーIDが与えられれば
        in-memory で User.active_session を更新する（永続化は close 時）。
        """
        if user_id not in self.users:
            return None

        session_id = str(uuid.uuid4())
        conv = Conversation(**{"_id": session_id, "user_id": user_id, "messages": []})
        self.conversations[session_id] = conv
        self.sessions[session_id] = []  # history kept as list (Gemini chat history)
        # In-memory update of user's active_session
        user = self.users[user_id]
        if user.active_session:
            # 移行: 古い active を old_session に退避
            if user.active_session not in user.old_session:
                user.old_session.append(user.active_session)
        user.active_session = session_id
        user.lastlogin = datetime.now()
        user.status = UserStatus.chatting  # セッション開始時にステータスを chatting に変更
        # note: do NOT call self.save_file() here to avoid frequent disk writes
        return session_id

    def has_session(self, session_id: str) -> bool:
        """
        セッションの存在確認（アクティブ・過去両方をチェック）
        """
        return session_id in self.sessions or session_id in self.conversations

    def has_user_session(self, user_id: str, session_id: str) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        return session_id == user.active_session or session_id in user.old_session

    def get_history(self, session_id: str) -> Any:
        # アクティブセッション（メモリ上）をチェック
        if session_id in self.sessions:
            return self.sessions.get(session_id, [])
        # 過去のセッション（永続化済み）をチェック
        elif session_id in self.conversations:
            return self.conversations.get(session_id, {}).messages
        else:
            return []

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
        
        注: summary/ai_insightの生成は非同期処理で行うため、ここでは実行しない
        """
        if session_id not in self.sessions and session_id not in self.conversations:
            raise KeyError("Session not found")

        history = self.sessions.get(session_id, [])
        messages: List[Message] = []
        # history の形式は可変なので耐性を持って変換する
        for part in history:
            try:
                # Gemini APIのレスポンスオブジェクトの場合
                if hasattr(part, 'role') and hasattr(part, 'parts'):
                    # roleを抽出（userまたはmodel）
                    role = getattr(part, 'role', 'model')
                    # partsからテキストを抽出
                    content = ""
                    parts = getattr(part, 'parts', [])
                    if parts and len(parts) > 0:
                        content = getattr(parts[0], 'text', str(part))
                    else:
                        content = str(part)
                    messages.append(Message(role=role, content=content))
                # 辞書形式の場合
                elif isinstance(part, dict) and "role" in part and "content" in part:
                    role = part["role"]
                    # assistantをmodelに変換
                    if role == "assistant":
                        role = "model"
                    messages.append(Message(role=role, content=part["content"]))
                # Messageオブジェクトの場合
                elif hasattr(part, "role") and hasattr(part, "content"):
                    role = getattr(part, "role")
                    # assistantをmodelに変換
                    if role == "assistant":
                        role = "model"
                    messages.append(Message(role=role, content=getattr(part, "content")))
                else:
                    # fallback: シリアライズして model として格納
                    messages.append(Message(role="model", content=str(part)))
            except Exception:
                messages.append(Message(role="model", content=str(part)))

        conv = self.conversations.get(session_id)
        if not conv:
            conv = Conversation(**{"_id": session_id, "user_id": "", "messages": []})

        conv.messages = messages
        conv.status = ChatStatus.closed
        self.conversations[session_id] = conv

        # ユーザーの active_session を解除して old_session に追加
        user_id = conv.user_id
        if user_id and user_id in self.users:
            user = self.users[user_id]
            if user.active_session == session_id:
                user.active_session = None
            if session_id not in user.old_session:
                user.old_session.append(session_id)
            user.status = UserStatus.logout  # セッション終了時にステータスを logout に変更

        # in-memory sessions を解放（必要なら残す）
        if session_id in self.sessions:
            del self.sessions[session_id]

        # 永続化（users, conversations, sessions）
        self.save_file()

    def generate_summary_and_insights(self, session_id: str) -> None:
        """
        セッションの要約とai_insightsを生成する（非同期処理用）。
        この関数はBackgroundTasksで呼び出される。
        """
        logger.info(f"🔄 [BackgroundTask] summary/ai_insights生成開始: session_id={session_id}")
        try:
            # セッションと履歴を取得
            conv = self.conversations.get(session_id)
            if not conv:
                logger.warning(f"⚠️ [BackgroundTask] セッションが見つかりません: {session_id}")
                return
            
            history = conv.messages
            logger.info(f"📝 [BackgroundTask] 履歴件数: {len(history)}")
            
            # summaryを生成
            try:
                summary_path = PROMPTS_DIR / "summary.md"
                if summary_path.exists():
                    logger.info(f"📄 [BackgroundTask] summary生成中...")
                    # ユーザーの ai_insights を要約の文脈として渡す
                    user_insight = ""
                    if conv.user_id and conv.user_id in self.users:
                        user_insight = getattr(self.users[conv.user_id], "ai_insights", "") or ""
                    
                    # 会話履歴を文字列形式に変換
                    conversation_text = ""
                    for msg in history:
                        role = msg.role if hasattr(msg, 'role') else msg.get('role', 'unknown')
                        content = msg.content if hasattr(msg, 'content') else msg.get('content', '')
                        conversation_text += f"{role}: {content}\n\n"
                    
                    # gemini_chat を使って要約を生成（履歴は空、会話内容はメッセージとして渡す）
                    summary_text, _ = gemini_chat(str(summary_path), conversation_text, [], ai_insight=user_insight)
                    conv.summary = summary_text
                    self.conversations[session_id] = conv
                    logger.info(f"✅ [BackgroundTask] summary生成完了: {len(summary_text)} 文字")
                else:
                    logger.warning(f"⚠️ [BackgroundTask] summary.mdが見つかりません: {summary_path}")
            except Exception as e:
                logger.error(f"❌ [BackgroundTask] summary生成エラー: {e}", exc_info=True)

            # ai_insightsを更新（summaryが生成されている場合）
            user_id = conv.user_id
            if user_id and user_id in self.users and conv.summary:
                user = self.users[user_id]
                try:
                    ai_insight_path = PROMPTS_DIR / "ai_insight.md"
                    if ai_insight_path.exists():
                        logger.info(f"🧠 [BackgroundTask] ai_insights更新中...")
                        # 既存の ai_insights を取得
                        existing_insights = user.ai_insights or ""
                        
                        # プロンプトメッセージを構築
                        message = f"""
**既存のAI Insights:**
```
{existing_insights if existing_insights else "（なし）"}
```

**今回の会話要約:**
```
{conv.summary}
```
"""
                        # gemini_chat を使って新しい ai_insights を生成
                        new_insights, _ = gemini_chat(str(ai_insight_path), message, [], ai_insight=None)
                        
                        # ユーザーの ai_insights を更新
                        user.ai_insights = new_insights
                        logger.info(f"✅ [BackgroundTask] ai_insights更新完了: {len(new_insights)} 文字")
                    else:
                        logger.warning(f"⚠️ [BackgroundTask] ai_insight.mdが見つかりません: {ai_insight_path}")
                except Exception as e:
                    logger.error(f"❌ [BackgroundTask] ai_insights更新エラー: {e}", exc_info=True)
            
            # 永続化
            logger.info(f"💾 [BackgroundTask] データ永続化中...")
            self.save_file()
            logger.info(f"✅ [BackgroundTask] 完了: session_id={session_id}")
        except Exception as e:
            logger.error(f"❌ [BackgroundTask] エラー: {e}", exc_info=True)

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

        @self.app.post("/users")
        async def create_user(user_id: str, gender: str, age: int, live_pref: Optional[str] = None, live_city: Optional[str] = None):
            """
            新規ユーザーを作成する。
            """
            personal = Personal(gender=gender, age=age, live_pref=live_pref, live_city=live_city)
            user = self.data_store.create_user(user_id, personal)
            return {"detail": "User created successfully", "user": user}

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

# Server を登録してルートを作成
_server = Server(app, DATA_STORE)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

