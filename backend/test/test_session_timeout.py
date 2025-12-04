#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
セッションタイムアウト機能のテストスクリプト
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import time

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

def test_user_timeout():
	"""ユーザータイムアウトのテスト（ユーザー単位）"""
	print("\n" + "=" * 60)
	print("  ユーザータイムアウトテスト")
	print("=" * 60)
	
	try:
		from backend.api.datastore import DataStore, SESSION_TIMEOUT
		from backend.api.models import Personal, ChatStatus
		
		# DataStore初期化
		ds = DataStore()
		
		# テストユーザー作成
		print("\n[TEST] ユーザー作成...")
		user_id = "test_timeout_user_001"
		personal = Personal(name="Timeout User", gender="male", age=25)
		user = ds.create_user(user_id, personal)
		print(f"[SUCCESS] ユーザー作成: {user_id}")
		print(f"  lastlogin: {user.lastlogin}")
		
		# セッション作成
		print("\n[TEST] セッション作成...")
		session_id = ds.create_session(user_id)
		assert session_id in ds.sessions
		assert session_id in ds.conversations
		conv = ds.conversations[session_id]
		assert conv.status == ChatStatus.active
		print(f"[SUCCESS] セッション作成: {session_id}")
		print(f"  最終アクセス時刻: {conv.last_accessed}")
		
		# lastloginを古い時刻に設定（タイムアウトをシミュレート）
		print("\n[TEST] lastloginを古い時刻に設定...")
		old_time = datetime.now() - timedelta(seconds=SESSION_TIMEOUT + 100)
		user.lastlogin = old_time
		print(f"  設定した時刻: {old_time}")
		print(f"  タイムアウト閾値: {datetime.now() - timedelta(seconds=SESSION_TIMEOUT)}")
		
		# タイムアウトチェック（ユーザー単位）
		print("\n[TEST] タイムアウトチェック（ユーザー単位）...")
		closed_sessions = ds.check_user_timeout()
		assert session_id in closed_sessions
		assert session_id not in ds.sessions  # メモリから削除されている
		assert user_id not in ds.users  # ユーザーもメモリから削除されている
		# conversationsには残っている（ディスクに保存）
		assert session_id in ds.conversations
		conv = ds.conversations[session_id]
		assert conv.status == ChatStatus.closed  # closed状態になっている
		print(f"[SUCCESS] ユーザーがタイムアウト: {user_id}")
		print(f"  クローズしたセッション数: {len(closed_sessions)}")
		print(f"  セッションステータス: {conv.status}")
		
		return True
	except Exception as e:
		print(f"[ERROR] テストエラー: {e}")
		import traceback
		traceback.print_exc()
		return False

def test_last_accessed_update():
	"""最終アクセス時刻更新のテスト"""
	print("\n" + "=" * 60)
	print("  最終アクセス時刻更新テスト")
	print("=" * 60)
	
	try:
		from backend.api.datastore import DataStore
		from backend.api.models import Personal
		import time
		
		# DataStore初期化
		ds = DataStore()
		
		# テストユーザー作成
		print("\n[TEST] ユーザー作成...")
		user_id = "test_access_user_001"
		personal = Personal(name="Access User", gender="female", age=30)
		user = ds.create_user(user_id, personal)
		
		# セッション作成
		print("\n[TEST] セッション作成...")
		session_id = ds.create_session(user_id)
		conv = ds.conversations[session_id]
		initial_time = conv.last_accessed
		print(f"[SUCCESS] セッション作成: {session_id}")
		print(f"  初期アクセス時刻: {initial_time}")
		
		# 少し待つ
		time.sleep(1)
		
		# 履歴更新
		print("\n[TEST] 履歴更新...")
		ds.update_history(session_id, [{"role": "user", "content": "test"}])
		conv = ds.conversations[session_id]
		updated_time = conv.last_accessed
		print(f"[SUCCESS] 履歴更新")
		print(f"  更新後アクセス時刻: {updated_time}")
		
		# 最終アクセス時刻が更新されているか確認
		assert updated_time > initial_time
		print(f"[SUCCESS] 最終アクセス時刻が更新されました")
		print(f"  時間差: {(updated_time - initial_time).total_seconds()}秒")
		
		return True
	except Exception as e:
		print(f"[ERROR] テストエラー: {e}")
		import traceback
		traceback.print_exc()
		return False

