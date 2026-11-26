"""LLM の役割ごとの呼び出し回数とトークン数をプロセス内に記録する。

プロセス起動からの累計をメモリに持つだけで、ファイルには保存しない。
"""

import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional


@dataclass
class RoleUsage:
	calls: int = 0            # LLM の invoke 回数(成功・失敗を含む)
	errors: int = 0           # 例外で終わった回数
	rate_limited: int = 0     # そのうち 429 だった回数
	input_tokens: int = 0
	output_tokens: int = 0
	total_tokens: int = 0


_lock = threading.Lock()
_usage: dict[str, RoleUsage] = {}
_since = datetime.now()


def is_rate_limit_error(exc: BaseException) -> bool:
	"""例外(と原因の連鎖)が Gemini の上限超過(429)か判定する。"""
	seen = set()
	current: Optional[BaseException] = exc
	for _ in range(10):
		if current is None or id(current) in seen:
			break
		seen.add(id(current))
		if getattr(current, "code", None) == 429 or getattr(current, "status_code", None) == 429:
			return True
		if "ResourceExhausted" in type(current).__name__:
			return True
		text = str(current)
		if "429" in text or "RESOURCE_EXHAUSTED" in text:
			return True
		current = current.__cause__ or current.__context__
	return False


def _get(role: str) -> RoleUsage:
	if role not in _usage:
		_usage[role] = RoleUsage()
	return _usage[role]


def record_success(role: str, message) -> None:
	"""invoke 成功を記録する。usage_metadata があればトークン数も足す。"""
	metadata = getattr(message, "usage_metadata", None)
	with _lock:
		usage = _get(role)
		usage.calls += 1
		if isinstance(metadata, dict):
			usage.input_tokens += int(metadata.get("input_tokens") or 0)
			usage.output_tokens += int(metadata.get("output_tokens") or 0)
			usage.total_tokens += int(metadata.get("total_tokens") or 0)


def record_error(role: str, exc: BaseException) -> None:
	"""invoke 失敗を記録する。429 なら rate_limited も数える。"""
	rate_limited = is_rate_limit_error(exc)
	with _lock:
		usage = _get(role)
		usage.calls += 1
		usage.errors += 1
		if rate_limited:
			usage.rate_limited += 1


def snapshot(models: Optional[dict] = None) -> dict:
	"""現在の集計を返す。models は呼び出し側が役割ごとのモデル名を渡す。"""
	with _lock:
		roles = {role: asdict(usage) for role, usage in _usage.items()}
		since = _since.isoformat()
	return {"since": since, "roles": roles, "models": dict(models or {})}


def reset() -> None:
	"""集計を空に戻す(テスト用)。"""
	global _since
	with _lock:
		_usage.clear()
		_since = datetime.now()
