#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NFC認証機能のテストスクリプト
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

def test_nfc_methods():
	"""NFC関連メソッドのテスト"""
	print("\n" + "=" * 60)
	print("  NFC関連メソッドのテスト")
	print("=" * 60)
	
	try:
		from backend.api.datastore import DataStore
		from backend.api.models import Personal
		
		# DataStore初期化
		ds = DataStore()
		
		# テストユーザー作成
		print("\n[TEST] ユーザー作成...")
		user_id = "test_nfc_user_001"
		personal = Personal(name="Test User", gender="male", age=25)
		user = ds.create_user(user_id, personal)
		print(f"[SUCCESS] ユーザー作成: {user_id}")
		
		# NFC登録
		print("\n[TEST] NFC登録...")
		nfc_id = "nfc_test_12345"
		nfc_user = ds.register_nfc(nfc_id, user_id)
		assert nfc_user.nfc_id == nfc_id
		assert nfc_user.user_id == user_id
		print(f"[SUCCESS] NFC登録: {nfc_id} -> {user_id}")
		
		# NFC IDからユーザーID取得
		print("\n[TEST] NFC IDからユーザーID取得...")
		retrieved_user_id = ds.get_user_by_nfc(nfc_id)
		assert retrieved_user_id == user_id
		print(f"[SUCCESS] ユーザーID取得: {nfc_id} -> {retrieved_user_id}")
		
		# 未登録のNFC ID
		print("\n[TEST] 未登録のNFC ID...")
		unknown_nfc = "unknown_nfc_99999"
		retrieved_user_id = ds.get_user_by_nfc(unknown_nfc)
		assert retrieved_user_id is None
		print(f"[SUCCESS] 未登録のNFC IDはNoneを返す")
		
		# NFC登録解除
		print("\n[TEST] NFC登録解除...")
		ds.unregister_nfc(nfc_id)
		retrieved_user_id = ds.get_user_by_nfc(nfc_id)
		assert retrieved_user_id is None
		print(f"[SUCCESS] NFC登録解除: {nfc_id}")
		
		# 存在しないユーザーへのNFC登録（エラー）
		print("\n[TEST] 存在しないユーザーへのNFC登録...")
		try:
			ds.register_nfc("nfc_error", "nonexistent_user")
			print("[FAIL] エラーが発生しませんでした")
			return False
		except KeyError as e:
			print(f"[SUCCESS] 正しくエラーが発生: {e}")
		
		return True
	except Exception as e:
		print(f"[ERROR] テストエラー: {e}")
		import traceback
		traceback.print_exc()
		return False

def test_nfc_persistence():
	"""NFC データの永続化テスト"""
	print("\n" + "=" * 60)
	print("  NFC データ永続化テスト")
	print("=" * 60)
	
	try:
		from backend.api.datastore import DataStore
		from backend.api.models import Personal
		import os
		
		# データファイルのパス
		nfc_file = Path("/home/kaerunomoto/school/LiVraria/backend/api/data/nfc_users.json")
		
		# DataStore初期化
		ds = DataStore()
		
		# テストユーザー作成
		print("\n[TEST] ユーザー作成...")
		user_id = "test_nfc_persist_001"
		personal = Personal(name="Persist User", gender="female", age=30)
		user = ds.create_user(user_id, personal)
		
		# NFC登録
		print("\n[TEST] NFC登録と保存...")
		nfc_id = "nfc_persist_67890"
		ds.register_nfc(nfc_id, user_id)
		
		# ファイルが作成されたか確認
		assert nfc_file.exists(), "nfc_users.jsonが作成されていません"
		print(f"[SUCCESS] nfc_users.jsonが作成されました")
		
		# 新しいDataStoreインスタンスで読み込み
		print("\n[TEST] データの再読み込み...")
		ds2 = DataStore()
		retrieved_user_id = ds2.get_user_by_nfc(nfc_id)
		assert retrieved_user_id == user_id
		print(f"[SUCCESS] データが正しく永続化されています: {nfc_id} -> {retrieved_user_id}")
		
		# クリーンアップ
		ds2.unregister_nfc(nfc_id)
		
		return True
	except Exception as e:
		print(f"[ERROR] 永続化テストエラー: {e}")
		import traceback
		traceback.print_exc()
		return False

def test_nfc_endpoints():
	"""NFC エンドポイントの存在確認"""
	print("\n" + "=" * 60)
	print("  NFC エンドポイント確認")
	print("=" * 60)
	
	try:
		from backend.api.server import app
		
		print("\n[TEST] エンドポイントの確認...")
		routes = [route.path for route in app.routes]
		
		expected_routes = [
			"/nfc/auth",
			"/nfc/register",
			"/nfc/unregister"
		]
		
		for route in expected_routes:
			assert route in routes, f"エンドポイント {route} が見つかりません"
			print(f"[SUCCESS] エンドポイント存在: {route}")
		
		return True
	except Exception as e:
		print(f"[ERROR] エンドポイント確認エラー: {e}")
		import traceback
		traceback.print_exc()
		return False

def main():
	"""メインテスト"""
	print("\n" + "🚀" * 30)
	print("  NFC認証機能テスト開始")
	print("🚀" * 30)
	
	results = []
	
	# テスト実行
	results.append(("NFC関連メソッドテスト", test_nfc_methods()))
	results.append(("NFCデータ永続化テスト", test_nfc_persistence()))
	results.append(("NFCエンドポイント確認", test_nfc_endpoints()))
	
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