def test_lastlogin_update():
	"""lastlogin更新のテスト"""
	print("\n" + "=" * 60)
	print("  lastlogin更新テスト")
	print("=" * 60)
	
	try:
		from backend.api.datastore import DataStore
		from backend.api.models import Personal
		import time
		
		# DataStore初期化
		ds = DataStore()
		
		# テストユーザー作成
		print("\n[TEST] ユーザー作成...")
		user_id = "test_login_user_001"
		personal = Personal(name="Login User", gender="female", age=30)
		user = ds.create_user(user_id, personal)
		initial_login = user.lastlogin
		print(f"[SUCCESS] ユーザー作成: {user_id}")
		print(f"  初期lastlogin: {initial_login}")
		
		# 少し待つ
		time.sleep(1)
		
		# get_user()でlastloginが更新されることを確認
		print("\n[TEST] get_user()でlastlogin更新...")
		user = ds.get_user(user_id)
		updated_login = user.lastlogin
		print(f"[SUCCESS] get_user()実行")
		print(f"  更新後lastlogin: {updated_login}")
		
		# lastloginが更新されているか確認
		assert updated_login > initial_login
		print(f"[SUCCESS] lastloginが更新されました")
		print(f"  時間差: {(updated_login - initial_login).total_seconds()}秒")
		
		return True
	except Exception as e:
		print(f"[ERROR] テストエラー: {e}")
		import traceback
		traceback.print_exc()
		return False


def test_timeout_settings():
	"""タイムアウト設定のテスト"""
	print("\n" + "=" * 60)
	print("  タイムアウト設定テスト")
	print("=" * 60)
	
	try:
		from backend.api.datastore import SESSION_TIMEOUT
		
		print("\n[TEST] タイムアウト設定確認...")
		print(f"[SUCCESS] SESSION_TIMEOUT: {SESSION_TIMEOUT}秒")
		print(f"  = {SESSION_TIMEOUT // 60}分")
		
		assert SESSION_TIMEOUT > 0
		print(f"[SUCCESS] タイムアウト時間が正しく設定されています")
		
		return True
	except Exception as e:
		print(f"[ERROR] テストエラー: {e}")
		import traceback
		traceback.print_exc()
		return False

def main():
	"""メインテスト"""
	print("\n" + "🚀" * 30)
	print("  ユーザータイムアウト機能テスト開始")
	print("🚀" * 30)
	
	results = []
	
	# テスト実行
	results.append(("タイムアウト設定テスト", test_timeout_settings()))
	results.append(("lastlogin更新テスト", test_lastlogin_update()))
	results.append(("ユーザータイムアウトテスト", test_user_timeout()))
	
	# 結果サマリー
	print("\n" + "=" * 60)
	print("  テスト結果サマリー")
	print("=" * 60)
	
	passed = sum(1 for _, result in results if result)
	total = len(results)
	
	for name, result in results:
		status = "[PASS]" if result else "[FAIL]"
		print(f"{status} {name}")
	
	print("\n" + "=" * 60)
	print(f"  合計: {passed}/{total} テスト成功")
	print("=" * 60)
	
	if passed == total:
		print("\n" + "🎉" * 30)
		print("  すべてのテストが成功しました！")
		print("🎉" * 30)
		return 0
	else:
		print("\n" + "❌" * 30)
		print(f"  {total - passed}個のテストが失敗しました")
		print("❌" * 30)
		return 1

if __name__ == "__main__":
	sys.exit(main())
