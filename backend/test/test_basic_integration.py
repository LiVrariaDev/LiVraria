#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基本的な統合テスト（認証不要エンドポイント）
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def print_section(title):
	"""セクションタイトルを表示"""
	print("\n" + "=" * 60)
	print(f"  {title}")
	print("=" * 60)

def print_result(success, message):
	"""テスト結果を表示"""
	status = "✅" if success else "❌"
	print(f"{status} {message}")

def test_root():
	"""ルートエンドポイントテスト"""
	print_section("1. ルートエンドポイント")
	try:
		response = requests.get(f"{BASE_URL}/")
		response.raise_for_status()
		data = response.json()
		print(f"レスポンス: {data}")
		print_result(True, "ルートエンドポイント成功")
		return True
	except Exception as e:
		print_result(False, f"エラー: {e}")
		return False

def test_create_user():
	"""ユーザー作成テスト（認証不要）"""
	print_section("2. ユーザー作成")
	user_id = f"test_user_{int(time.time())}"
	params = {
		"user_id": user_id,
		"gender": "male",
		"age": 25,
		"live_pref": "東京都",
		"live_city": "新宿区"
	}
	
	try:
		response = requests.post(f"{BASE_URL}/users", params=params)
		response.raise_for_status()
		data = response.json()
		print(f"ユーザーID: {user_id}")
		print(f"作成日時: {data.get('created_at', 'N/A')}")
		print_result(True, "ユーザー作成成功")
		return user_id
	except Exception as e:
		print_result(False, f"エラー: {e}")
		return None

def test_chat(user_id):
	"""チャットテスト（認証不要）"""
	print_section("3. チャット送信")
	
	# 1回目のチャット
	payload = {
		"user_id": user_id,
		"message": "こんにちは"
	}
	
	try:
		response = requests.post(f"{BASE_URL}/sessions/new/messages", json=payload)
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
		response2 = requests.post(f"{BASE_URL}/sessions/{session_id}/messages", json=payload2)
		response2.raise_for_status()
		data2 = response2.json()
		print(f"\n📨 送信: {payload2['message']}")
		print(f"🤖 応答: {data2.get('response', '')[:100]}...")
		print_result(True, "チャット継続成功")
		
		return session_id
	except Exception as e:
		print_result(False, f"エラー: {e}")
		return None

def test_get_session(user_id, session_id):
	"""セッション取得テスト（認証不要）"""
	print_section("4. セッション情報取得")
	
	try:
		response = requests.get(f"{BASE_URL}/sessions/{session_id}", params={"user_id": user_id})
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

def test_close_session(user_id, session_id):
	"""セッションクローズテスト（認証不要）"""
	print_section("5. セッションクローズ")
	
	try:
		response = requests.put(f"{BASE_URL}/sessions/{session_id}/close", params={"user_id": user_id})
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
	print("  基本統合テスト開始")
	print("🚀" * 30)
	
	results = []
	
	# 1. ルートエンドポイント
	results.append(("ルートエンドポイント", test_root()))
	
	# 2. ユーザー作成
	user_id = test_create_user()
	if not user_id:
		print("\n❌ ユーザー作成に失敗したため、テストを中断します")
		return 1
	results.append(("ユーザー作成", True))
	
	# 3. チャット
	session_id = test_chat(user_id)
	if not session_id:
		print("\n❌ チャットに失敗したため、テストを中断します")
		return 1
	results.append(("チャット", True))
	
	# 4. セッション情報取得
	results.append(("セッション情報取得", test_get_session(user_id, session_id)))
	
	# 5. セッションクローズ
	results.append(("セッションクローズ", test_close_session(user_id, session_id)))
	
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
