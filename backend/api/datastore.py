# DataStore: JSONベースの暫定ストレージ（Users, Conversations, Sessions）

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .models import (
    ChatStatus, UserStatus, User, Conversation, 
    Message, Personal, BookData, RecommendationLogEntry
)
from .gemini import gemini_chat

# ロガー設定
logger = logging.getLogger("uvicorn.error")

# ファイルパス
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
DATA_DIR = Path(__file__).resolve().parent / "data"
USERS_FILE = DATA_DIR / "users.json"
CONV_FILE = DATA_DIR / "conversations.json"


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

        # in-memoryセッションを初期化
        self.sessions = {}
        
        # pause状態のセッションを復元
        restored_count = 0
        for session_id, conv in self.conversations.items():
            if conv.status == ChatStatus.pause:
                # messagesをin-memoryセッションに復元
                # Gemini APIが理解できる形式に変換する必要がある
                # ここでは単純にmessagesをそのまま復元
                self.sessions[session_id] = conv.messages
                restored_count += 1
        
        if restored_count > 0:
            logger.info(f"[SUCCESS] Restored {restored_count} paused session(s)")

    def save_file(self):
        """
        users と conversations を永続化する。
        sessions はメモリ上のみで管理し、pause/close時に conversations に保存される。
        """
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump([v.model_dump(by_alias=True) for v in self.users.values()], f, indent=2, default=str, ensure_ascii=False)
        
        with open(CONV_FILE, 'w', encoding='utf-8') as f:
            json.dump({k: v.model_dump(by_alias=True) for k, v in self.conversations.items()}, f, indent=2, default=str, ensure_ascii=False)

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

    def pause_session(self, session_id: str) -> None:
        """
        アクティブセッションを一時停止して保存する。
        summary/ai_insightは生成しない。
        サーバー終了時などに使用。
        """
        if session_id not in self.sessions:
            return
        
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
        conv.status = ChatStatus.pause  # pauseに設定
        self.conversations[session_id] = conv

        # 永続化（users, conversations, sessions）
        self.save_file()
        logger.info(f"[SUCCESS] Session paused: {session_id}")

    def generate_summary_and_insights(self, session_id: str) -> None:
        """
        セッションの要約とai_insightsを生成する（非同期処理用）。
        この関数はBackgroundTasksで呼び出される。
        """
        logger.info(f"[INFO] [BackgroundTask] Starting summary/ai_insights generation: session_id={session_id}")
        try:
            # セッションと履歴を取得
            conv = self.conversations.get(session_id)
            if not conv:
                logger.warning(f"[WARNING] [BackgroundTask] Session not found: {session_id}")
                return
            
            history = conv.messages
            logger.info(f"[INFO] [BackgroundTask] History count: {len(history)}")
            
            # summaryを生成
            try:
                summary_path = PROMPTS_DIR / "summary.md"
                if summary_path.exists():
                    logger.info("[INFO] [BackgroundTask] Generating summary...")
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
                    logger.info(f"[SUCCESS] [BackgroundTask] Summary generated: {len(summary_text)} characters")
                else:
                    logger.warning(f"[WARNING] [BackgroundTask] summary.md not found: {summary_path}")
            except Exception as e:
                logger.error(f"[ERROR] [BackgroundTask] Summary generation failed: {e}", exc_info=True)

            # ai_insightsを更新（summaryが生成されている場合）
            user_id = conv.user_id
            if user_id and user_id in self.users and conv.summary:
                user = self.users[user_id]
                try:
                    ai_insight_path = PROMPTS_DIR / "ai_insight.md"
                    if ai_insight_path.exists():
                        logger.info("[INFO] [BackgroundTask] Updating ai_insights...")
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
                        logger.info(f"[SUCCESS] [BackgroundTask] ai_insights updated: {len(new_insights)} characters")
                    else:
                        logger.warning(f"[WARNING] [BackgroundTask] ai_insight.md not found: {ai_insight_path}")
                except Exception as e:
                    logger.error(f"[ERROR] [BackgroundTask] ai_insights update failed: {e}", exc_info=True)
            
            # 永続化
            logger.info("[INFO] [BackgroundTask] Saving data...")
            self.save_file()
            logger.info(f"[SUCCESS] [BackgroundTask] Completed: session_id={session_id}")
        except Exception as e:
            logger.error(f"[ERROR] [BackgroundTask] Error: {e}", exc_info=True)
