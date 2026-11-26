"""会話の1ターンごとのトレース(LLM のノード単位の処理内容)の記録と、ログへの trace_id 付与。

LIVRARIA_DEBUG=true のときだけ記録する。トレースには全利用者の発言が入るため、
参照は管理者キーで保護された /debug/* API からのみ行う。
"""

import collections
import contextvars
import json
import logging
import os
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend import DATA_DIR

logger = logging.getLogger("uvicorn.error")

# 現在処理中のターンの trace_id。chat_prompt が設定する。
current_trace_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_trace_id", default=None)

_MARK_ATTR = "_trace_prefixed"


class TraceIdFilter(logging.Filter):
	"""current_trace_id があれば、ログのメッセージの先頭に "[trace=<先頭8文字>] " を付ける。"""

	def filter(self, record: logging.LogRecord) -> bool:
		tid = current_trace_id.get()
		if tid:
			record.trace_id = tid
			if not getattr(record, _MARK_ATTR, False):
				record.msg = f"[trace={tid[:8]}] {record.msg}"
				setattr(record, _MARK_ATTR, True)
		return True


def install_log_filter(logger_name: str = "uvicorn.error") -> None:
	"""指定のロガーに TraceIdFilter を1回だけ追加する。"""
	target = logging.getLogger(logger_name)
	if not any(isinstance(f, TraceIdFilter) for f in target.filters):
		target.addFilter(TraceIdFilter())


@dataclass
class TraceStep:
	index: int
	node: str                  # "agent" / "tools" / "force_tool"
	attempt: int               # llm_chat のリトライ回数(0 から)
	started_at: str
	ended_at: str
	duration_ms: int
	ai_text: Optional[str] = None
	tool_calls: list = field(default_factory=list)    # [{"name", "args"}]
	tool_results: list = field(default_factory=list)  # [{"name", "content"}]
	usage: Optional[dict] = None
	error: Optional[dict] = None                      # {"type", "message", "traceback"}


@dataclass
class TurnTrace:
	trace_id: str
	session_id: Optional[str]
	user_id: Optional[str]
	started_at: str
	ended_at: Optional[str]
	user_message: str
	response_text: Optional[str] = None
	expression: Optional[str] = None
	recommended_count: int = 0
	failed: bool = False
	error: Optional[dict] = None
	steps: list = field(default_factory=list)


def _now() -> str:
	return datetime.now().isoformat()


class TraceStore:
	def __init__(self, data_dir: Path, limit: int):
		self.data_dir = Path(data_dir)
		self.limit = limit
		self._turns: collections.deque = collections.deque(maxlen=limit)
		self._lock = threading.Lock()

	def start_turn(self, trace_id: str, session_id: Optional[str], user_id: Optional[str], user_message: str) -> TurnTrace:
		return TurnTrace(
			trace_id=trace_id,
			session_id=session_id,
			user_id=user_id,
			started_at=_now(),
			ended_at=None,
			user_message=user_message,
		)

	def finish_turn(self, turn: TurnTrace) -> None:
		"""ended_at を設定し、メモリと JSONL に保存する。"""
		turn.ended_at = _now()
		with self._lock:
			self._turns.append(turn)
			try:
				traces_dir = self.data_dir / "traces"
				traces_dir.mkdir(parents=True, exist_ok=True)
				path = traces_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
				with open(path, "a", encoding="utf-8") as f:
					f.write(json.dumps(asdict(turn), ensure_ascii=False, default=str) + "\n")
			except Exception:
				logger.exception("Failed to write trace JSONL")

	def list_sessions(self) -> list[dict]:
		"""新しい順のセッション一覧。"""
		with self._lock:
			turns = list(self._turns)
		sessions: dict = {}
		for turn in turns:
			key = turn.session_id
			last = turn.ended_at or turn.started_at
			item = sessions.get(key)
			if item is None:
				sessions[key] = {"session_id": key, "user_id": turn.user_id, "turns": 1, "last_at": last}
			else:
				item["turns"] += 1
				if last > item["last_at"]:
					item["last_at"] = last
		return sorted(sessions.values(), key=lambda s: s["last_at"], reverse=True)

	def list_turns(self, session_id) -> list[dict]:
		"""古い順のターン一覧。"""
		with self._lock:
			turns = [t for t in self._turns if t.session_id == session_id]
		return [
			{
				"trace_id": t.trace_id,
				"started_at": t.started_at,
				"user_message": t.user_message,
				"response_text": t.response_text,
				"failed": t.failed,
				"nodes": [step.node for step in t.steps],
			}
			for t in turns
		]

	def get_turn(self, trace_id: str) -> Optional[dict]:
		with self._lock:
			for turn in self._turns:
				if turn.trace_id == trace_id:
					return asdict(turn)
		return None


# 現在処理中のターン。chat_prompt が設定し、llm_chat が読む。
current_turn: contextvars.ContextVar[Optional[TurnTrace]] = contextvars.ContextVar("current_turn", default=None)

_store: Optional[TraceStore] = None
_store_lock = threading.Lock()


def debug_enabled() -> bool:
	return os.getenv("LIVRARIA_DEBUG", "false").lower() == "true"


def get_trace_store() -> Optional[TraceStore]:
	"""LIVRARIA_DEBUG が true のときだけ生成する(遅延生成のシングルトン)。"""
	global _store
	if not debug_enabled():
		return None
	with _store_lock:
		if _store is None:
			try:
				limit = int(os.getenv("LIVRARIA_TRACE_LIMIT", "500"))
			except ValueError:
				limit = 500
			_store = TraceStore(DATA_DIR, max(limit, 1))
		return _store


def reset_trace_store() -> None:
	"""テスト用。"""
	global _store
	with _store_lock:
		_store = None
