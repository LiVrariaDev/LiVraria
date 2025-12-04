#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Firebase Custom Tokenを使った統合テスト
"""

import requests
import json
import time
import os
from pathlib import Path

# Firebase Admin SDK
import firebase_admin
from firebase_admin import credentials, auth

BASE_URL = "http://localhost:8000"

# Firebase初期化
from dotenv import load_dotenv

# .envをLiVrariaルートから読み込む
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

FIREBASE_KEY_PATH_ENV = os.getenv("FIREBASE_ACCOUNT_KEY_PATH", "firebase-key.json")
FIREBASE_KEY_PATH = Path(__file__).resolve().parent.parent / "api" / FIREBASE_KEY_PATH_ENV

def init_firebase():
	"""Firebase Admin SDKを初期化"""
	if not FIREBASE_KEY_PATH.exists():
		print(f"❌ Firebase key file not found: {FIREBASE_KEY_PATH}")
		print("⚠️ このテストにはFirebase Admin SDKが必要です")
		return False
	
	try:
		# 既に初期化されているか確認
		firebase_admin.get_app()
		print("✅ Firebase already initialized")
	except ValueError:
		# 初期化されていない場合は初期化
		cred = credentials.Certificate(str(FIREBASE_KEY_PATH))
		firebase_admin.initialize_app(cred)
		print("✅ Firebase initialized")
	
	return True

def create_custom_token(user_id: str) -> str:
	"""Firebase Custom Tokenを生成"""
	try:
		custom_token = auth.create_custom_token(user_id)
		return custom_token.decode('utf-8')
	except Exception as e:
		print(f"❌ Custom token creation failed: {e}")
		return None

def exchange_custom_token_for_id_token(custom_token: str) -> str:
	"""Custom TokenをID Tokenに交換"""
	# Firebase API Key（環境変数から取得）
	api_key = os.getenv("FIREBASE_API_KEY")
	if not api_key:
		print("❌ FIREBASE_API_KEY not found in environment variables")
		print("⚠️ .envファイルにFIREBASE_API_KEYを追加してください")
		return None
	
	url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={api_key}"
	payload = {
		"token": custom_token,
		"returnSecureToken": True
	}
	
	try:
		response = requests.post(url, json=payload)
		response.raise_for_status()
		data = response.json()
		id_token = data.get('idToken')
		print(f"✅ ID Token取得成功: {id_token[:50]}...")
		return id_token
	except Exception as e:
		print(f"❌ ID Token exchange failed: {e}")
		if hasattr(e, 'response') and e.response is not None:
			print(f"   Response: {e.response.text}")
		return None

def print_section(title):
	"""セクションタイトルを表示"""
	print("\n" + "=" * 60)
	print(f"  {title}")
	print("=" * 60)

def print_result(success, message):
	"""テスト結果を表示"""
	status = "✅" if success else "❌"
	print(f"{status} {message}")

def test_create_user(token: str, user_id: str):
	"""ユーザー作成テスト"""
	print_section("1. ユーザー作成")
	
	params = {
		"name": "Test User",
		"gender": "male",
		"age": 25,
		"live_pref": "東京都",
		"live_city": "新宿区"
	}
	
	headers = {
		"Authorization": f"Bearer {token}"
	}
	
	try:
		response = requests.post(f"{BASE_URL}/users", params=params, headers=headers)
		response.raise_for_status()
		data = response.json()
		print(f"ユーザーID: {user_id}")
		print(f"レスポンス: {data.get('detail', 'N/A')}")
		print_result(True, "ユーザー作成成功")
		return True
	except Exception as e:
		print_result(False, f"エラー: {e}")
		return False

def test_get_user(token: str, user_id: str):
	"""ユーザー情報取得テスト"""
	print_section("2. ユーザー情報取得")
	
	headers = {
		"Authorization": f"Bearer {token}"
	}
	
	try:
		response = requests.get(f"{BASE_URL}/users/{user_id}", headers=headers)
		response.raise_for_status()
		data = response.json()
		print(f"ユーザーID: {data.get('user_id', 'N/A')}")
		print(f"名前: {data.get('personal', {}).get('name', 'N/A')}")
		print(f"ステータス: {data.get('status', 'N/A')}")
		print_result(True, "ユーザー情報取得成功")
		return True
	except Exception as e:
		print_result(False, f"エラー: {e}")
		return False

def test_chat(token: str, user_id: str):
	"""チャットテスト"""
	print_section("3. チャット送信")
	
	headers = {
		"Authorization": f"Bearer {token}"
	}
	
	# 1回目のチャット
	payload = {
		"user_id": user_id,
		"message": "こんにちは"
	}
	
	try:
		response = requests.post(f"{BASE_URL}/sessions/new/messages", json=payload, headers=headers)
		response.raise_for_status()
		data = response.json()
		session_id = data.get('session_id')
		print(f"📨 送信: {payload['message']}")
		print(f"🤖 応答: {data.get('response', '')[:100]}...")
		print(f"セッションID: {session_id}")
		print_result(True, "チャット送信成功")
		
		# 2回目のチャット（同じセッション）
		time.sleep(1)
		payload2 = {
			"user_id": user_id,
			"message": "おすすめの本を教えてください"
		}
		response2 = requests.post(f"{BASE_URL}/sessions/{session_id}/messages", json=payload2, headers=headers)
		response2.raise_for_status()
		data2 = response2.json()
		print(f"\n📨 送信: {payload2['message']}")
		print(f"🤖 応答: {data2.get('response', '')[:100]}...")
		print_result(True, "チャット継続成功")
		
		return session_id
	except Exception as e:
		print_result(False, f"エラー: {e}")
		return None

def test_get_session(token: str, user_id: str, session_id: str):
	"""セッション取得テスト"""
	print_section("4. セッション情報取得")
	
	headers = {
		"Authorization": f"Bearer {token}"
	}
	
	try:
		response = requests.get(f"{BASE_URL}/sessions/{session_id}", params={"user_id": user_id}, headers=headers)
		response.raise_for_status()
		data = response.json()
		print(f"セッションID: {session_id}")
		print(f"ステータス: {data.get('status', 'N/A')}")
		print(f"履歴件数: {len(data.get('history', []))} 件")
		print_result(True, "セッション情報取得成功")
		return True
	except Exception as e:
		print_result(False, f"エラー: {e}")
		return False

def test_close_session(token: str, user_id: str, session_id: str):
	"""セッションクローズテスト"""
	print_section("5. セッションクローズ")
	
	headers = {
		"Authorization": f"Bearer {token}"
	}
	
	try:
		response = requests.put(f"{BASE_URL}/sessions/{session_id}/close", params={"user_id": user_id}, headers=headers)
		response.raise_for_status()
		print_result(True, "セッションクローズ成功")
		
		# バックグラウンドタスクの完了を待つ
		print("\n⏳ バックグラウンドタスク（summary/ai_insights生成）の完了を待機中...")
		time.sleep(10)
		print("✅ 待機完了")
		return True
	except Exception as e:
		print_result(False, f"エラー: {e}")
		return False

def main():
	"""メインテスト"""
	print("\n" + "🚀" * 30)
	print("  Firebase Custom Token統合テスト開始")
	print("🚀" * 30)
	
	# Firebase初期化
	if not init_firebase():
		print("\n❌ Firebase初期化に失敗したため、テストを中断します")
		return 1
	
	# テストユーザーID
	user_id = f"test_user_{int(time.time())}"
	print(f"\n📝 テストユーザーID: {user_id}")
	
	# Custom Token生成
	print("\n🔑 Firebase Custom Token生成中...")
	custom_token = create_custom_token(user_id)
	if not custom_token:
		print("\n❌ Custom Token生成に失敗したため、テストを中断します")
		return 1
	print(f"✅ Custom Token生成成功: {custom_token[:50]}...")
	
	# Custom TokenをID Tokenに交換
	print("\n🔄 Custom TokenをID Tokenに交換中...")
	id_token = exchange_custom_token_for_id_token(custom_token)
	if not id_token:
		print("\n❌ ID Token取得に失敗したため、テストを中断します")
		return 1
	
	results = []
	
	# 1. ユーザー作成
	results.append(("ユーザー作成", test_create_user(id_token, user_id)))
	
	# 2. ユーザー情報取得
	results.append(("ユーザー情報取得", test_get_user(id_token, user_id)))
	
	# 3. チャット
	session_id = test_chat(id_token, user_id)
	if not session_id:
		print("\n❌ チャットに失敗したため、テストを中断します")
		return 1
	results.append(("チャット", True))
	
	# 4. セッション情報取得
	results.append(("セッション情報取得", test_get_session(id_token, user_id, session_id)))
	
	# 5. セッションクローズ
	results.append(("セッションクローズ", test_close_session(id_token, user_id, session_id)))
	
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
	import sys
	sys.exit(main())
