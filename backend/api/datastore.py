# DataStore: JSONベースの暫定ストレージ（Users, Conversations, Sessions）
#
# 並行性について:
#   FastAPI のリクエスト処理（スレッドプール）、BackgroundTasks、タイムアウト監視が
#   同じ DataStore を同時に触るため、状態の読み書きは self._lock で直列化する。
#   LLM 呼び出し（要約・AI Insights 生成）は時間がかかるため、ロックの外で実行する。

import json
import logging
import os
import tempfile
import re
import threading
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Dict, List, Optional

from .models import (
	ChatStatus, UserStatus, User, Conversation,
	Personal, BookData, RecommendationLogEntry, NfcUser
)
# LangChainベースのLLM関数を使用
from . import summary_function

# LangChain Messages
from langchain_core.messages import (
	BaseMessage,
	messages_to_dict,
	messages_from_dict
)

# ロガー設定
logger = logging.getLogger("uvicorn.error")

# ファイルパス (DBへ移行するため, 一時的なもの. 本番はENVへまとめる)
from backend import DATA_DIR, USERS_FILE, CONVERSATIONS_FILE, NFC_USERS_FILE, PROMPT_SUMMARY_AND_INSIGHT, SESSION_TIMEOUT


def _locked(method):
	"""DataStore のメソッドを self._lock で保護するデコレータ。"""
	@wraps(method)
	def wrapper(self, *args, **kwargs):
		with self._lock:
			return method(self, *args, **kwargs)
	return wrapper


def _atomic_write_json(path: Path, data) -> None:
	"""
	一時ファイルへ書き込んでから置き換える。
	書き込み途中でプロセスが落ちても、元のファイルが壊れた状態で残らない。
	"""
	path = Path(path)
	fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
	try:
		with os.fdopen(fd, "w", encoding="utf-8") as f:
			json.dump(data, f, indent=2, default=str, ensure_ascii=False)
			f.flush()
			os.fsync(f.fileno())
		os.replace(tmp_path, path)
	except BaseException:
		try:
			os.remove(tmp_path)
		except FileNotFoundError:
			pass
		raise


def _load_json(path: Path, default):
	"""
	JSON ファイルを読み込む。
	- 存在しない / 空ファイル: default を返す
	- 壊れている: 退避（*.corrupt-日時）してから default を返す
	  （以前は例外を握りつぶして空データで起動し、次の保存で全データを消していた）
	"""
	path = Path(path)
	if not path.exists():
		return default
	text = path.read_text(encoding="utf-8")
	if not text.strip():
		return default
	try:
		return json.loads(text)
	except json.JSONDecodeError as e:
		backup = path.with_name(f"{path.name}.corrupt-{datetime.now():%Y%m%d%H%M%S}")
		path.replace(backup)
		logger.error(f"[ERROR] {path.name} is corrupted ({e}). Moved to {backup.name} and starting empty.")
		return default


_SUMMARY_TAG = re.compile(r"<summary>(.*?)</summary>", re.DOTALL)
_INSIGHTS_TAG = re.compile(r"<ai_insights>(.*?)</ai_insights>", re.DOTALL)


def parse_summary_and_insights(result: Optional[str]) -> tuple[Optional[str], Optional[str]]:
	"""LLM の出力から (要約, AI Insights) を取り出す。取れないものは None。"""
	if not result or not result.strip():
		return None, None
	summary_match = _SUMMARY_TAG.search(result)
	if not summary_match:
		# 形式を守らなかった場合は、タグを除いた全文を要約として残す。
		text = re.sub(r"</?(?:summary|ai_insights)>", "", result).strip()
		return (text or None), None
	insights_match = _INSIGHTS_TAG.search(result)
	summary = summary_match.group(1).strip() or None
	insights = (insights_match.group(1).strip() or None) if insights_match else None
	return summary, insights


