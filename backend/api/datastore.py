# DataStore: JSONベースの暫定ストレージ（Users, Conversations, Sessions）

import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from .models import (
	ChatStatus, UserStatus, User, Conversation, 
	Personal, BookData, RecommendationLogEntry, NfcUser
)
# LangChainベースのLLM関数を使用
from . import summary_function

# LangChain Messages
from langchain_core.messages import (
	BaseMessage, 
	HumanMessage, 
	AIMessage,
	messages_to_dict, 
	messages_from_dict
)

# ロガー設定
logger = logging.getLogger("uvicorn.error")

# ファイルパス (DBへ移行するため, 一時的なもの. 本番はENVへまとめる)
from backend import PROMPTS_DIR, DATA_DIR, USERS_FILE, CONVERSATIONS_FILE, NFC_USERS_FILE, PROMPT_SUMMARY, PROMPT_AI_INSIGHT, SESSION_TIMEOUT



class DataStore:
	def __init__(self):
		DATA_DIR.mkdir(exist_ok=True)
		# メモリ上のデータ（最小限）
		self.users: Dict[str, User] = {}  # pauseセッションのユーザーのみ
		self.conversations: Dict[str, Conversation] = {}  # pauseのみ
		# sessions は Gemini とやり取りする「history」をそのまま保持する辞書（メモリ上）
		self.sessions: Dict[str, List[BaseMessage]] = {}
		# NFC認証用の辞書（全件）
		self.nfc_users: Dict[str, NfcUser] = {}
		# pauseセッションとそのユーザーを復元
		self._restore_paused_sessions()

	def _restore_paused_sessions(self):
		"""
		すべてのconversationsをメモリに読み込み、pauseセッションをactiveに戻す。
		last_accessedとlastloginを現在時刻に更新。
		そのユーザーも読み込む。
		"""
		if USERS_FILE.exists():
			with open(USERS_FILE, "r", encoding="utf-8") as f:
				try:
					users_data = json.load(f)
					for user_dict in users_data:
						user = User(**user_dict)
						self.users[user.user_id] = user
				except Exception:
					self.users = {}

		if CONVERSATIONS_FILE.exists():
			with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
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
				# messagesをin-memoryセッションに復元 (dict -> BaseMessage list)
				try:
					# 既存の messages (List[dict]) を LangChain Objects に変換
					# messages_from_dict は [{"type": "human", ...}] 形式を期待する
					# 互換性なし設定のため、パース失敗時は空リストまたはエラー
					if conv.messages:
						self.sessions[session_id] = messages_from_dict(conv.messages)
					else:
						self.sessions[session_id] = []
					restored_count += 1
				except Exception as e:
					logger.warning(f"[WARNING] Failed to restore session {session_id} due to format mismatch: {e}")
					# フォーマット不整合時は空で初期化（既存データ破棄）
					self.sessions[session_id] = []
		
		if restored_count > 0:
			logger.info(f"[SUCCESS] Restored {restored_count} paused session(s)")
		
		# nfc_users.jsonの読み込み
		if NFC_USERS_FILE.exists():
			with open(NFC_USERS_FILE, "r", encoding="utf-8") as f:
				try:
					nfc_data = json.load(f)
					for nfc_dict in nfc_data:
						nfc_user = NfcUser(**nfc_dict)
						self.nfc_users[nfc_user.nfc_id] = nfc_user
				except Exception:
					self.nfc_users = {}

	def save_file(self):
		"""
		users と conversations を永続化する。
		sessions はメモリ上のみで管理し、pause/close時に conversations に保存される。
		"""
		with open(USERS_FILE, 'w', encoding='utf-8') as f:
			json.dump([v.model_dump(by_alias=True) for v in self.users.values()], f, indent=2, default=str, ensure_ascii=False)
		
		with open(CONVERSATIONS_FILE, 'w', encoding='utf-8') as f:
			json.dump({k: v.model_dump(by_alias=True) for k, v in self.conversations.items()}, f, indent=2, default=str, ensure_ascii=False)
		
		# nfc_users.jsonへの保存
		with open(NFC_USERS_FILE, 'w', encoding='utf-8') as f:
			json.dump([v.model_dump(by_alias=True) for v in self.nfc_users.values()], f, indent=2, default=str, ensure_ascii=False)

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
		"""
		ユーザーデータを取得する（遅延読み込み）。
		既にメモリにある場合はそのまま返す。
		ない場合はディスクから読み込む。
		"""
		if user_id in self.users:
			# lastloginを更新
			self.users[user_id].lastlogin = datetime.now()
			return self.users[user_id]
		
		# ディスクから読み込み
		if USERS_FILE.exists():
			with open(USERS_FILE, "r", encoding="utf-8") as f:
				try:
					users_data = json.load(f)
					# リスト形式からdict形式に変換
					all_users = {}
					for user_dict in users_data:
						uid = user_dict.get("_id")
						if uid:
							all_users[uid] = user_dict
					
					if user_id in all_users:
						user_data = all_users[user_id]
						user = User(**user_data)
						# lastloginを更新
						user.lastlogin = datetime.now()
						self.users[user_id] = user
						logger.info(f"[INFO] Loaded user from disk: {user_id}")
						# 更新を保存
						self.save_file()
						return user
				except Exception as e:
					logger.error(f"[ERROR] Failed to load user from disk: {e}")
		
		return None


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
				# personalフィールドの場合はPersonalモデルに変換してから代入
				if key == "personal" and isinstance(value, dict):
					# 既存のpersonalオブジェクトを更新するか、新しく作成
					if user.personal:
						updated_personal = user.personal.copy(update=value)
						setattr(user, "personal", updated_personal)
					else:
						setattr(user, "personal", Personal(**value))
				else:
					setattr(user, key, value)
			else:
				raise ValueError(f"Invalid field: {key}")
		
		# 変更を保存
		self.save_file()
		
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
	
	# NFC authentication
	def register_nfc(self, nfc_id: str, user_id: str) -> NfcUser:
		"""
		NFC IDとユーザーIDを紐付ける。
		"""
		# ユーザーが存在するか確認（ディスクからのロード含む）
		if not self.get_user(user_id):
			raise KeyError(f"User not found: {user_id}")
		
		nfc_user = NfcUser(**{"_id": nfc_id, "user_id": user_id})
		self.nfc_users[nfc_id] = nfc_user
		self.save_file()
		return nfc_user
	
	def get_user_by_nfc(self, nfc_id: str) -> Optional[str]:
		"""
		NFC IDからユーザーIDを取得する。
		"""
		nfc_user = self.nfc_users.get(nfc_id)
		if nfc_user:
			return nfc_user.user_id
		return None
	
	def get_nfc_by_user_id(self, user_id: str) -> Optional[str]:
		"""
		ユーザーIDからNFC IDを取得する (逆引き)。
		"""
		for nfc_user in self.nfc_users.values():
			if nfc_user.user_id == user_id:
				return nfc_user.nfc_id
		return None
	
	def unregister_nfc(self, nfc_id: str) -> None:
		"""
		NFC IDの登録を解除する。
		"""
		if nfc_id in self.nfc_users:
			del self.nfc_users[nfc_id]
			self.save_file()

	# Session management (for chat runtime history)
	def create_session(self, user_id: str) -> str:
		"""
		新しいセッションをメモリ上に作成する。ユーザーIDが与えられれば
		in-memory で User.active_session を更新する（永続化は close 時）。
		"""
		# ユーザーがメモリにない場合はロード
		if user_id not in self.users:
			user = self.get_user(user_id)
			if not user:
				return None

		session_id = str(uuid.uuid4())
		conv = Conversation(**{"_id": session_id, "user_id": user_id, "messages": []})
		self.conversations[session_id] = conv
		self.sessions[session_id] = []  # history kept as List[BaseMessage]
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

	def get_history(self, session_id: str) -> List[BaseMessage]:
		# アクティブセッション（メモリ上）をチェック
		if session_id in self.sessions:
			return self.sessions.get(session_id, [])
		# 過去のセッション（永続化済み）をチェック
		elif session_id in self.conversations:
			# Dict -> BaseMessage 変換して返す (read-only用途が多いが念のため)
			messages_dict = self.conversations.get(session_id).messages
			if messages_dict:
				try:
					return messages_from_dict(messages_dict)
				except Exception:
					return []
			return []
		else:
			return []

	def update_history(self, session_id: str, history: List[BaseMessage]) -> None:
		"""
		メモリ上の履歴を更新し、最終アクセス時刻を記録する。
		"""
		self.sessions[session_id] = history
		
		# 最終アクセス時刻を更新し、ステータスをactiveにする
		if session_id in self.conversations:
			conv = self.conversations[session_id]
			conv.last_accessed = datetime.now()
			# pauseから復帰した場合などを考慮してactiveにする
			if conv.status != ChatStatus.active:
				conv.status = ChatStatus.active


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
		# List[BaseMessage] -> List[dict] に変換して保存
		messages = messages_to_dict(history)

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
		# List[BaseMessage] -> List[dict] に変換して保存
		messages = messages_to_dict(history)

		conv = self.conversations.get(session_id)
		if not conv:
			conv = Conversation(**{"_id": session_id, "user_id": "", "messages": []})

		conv.messages = messages
		conv.status = ChatStatus.pause  # pauseに設定
		self.conversations[session_id] = conv

		# in-memory sessionsを解放
		if session_id in self.sessions:
			del self.sessions[session_id]

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
				summary_path = PROMPT_SUMMARY
				if summary_path.exists():
					logger.info("[INFO] [BackgroundTask] Generating summary...")
					# ユーザーの ai_insights を要約の文脈として渡す
					user_insight = ""
					if conv.user_id and conv.user_id in self.users:
						user_insight = getattr(self.users[conv.user_id], "ai_insights", "") or ""
					
					# 会話履歴を文字列形式に変換
					conversation_text = ""
					
					try:
						history_objs = messages_from_dict(history)
						for msg in history_objs:
							# BaseMessage objects have .content and .type (or logic for role)
							role = msg.type
							content = msg.content
							conversation_text += f"{role}: {content}\n\n"
					except Exception:
						# Fallback for old data if any (though we said no compatibility)
						for msg in history:
							role = msg.get('role', msg.get('type', 'unknown'))
							content = msg.get('content', '')
							conversation_text += f"{role}: {content}\n\n"
					
					# summary_function を使って要約を生成（LangChainベース）
					summary_text = summary_function(str(summary_path), conversation_text, ai_insight=user_insight)
					if summary_text:
						conv.summary = summary_text
						self.conversations[session_id] = conv
						logger.info(f"[SUCCESS] [BackgroundTask] Summary generated: {len(summary_text)} characters")
					else:
						logger.warning(f"[WARNING] [BackgroundTask] Summary generation returned None")
				else:
					logger.warning(f"[WARNING] [BackgroundTask] summary.md not found: {summary_path}")
			except Exception as e:
				logger.error(f"[ERROR] [BackgroundTask] Summary generation failed: {e}", exc_info=True)

			# ai_insightsを更新（summaryが生成されている場合）
			user_id = conv.user_id
			if user_id and user_id in self.users and conv.summary:
				user = self.users[user_id]
				try:
					ai_insight_path = PROMPT_AI_INSIGHT
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
						# summary_function を使って新しい ai_insights を生成（LangChainベース）
						user.ai_insights = summary_function(str(ai_insight_path), message, ai_insight=None)
						logger.info(f"[SUCCESS] [BackgroundTask] ai_insights updated: {len(user.ai_insights)} characters")
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
	
	def check_user_timeout(self) -> List[str]:
		"""
		非アクティブなユーザーのセッションをcloseする。
		lastloginを基準に判定（SESSION_TIMEOUT秒）。
		タイムアウトしたセッションIDのリストを返す。
		"""
		timeout_threshold = datetime.now() - timedelta(seconds=SESSION_TIMEOUT)
		closed_sessions = []
		
		for user_id, user in list(self.users.items()):
			# lastloginがタイムアウトを超えている場合
			if user.lastlogin < timeout_threshold:
				# そのユーザーのアクティブセッションをすべてclose
				for session_id, conv in list(self.conversations.items()):
					if conv.user_id == user_id and conv.status == ChatStatus.active:
						logger.info(f"[INFO] User timeout: {user_id}, closing session: {session_id}")
						
						# タイムアウト時も要約とAI Insightsを生成する
						try:
							self.generate_summary_and_insights(session_id)
						except Exception as e:
							logger.error(f"[ERROR] Failed to generate insights during timeout for session {session_id}: {e}")
						
						# active → closed
						conv.status = ChatStatus.closed
						# メモリから削除
						if session_id in self.sessions:
							del self.sessions[session_id]
						closed_sessions.append(session_id)
				
				# ユーザーをメモリから削除せず、ステータスをlogoutに変更
				# del self.users[user_id]
				user.status = UserStatus.logout
				logger.info(f"[INFO] User timeout: {user_id}, status set to logout")
				logger.info(f"[INFO] Unloaded inactive user: {user_id}")
		
		# 変更を保存
		if closed_sessions:
			self.save_file()
		
		return closed_sessions

	
	def resume_session(self, session_id: str) -> None:
		"""
		pause状態のセッションをactiveに戻す。
		"""
		if session_id in self.conversations:
			conv = self.conversations[session_id]
			if conv.status == ChatStatus.pause:
				conv.status = ChatStatus.active
				conv.last_accessed = datetime.now()
				# messagesをin-memoryセッションに復元 (dict -> object)
				try:
					if conv.messages:
						self.sessions[session_id] = messages_from_dict(conv.messages)
					else:
						self.sessions[session_id] = []
				except Exception:
					self.sessions[session_id] = []
				logger.info(f"[INFO] Session resumed: {session_id}")
