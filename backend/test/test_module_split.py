#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
モジュール分割後の動作確認テスト
models.py, datastore.py, server.pyが正しくインポートできるかテスト
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
	"""モジュールのインポートテスト"""
	print("\n" + "=" * 60)
	print("  モジュールインポートテスト")
	print("=" * 60)
	
	try:
		# models.pyのインポート
		print("\n[TEST] models.pyのインポート...")
		from backend.api.models import (
			ChatStatus, UserStatus, ChatRequest, ChatResponse,
			Message, User, Conversation, Personal
		)
		print("[SUCCESS] models.py: すべてのクラスをインポート成功")
		
		# datastore.pyのインポート
		print("\n[TEST] datastore.pyのインポート...")
		from backend.api.datastore import DataStore
		print("[SUCCESS] datastore.py: DataStoreクラスをインポート成功")
		
		# server.pyのインポート
		print("\n[TEST] server.pyのインポート...")
		from backend.api.server import Server, app
		print("[SUCCESS] server.py: Serverクラスとappをインポート成功")
		
		return True
	except Exception as e:
		print(f"[ERROR] インポートエラー: {e}")
		import traceback
		traceback.print_exc()
		return False

def test_enum_values():
	"""Enumの値テスト"""
	print("\n" + "=" * 60)
	print("  Enum値テスト")
	print("=" * 60)
	
	try:
		from backend.api.models import ChatStatus, UserStatus
		
		# ChatStatus
		print("\n[TEST] ChatStatus...")
		assert ChatStatus.active == "active"
		assert ChatStatus.pause == "pause"
		assert ChatStatus.closed == "closed"
		print("[SUCCESS] ChatStatus: すべての値が正しい")
		
		# UserStatus
		print("\n[TEST] UserStatus...")
		assert UserStatus.activate == "activate"
		assert UserStatus.logout == "logout"
		assert UserStatus.chatting == "chatting"
		print("[SUCCESS] UserStatus: すべての値が正しい")
		
		return True
	except Exception as e:
		print(f"[ERROR] Enumテストエラー: {e}")
		import traceback
		traceback.print_exc()
		return False

def test_pydantic_models():
	"""Pydanticモデルのインスタンス化テスト"""
	print("\n" + "=" * 60)
	print("  Pydanticモデルテスト")
	print("=" * 60)
	
	try:
		from backend.api.models import (
			ChatRequest, ChatResponse, Message, Personal, User, Conversation
		)
		
		# ChatRequest
		print("\n[TEST] ChatRequest...")
		req = ChatRequest(message="test message", session_id="test-session")
		assert req.message == "test message"
		assert req.session_id == "test-session"
		print("[SUCCESS] ChatRequest: インスタンス化成功")
		
		# ChatResponse
		print("\n[TEST] ChatResponse...")
		res = ChatResponse(response="test response", session_id="test-session")
		assert res.response == "test response"
		assert res.session_id == "test-session"
		print("[SUCCESS] ChatResponse: インスタンス化成功")
		
		# Message
		print("\n[TEST] Message...")
		msg = Message(role="user", content="test content")
		assert msg.role == "user"
		assert msg.content == "test content"
		print("[SUCCESS] Message: インスタンス化成功")
		
		# Personal
		print("\n[TEST] Personal...")
		personal = Personal(name="Test User", gender="male", age=25)
		assert personal.name == "Test User"
		assert personal.gender == "male"
		assert personal.age == 25
		print("[SUCCESS] Personal: インスタンス化成功")
		
		return True
	except Exception as e:
		print(f"[ERROR] Pydanticモデルテストエラー: {e}")
		import traceback
		traceback.print_exc()
		return False

def test_datastore_initialization():
	"""DataStoreの初期化テスト"""
	print("\n" + "=" * 60)
	print("  DataStore初期化テスト")
	print("=" * 60)
	
	try:
		from backend.api.datastore import DataStore
		
		print("\n[TEST] DataStoreの初期化...")
		ds = DataStore()
		
		# 基本的な属性の確認
		assert hasattr(ds, 'users')
		assert hasattr(ds, 'conversations')
		assert hasattr(ds, 'sessions')
		assert isinstance(ds.users, dict)
		assert isinstance(ds.conversations, dict)
		assert isinstance(ds.sessions, dict)
		
		print("[SUCCESS] DataStore: 初期化成功、すべての属性が存在")
		
		# メソッドの存在確認
		methods = [
			'save_file', 'create_user', 'get_user', 'update_user',
			'add_recommendation', 'create_session', 'has_session',
			'has_user_session', 'get_history', 'update_history',
			'close_session', 'pause_session', 'generate_summary_and_insights'
		]
		
		print("\n[TEST] DataStoreのメソッド確認...")
		for method in methods:
			assert hasattr(ds, method), f"メソッド {method} が存在しません"
		print(f"[SUCCESS] DataStore: {len(methods)}個のメソッドが存在")
		
		return True
	except Exception as e:
		print(f"[ERROR] DataStore初期化テストエラー: {e}")
		import traceback
		traceback.print_exc()
		return False

def test_server_initialization():
	"""Serverの初期化テスト"""
	print("\n" + "=" * 60)
	print("  Server初期化テスト")
	print("=" * 60)
	
	try:
		from backend.api.server import app, server
		from fastapi import FastAPI
		
		print("\n[TEST] FastAPIアプリケーションの確認...")
		assert isinstance(app, FastAPI)
		print("[SUCCESS] app: FastAPIインスタンス")
		
		print("\n[TEST] Serverインスタンスの確認...")
		assert hasattr(server, 'app')
		assert hasattr(server, 'data_store')
		print("[SUCCESS] server: Serverインスタンス、appとdata_storeが存在")
		
		# エンドポイントの確認
		print("\n[TEST] エンドポイントの確認...")
		routes = [route.path for route in app.routes]
		expected_routes = [
			"/", "/users", "/sessions", 
			"/chat/default", "/chat/librarian", "/close_session"
		]
		
		for route in expected_routes:
			assert route in routes, f"エンドポイント {route} が見つかりません"
		print(f"[SUCCESS] エンドポイント: {len(expected_routes)}個のエンドポイントが存在")
		
		return True
	except Exception as e:
		print(f"[ERROR] Server初期化テストエラー: {e}")
		import traceback
		traceback.print_exc()
		return False

def main():
	"""メインテスト"""
	print("\n" + "🚀" * 30)
	print("  モジュール分割検証テスト開始")
	print("🚀" * 30)
	
	results = []
	
	# テスト実行
	results.append(("インポートテスト", test_imports()))
	results.append(("Enum値テスト", test_enum_values()))
	results.append(("Pydanticモデルテスト", test_pydantic_models()))
	results.append(("DataStore初期化テスト", test_datastore_initialization()))
	results.append(("Server初期化テスト", test_server_initialization()))
	
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