class DataStore:
	def __init__(self):
		DATA_DIR.mkdir(parents=True, exist_ok=True)
		self._lock = threading.RLock()
		self.users: Dict[str, User] = {}
		self.conversations: Dict[str, Conversation] = {}
		# sessions は LLM とやり取りする「history」をそのまま保持する辞書（メモリ上）
		# 永続化は close/pause/timeout 時に conversations[session_id].messages へ書き出す
		self.sessions: Dict[str, List[BaseMessage]] = {}
		# NFC認証用の辞書（全件）
		self.nfc_users: Dict[str, NfcUser] = {}
		self._restore_paused_sessions()

	def _restore_paused_sessions(self):
		"""
		users / conversations / nfc_users を読み込み、pause セッションを in-memory に復元する。
		個々のレコードが壊れていても、そのレコードだけ飛ばして他は読み込む。
		"""
		for user_dict in _load_json(USERS_FILE, []):
			try:
				user = User(**user_dict)
				self.users[user.user_id] = user
			except Exception as e:
				logger.error(f"[ERROR] Skipped invalid user record: {e}")

		for conv_dict in _load_json(CONVERSATIONS_FILE, {}).values():
			try:
				conv = Conversation(**conv_dict)
				self.conversations[conv.session_id] = conv
			except Exception as e:
				logger.error(f"[ERROR] Skipped invalid conversation record: {e}")

		restored_count = 0
		for session_id, conv in self.conversations.items():
			if conv.status == ChatStatus.pause:
				self.sessions[session_id] = self._messages_from_conv(conv)
				restored_count += 1
		if restored_count > 0:
			logger.info(f"[SUCCESS] Restored {restored_count} paused session(s)")

		for nfc_dict in _load_json(NFC_USERS_FILE, []):
			try:
				nfc_user = NfcUser(**nfc_dict)
				self.nfc_users[nfc_user.nfc_id] = nfc_user
			except Exception as e:
				logger.error(f"[ERROR] Skipped invalid NFC record: {e}")

	@staticmethod
	def _messages_from_conv(conv: Conversation) -> List[BaseMessage]:
		if not conv.messages:
			return []
		try:
			return messages_from_dict(conv.messages)
		except Exception as e:
			logger.warning(f"[WARNING] Failed to parse messages of session {conv.session_id}: {e}")
			return []

	@_locked
	def save_file(self):
		"""users / conversations / nfc_users をアトミックに永続化する。"""
		_atomic_write_json(USERS_FILE, [v.model_dump(by_alias=True) for v in self.users.values()])
		_atomic_write_json(CONVERSATIONS_FILE, {k: v.model_dump(by_alias=True) for k, v in self.conversations.items()})
		_atomic_write_json(NFC_USERS_FILE, [v.model_dump(by_alias=True) for v in self.nfc_users.values()])

	@_locked
	def create_user(self, user_id: str, personal: Personal) -> User:
		if user_id not in self.users:
			self.users[user_id] = User(**{
				"_id": user_id,
				"lastlogin": datetime.now(),
				"personal": personal,
				"status": UserStatus.activate
			})
			self.save_file()
		return self.users[user_id]

	@_locked
	def get_user(self, user_id: str) -> Optional[User]:
		"""
		ユーザーデータを取得し、lastlogin（最終操作時刻）を更新する。
		起動時に全ユーザーを読み込んでいるため、ディスクの再読込はしない。
		"""
		user = self.users.get(user_id)
		if user:
			user.lastlogin = datetime.now()
		return user

	@_locked
	def update_user(self, user_id: str, **kwargs) -> User:
		"""
		ユーザー情報を更新する（サーバー内部用）。
		クライアントからの更新は update_personal を使うこと。
		"""
		if user_id not in self.users:
			raise KeyError(f"User not found: {user_id}")

		user = self.users[user_id]
		for key in kwargs:
			if key not in User.model_fields:
				raise ValueError(f"Invalid field: {key}")
		for key, value in kwargs.items():
			if key == "personal" and isinstance(value, dict):
				value = user.personal.model_copy(update=value) if user.personal else Personal(**value)
			setattr(user, key, value)

		self.save_file()
		return user

	@_locked
	def update_personal(self, user_id: str, updates: dict) -> User:
		"""
		クライアントから変更してよいのは personal のみ。
		pydantic で検証してから反映する（型不正は ValueError）。
		"""
		if user_id not in self.users:
			raise KeyError(f"User not found: {user_id}")
		user = self.users[user_id]
		merged = user.personal.model_dump() if user.personal else {}
		merged.update(updates)
		user.personal = Personal(**merged)
		self.save_file()
		return user

	@_locked
	def add_recommendation(self, user_id: str, book_data: BookData, reason: str) -> None:
		"""ユーザーの推薦ログに新しい書籍推薦を追加する。"""
		if user_id not in self.users:
			raise KeyError(f"User not found: {user_id}")
		entry = RecommendationLogEntry(book_data=book_data, reason=reason)
		self.users[user_id].recommend_log.append(entry)

	# NFC authentication
	@_locked
	def register_nfc(self, nfc_id: str, user_id: str) -> NfcUser:
		"""
		NFC IDとユーザーIDを紐付ける。
		1ユーザーにつき1枚のみ登録可能（既存の登録があれば削除）。
		他人が登録済みのカードは上書きしない。
		"""
		if user_id not in self.users:
			raise KeyError(f"User not found: {user_id}")

		existing = self.nfc_users.get(nfc_id)
		if existing and existing.user_id != user_id:
			raise PermissionError("NFC card is already registered to another user")

		old_nfc_id = self.get_nfc_by_user_id(user_id)
		if old_nfc_id and old_nfc_id != nfc_id:
			del self.nfc_users[old_nfc_id]
			logger.info(f"[INFO] Removed old NFC card for user {user_id}")

		nfc_user = NfcUser(**{"_id": nfc_id, "user_id": user_id})
		self.nfc_users[nfc_id] = nfc_user
		self.save_file()
		return nfc_user

	@_locked
	def get_user_by_nfc(self, nfc_id: str) -> Optional[str]:
		nfc_user = self.nfc_users.get(nfc_id)
		return nfc_user.user_id if nfc_user else None

	@_locked
	def get_nfc_by_user_id(self, user_id: str) -> Optional[str]:
		for nfc_user in self.nfc_users.values():
			if nfc_user.user_id == user_id:
				return nfc_user.nfc_id
		return None

	@_locked
	def unregister_nfc(self, nfc_id: str) -> None:
		if nfc_id in self.nfc_users:
			del self.nfc_users[nfc_id]
			self.save_file()

	# Session management (for chat runtime history)
	@_locked
	def create_session(self, user_id: str) -> Optional[str]:
		"""
		新しいセッションをメモリ上に作成し、User.active_session を更新する。
		ユーザーが存在しなければ None。
		"""
		user = self.users.get(user_id)
		if not user:
			return None

		session_id = str(uuid.uuid4())
		self.conversations[session_id] = Conversation(**{"_id": session_id, "user_id": user_id, "messages": []})
		self.sessions[session_id] = []
		if user.active_session and user.active_session not in user.old_session:
			user.old_session.append(user.active_session)
		user.active_session = session_id
		user.lastlogin = datetime.now()
		user.status = UserStatus.chatting
		# 頻繁な書き込みを避けるため、ここでは save_file() しない
		return session_id

	@_locked
	def has_session(self, session_id: str) -> bool:
		return session_id in self.sessions or session_id in self.conversations

	@_locked
	def is_session_open(self, session_id: str) -> bool:
		"""closed でない（会話を続けられる）セッションか。"""
		conv = self.conversations.get(session_id)
		return conv is not None and conv.status != ChatStatus.closed

	@_locked
	def has_user_session(self, user_id: str, session_id: str) -> bool:
		"""
		session_id が user_id の所有物か。
		Conversation.user_id を正とする（User 側のリストは改ざんされうるため）。
		"""
		conv = self.conversations.get(session_id)
		return conv is not None and conv.user_id == user_id

	@_locked
	def get_history(self, session_id: str) -> List[BaseMessage]:
		if session_id in self.sessions:
			return list(self.sessions[session_id])
		conv = self.conversations.get(session_id)
		return self._messages_from_conv(conv) if conv else []

	@_locked
	def update_history(self, session_id: str, history: List[BaseMessage]) -> None:
		"""メモリ上の履歴を更新し、最終アクセス時刻を記録する。"""
		self.sessions[session_id] = history
		conv = self.conversations.get(session_id)
		if conv:
			conv.last_accessed = datetime.now()
			if conv.status != ChatStatus.active:
				conv.status = ChatStatus.active

	def _flush_history(self, session_id: str) -> Optional[Conversation]:
		"""in-memory の履歴を Conversation.messages に書き出し、メモリから解放する（要ロック）。"""
		conv = self.conversations.get(session_id)
		if session_id in self.sessions:
			history = self.sessions.pop(session_id)
			if conv is None:
				conv = Conversation(**{"_id": session_id, "user_id": "", "messages": []})
				self.conversations[session_id] = conv
			conv.messages = messages_to_dict(history)
		return conv

	def _close_session_locked(self, session_id: str) -> None:
		conv = self._flush_history(session_id)
		if conv is None:
			raise KeyError("Session not found")
		conv.status = ChatStatus.closed

		user = self.users.get(conv.user_id)
		if user:
			if user.active_session == session_id:
				user.active_session = None
			if session_id not in user.old_session:
				user.old_session.append(session_id)
			user.status = UserStatus.logout

	@_locked
	def close_session(self, session_id: str) -> None:
		"""
		セッションをクローズして永続化する。
		summary/ai_insight の生成は generate_summary_and_insights で別途行う。
		"""
		self._close_session_locked(session_id)
		self.save_file()

	@_locked
	def pause_session(self, session_id: str) -> None:
		"""アクティブセッションを一時停止して保存する（サーバー終了時用）。"""
		if session_id not in self.sessions:
			return
		conv = self._flush_history(session_id)
		conv.status = ChatStatus.pause
		self.save_file()
		logger.info(f"[SUCCESS] Session paused: {session_id}")

	@_locked
	def active_session_ids(self) -> List[str]:
		return list(self.sessions.keys())

	@_locked
	def conversation_status(self, session_id: str) -> Optional[ChatStatus]:
		conv = self.conversations.get(session_id)
		return conv.status if conv else None

	def generate_summary_and_insights(self, session_id: str) -> None:
		"""
		セッションの要約とai_insightsを1回のLLM呼び出しで生成する（BackgroundTasks / タイムアウト監視から呼ばれる）。
		LLM 呼び出しはロック外で行い、結果の反映だけロック内で行う。
		ユーザーの learning_enabled が False なら LLM を呼ばず、何も更新しない。
		"""
		logger.info(f"[INFO] [BackgroundTask] Starting summary/ai_insights generation: session_id={session_id}")
		try:
			with self._lock:
				conv = self.conversations.get(session_id)
				if not conv:
					logger.warning(f"[WARNING] [BackgroundTask] Session not found: {session_id}")
					return
				# まだメモリ上にある場合（pause 前など）はそちらを優先
				history_objs = list(self.sessions.get(session_id) or self._messages_from_conv(conv))
				user = self.users.get(conv.user_id)
				existing_insights = (user.ai_insights if user else "") or ""
				learning_enabled = user.learning_enabled if user else True

			if not learning_enabled:
				logger.info(f"[INFO] [BackgroundTask] Learning disabled for user, skipped: {session_id}")
				return

			if not history_objs:
				logger.info(f"[INFO] [BackgroundTask] Empty conversation, skipped: {session_id}")
				return

			if not PROMPT_SUMMARY_AND_INSIGHT.exists():
				logger.warning(f"[WARNING] [BackgroundTask] summary_and_insight prompt not found: {PROMPT_SUMMARY_AND_INSIGHT}")
				return

			conversation_text = "".join(f"{m.type}: {m.content}\n\n" for m in history_objs)
			message = f"""**既存のAI Insights:**
```
{existing_insights or "（なし）"}
```

**今回の会話履歴:**
```
{conversation_text}
```
"""
			result = summary_function(str(PROMPT_SUMMARY_AND_INSIGHT), message)
			summary_text, new_insights = parse_summary_and_insights(result)
			if not summary_text:
				logger.warning("[WARNING] [BackgroundTask] Summary generation failed; keeping existing data")
				return
			if user and new_insights is None:
				logger.warning("[WARNING] [BackgroundTask] ai_insights not found in result; keeping existing insights")

			with self._lock:
				conv.summary = summary_text
				if user and new_insights is not None:
					user.ai_insights = new_insights
				self.save_file()
			logger.info(f"[SUCCESS] [BackgroundTask] Completed: session_id={session_id}")
		except Exception as e:
			logger.error(f"[ERROR] [BackgroundTask] Error: {e}", exc_info=True)

	def check_user_timeout(self) -> List[str]:
		"""
		lastlogin から SESSION_TIMEOUT 秒以上操作のないユーザーのセッションを close する。
		履歴を保存してから要約を生成する（以前は履歴を保存せずに捨てていた）。
		"""
		timeout_threshold = datetime.now() - timedelta(seconds=SESSION_TIMEOUT)
		closed_sessions = []

		with self._lock:
			for user_id, user in self.users.items():
				if user.status == UserStatus.logout or user.lastlogin >= timeout_threshold:
					continue
				for session_id, conv in self.conversations.items():
					if conv.user_id == user_id and conv.status in (ChatStatus.active, ChatStatus.pause):
						logger.info(f"[INFO] User timeout: {user_id}, closing session: {session_id}")
						closed_sessions.append(session_id)
				user.status = UserStatus.logout
				logger.info(f"[INFO] User timeout: {user_id}, status set to logout")

			for session_id in closed_sessions:
				self._close_session_locked(session_id)
			if closed_sessions:
				self.save_file()

		# 要約はロック外で（LLM 呼び出しのため）
		for session_id in closed_sessions:
			self.generate_summary_and_insights(session_id)

		return closed_sessions

	@_locked
	def resume_session(self, session_id: str) -> None:
		"""pause状態のセッションをactiveに戻す。"""
		conv = self.conversations.get(session_id)
		if conv and conv.status == ChatStatus.pause:
			conv.status = ChatStatus.active
			conv.last_accessed = datetime.now()
			if session_id not in self.sessions:
				self.sessions[session_id] = self._messages_from_conv(conv)
			logger.info(f"[INFO] Session resumed: {session_id}")
