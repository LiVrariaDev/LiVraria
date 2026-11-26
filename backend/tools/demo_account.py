"""デモ/ショーケースアカウント用の管理スクリプト。

使い方:
	python -m backend.tools.demo_account show <user_id>
	python -m backend.tools.demo_account learning <user_id> on|off
	python -m backend.tools.demo_account set-insights <user_id> <file>

注意: バックエンドの停止中に使うこと。稼働中に実行すると、
バックエンドの次の保存で変更が上書きされる。
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from backend import USERS_FILE
from backend.api.datastore import _atomic_write_json, _load_json
from backend.api.models import User


def _load_users() -> list[User]:
	return [User.model_validate(raw) for raw in _load_json(USERS_FILE, [])]


def _save_users(users: list[User]) -> None:
	# datastore.save_file と同じ保存形式
	_atomic_write_json(USERS_FILE, [u.model_dump(by_alias=True) for u in users])


def _find(users: list[User], user_id: str) -> Optional[User]:
	return next((u for u in users if u.user_id == user_id), None)


def main(argv: Optional[list[str]] = None) -> int:
	parser = argparse.ArgumentParser(
		prog="demo_account",
		description="デモ/ショーケースアカウントの管理。バックエンドの停止中に使うこと"
		"(稼働中に実行すると、バックエンドの次の保存で上書きされる)。",
	)
	sub = parser.add_subparsers(dest="command", required=True)

	p_show = sub.add_parser("show", help="ユーザーの状態を表示する")
	p_show.add_argument("user_id")

	p_learning = sub.add_parser("learning", help="学習(要約と AI Insights の更新)の on/off を切り替える")
	p_learning.add_argument("user_id")
	p_learning.add_argument("state", choices=["on", "off"])

	p_set = sub.add_parser("set-insights", help="ファイルの中身(UTF-8)で ai_insights を置き換える")
	p_set.add_argument("user_id")
	p_set.add_argument("file")

	args = parser.parse_args(argv)

	users = _load_users()
	user = _find(users, args.user_id)
	if user is None:
		print(f"ユーザーが見つかりません: {args.user_id}", file=sys.stderr)
		return 1

	if args.command == "show":
		print(f"user_id: {user.user_id}")
		print(f"name: {user.personal.name}")
		print(f"learning_enabled: {user.learning_enabled}")
		print(f"ai_insights: {user.ai_insights[:200]}")
	elif args.command == "learning":
		user.learning_enabled = args.state == "on"
		_save_users(users)
		print(f"learning_enabled を {user.learning_enabled} にしました: {user.user_id}")
	elif args.command == "set-insights":
		user.ai_insights = Path(args.file).read_text(encoding="utf-8")
		_save_users(users)
		print(f"ai_insights を置き換えました: {user.user_id}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
