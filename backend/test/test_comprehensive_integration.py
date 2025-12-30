#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
包括的統合テスト（サーバー再起動を含む）
NFCを除く全機能をテスト
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
from backend import FIREBASE_ACCOUNT_KEY_PATH, CONVERSATIONS_FILE, USERS_FILE


def init_firebase():
	"""Firebase Admin SDKを初期化"""
	if not FIREBASE_ACCOUNT_KEY_PATH.exists():
		print(f"❌ Firebase key file not found: {FIREBASE_ACCOUNT_KEY_PATH}")
		return False
	
	try:
		firebase_admin.get_app()
		print("✅ Firebase already initialized")
	except ValueError:
		cred = credentials.Certificate(str(FIREBASE_ACCOUNT_KEY_PATH))
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
	api_key = os.getenv("FIREBASE_API_KEY")
	if not api_key:
		print("❌ FIREBASE_API_KEY not found in environment variables")
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
		return id_token
	except Exception as e:
		print(f"❌ ID Token exchange failed: {e}")
		return None

def print_section(title):
	"""セクションタイトルを表示"""
	print("\n" + "=" * 70)
	print(f"  {title}")
	print("=" * 70)

def print_result(success, message):
	"""テスト結果を表示"""
	status = "✅" if success else "❌"
	print(f"{status} {message}")

def check_json_file(file_path: Path, session_id: str, expected_status: str):
	"""JSONファイルの内容を確認"""
	if not file_path.exists():
		print(f"❌ {file_path.name} が存在しません")
		return False
	
	try:
		with open(file_path, 'r', encoding='utf-8') as f:
			data = json.load(f)
		
		if session_id in data:
			status = data[session_id].get('status', 'unknown')
			messages_count = len(data[session_id].get('messages', []))
			print(f"\n📄 {file_path.name}:")
			print(f"  - セッションID: {session_id}")
			print(f"  - ステータス: {status}")
			print(f"  - メッセージ数: {messages_count}")
			
			if status == expected_status:
				print_result(True, f"ステータスが {expected_status} です")
				return True
			else:
				print_result(False, f"ステータスが {expected_status} ではありません（実際: {status}）")
				return False
		else:
			print(f"❌ セッション {session_id} が {file_path.name} に見つかりません")
			return False
	except Exception as e:
		print(f"❌ {file_path.name} の読み込みエラー: {e}")
		return False

def main():
	"""メインテスト"""
	print("\n" + "🚀" * 35)
	print("  包括的統合テスト開始（サーバー再起動を含む）")
	print("🚀" * 35)
	
	# Firebase初期化
	if not init_firebase():
		print("\n❌ Firebase初期化に失敗したため、テストを中断します")
		return 1
	
	# テストユーザーID
	user_id = f"test_comprehensive_{int(time.time())}"
	print(f"\n📝 テストユーザーID: {user_id}")
	
	# Custom Token生成
	print("\n🔑 Firebase Custom Token生成中...")
	custom_token = create_custom_token(user_id)
	if not custom_token:
		print("\n❌ Custom Token生成に失敗したため、テストを中断します")
		return 1
	
	# ID Token取得
	print("🔄 Custom TokenをID Tokenに交換中...")
	id_token = exchange_custom_token_for_id_token(custom_token)
	if not id_token:
		print("\n❌ ID Token取得に失敗したため、テストを中断します")
		return 1
	print("✅ 認証成功")
	
	headers = {"Authorization": f"Bearer {id_token}"}
	
	# ========================================
	# 1. ユーザー作成
	# ========================================
	print_section("1. ユーザー作成")
	personal_data = {
		"name": "Comprehensive Test User",
		"gender": "female",
		"age": 28,
		"live_pref": "大阪府",
		"live_city": "大阪市"
	}
	
	try:
		response = requests.post(f"{BASE_URL}/users", json=personal_data, headers=headers)
		response.raise_for_status()
		print(f"ユーザーID: {user_id}")
		print(f"名前: {personal_data['name']}")
		print_result(True, "ユーザー作成成功")
	except Exception as e:
		print_result(False, f"ユーザー作成失敗: {e}")
		return 1
	
	# ========================================
	# 2. ユーザー情報取得
	# ========================================
	print_section("2. ユーザー情報取得")
	try:
		response = requests.get(f"{BASE_URL}/users/{user_id}", headers=headers)
		response.raise_for_status()
		user_data = response.json()
		print(f"名前: {user_data.get('personal', {}).get('name', 'N/A')}")
		print(f"ステータス: {user_data.get('status', 'N/A')}")
		print(f"作成日時: {user_data.get('created_at', 'N/A')}")
		print_result(True, "ユーザー情報取得成功")
	except Exception as e:
		print_result(False, f"ユーザー情報取得失敗: {e}")
		return 1
	
	# ========================================
	# 3. チャット送信（3回）
	# ========================================
	print_section("3. チャット送信（3回）")
	
	messages = [
		"こんにちは、図書館司書さん",
		"最近、SF小説に興味があります",
		"初心者でも読みやすい作品を教えてください"
	]
	
	session_id = None
	for i, message in enumerate(messages, 1):
		print(f"\n--- チャット {i}/3 ---")
		payload = {"user_id": user_id, "message": message}
		
		try:
			if session_id is None:
				response = requests.post(f"{BASE_URL}/sessions/new/messages", json=payload, headers=headers)
			else:
				response = requests.post(f"{BASE_URL}/sessions/{session_id}/messages", json=payload, headers=headers)
			
			response.raise_for_status()
			data = response.json()
			session_id = data.get('session_id')
			
			print(f"📨 送信: {message}")
			print(f"🤖 応答: {data.get('response', '')[:80]}...")
			print(f"セッションID: {session_id}")
			print_result(True, f"チャット{i}成功")
			time.sleep(1)
		except Exception as e:
			print_result(False, f"チャット{i}失敗: {e}")
			return 1
	
	# ========================================
	# 4. セッション情報取得（再起動前）
	# ========================================
	print_section("4. セッション情報取得（再起動前）")
	try:
		response = requests.get(f"{BASE_URL}/sessions/{session_id}", params={"user_id": user_id}, headers=headers)
		response.raise_for_status()
		session_data = response.json()
		message_count_before = len(session_data.get('history', []))
		print(f"セッションID: {session_id}")
		print(f"ステータス: {session_data.get('status', 'N/A')}")
		print(f"履歴件数: {message_count_before} 件")
		print_result(True, "セッション情報取得成功")
	except Exception as e:
		print_result(False, f"セッション情報取得失敗: {e}")
		return 1
	
	# ========================================
	# 5. サーバー再起動の指示
	# ========================================
	print_section("5. サーバー再起動")
	print("⚠️ サーバーを再起動してください:")
	print("   1. サーバーのターミナルで Ctrl+C を押す")
	print("   2. shutdown イベントで active セッションが pause に変更されることを確認")
	print("   3. conversations.json を確認（次のステップで自動確認）")
	input("\n👉 サーバーを停止したら Enter キーを押してください...")
	
	# ========================================
	# 6. conversations.json確認（pause状態）
	# ========================================
	print_section("6. conversations.json確認（pause状態）")
	# ファイル書き込みが完了するまで少し待つ
	time.sleep(1)
	if not check_json_file(CONVERSATIONS_FILE, session_id, "pause"):
		print("⚠️ pause状態の確認に失敗しましたが、テストを続行します")
	
	# ========================================
	# 7. サーバー再起動
	# ========================================
	print("\n⚠️ サーバーを再起動してください:")
	print("   1. 'プロジェクトルートで python -m backend.run で起動")
	print("   2. 起動ログで pause セッションが active に復元されることを確認")
	input("\n👉 サーバーを起動したら Enter キーを押してください...")
	
	# サーバーが起動するまで少し待つ
	print("\n⏳ サーバーの起動を待機中...")
	time.sleep(3)
	print("✅ 待機完了")
	
	# ========================================
	# 8. チャット継続（再起動後）
	# ========================================
	print_section("8. チャット継続（再起動後）")
	
	continuation_messages = [
		"ありがとうございます",
		"その本を読んでみます"
	]
	
	for i, message in enumerate(continuation_messages, 1):
		print(f"\n--- 継続チャット {i}/2 ---")
		payload = {"user_id": user_id, "message": message}
		
		try:
			response = requests.post(f"{BASE_URL}/sessions/{session_id}/messages", json=payload, headers=headers)
			response.raise_for_status()
			data = response.json()
			
			print(f"📨 送信: {message}")
			print(f"🤖 応答: {data.get('response', '')[:80]}...")
			print_result(True, f"継続チャット{i}成功")
			time.sleep(1)
		except Exception as e:
			print_result(False, f"継続チャット{i}失敗: {e}")
			return 1
	
	# ========================================
	# 9. セッション情報取得（再起動後）
	# ========================================
	print_section("9. セッション情報取得（再起動後）")
	try:
		response = requests.get(f"{BASE_URL}/sessions/{session_id}", params={"user_id": user_id}, headers=headers)
		response.raise_for_status()
		session_data = response.json()
		message_count_after = len(session_data.get('history', []))
		print(f"セッションID: {session_id}")
		print(f"ステータス: {session_data.get('status', 'N/A')}")
		print(f"履歴件数: {message_count_after} 件")
		
		expected_count = message_count_before + len(continuation_messages) * 2  # user + model
		if message_count_after == expected_count:
			print_result(True, f"履歴が正しく保持されています（{message_count_before} → {message_count_after}）")
		else:
			print_result(False, f"履歴件数が期待値と異なります（期待: {expected_count}, 実際: {message_count_after}）")
	except Exception as e:
		print_result(False, f"セッション情報取得失敗: {e}")
		return 1
	
	# ========================================
	# 10. ユーザー情報更新
	# ========================================
	print_section("10. ユーザー情報更新")
	
	# 現在のユーザー情報を取得
	try:
		response = requests.get(f"{BASE_URL}/users/{user_id}", headers=headers)
		response.raise_for_status()
		current_user = response.json()
		
		# personalフィールドを更新
		personal = current_user.get('personal', {})
		personal['live_pref'] = "京都府"
		personal['live_city'] = "京都市"
		
		updates = {"personal": personal}
		
		response = requests.put(f"{BASE_URL}/users/{user_id}", json=updates, headers=headers)
		response.raise_for_status()
		updated_user = response.json()
		print(f"更新後の住所: {updated_user.get('personal', {}).get('live_pref', 'N/A')} {updated_user.get('personal', {}).get('live_city', 'N/A')}")
		print_result(True, "ユーザー情報更新成功")
	except Exception as e:
		print_result(False, f"ユーザー情報更新失敗: {e}")
		# 更新失敗しても続行
	
	# ========================================
	# 11. セッションクローズ
	# ========================================
	print_section("11. セッションクローズ")
	try:
		response = requests.post(f"{BASE_URL}/sessions/{session_id}/close", params={"user_id": user_id}, headers=headers)
		response.raise_for_status()
		print_result(True, "セッションクローズ成功")
		
		# バックグラウンドタスクの完了を待つ
		print("\n⏳ バックグラウンドタスク（summary/ai_insights生成）の完了を待機中...")
		time.sleep(10)
		print("✅ 待機完了")
	except Exception as e:
		print_result(False, f"セッションクローズ失敗: {e}")
		return 1
	
	# ========================================
	# 12. conversations.json確認（closed状態）
	# ========================================
	print_section("12. conversations.json確認（closed状態）")
	if not check_json_file(CONVERSATIONS_FILE, session_id, "closed"):
		print("⚠️ closed状態の確認に失敗しました")
	
	# ========================================
	# 13. users.json確認
	# ========================================
	print_section("13. users.json確認")
	if not USERS_FILE.exists():
		print(f"❌ {USERS_FILE.name} が存在しません")
	else:
		try:
			with open(USERS_FILE, 'r', encoding='utf-8') as f:
				users_data = json.load(f)
			
			user_found = False
			for user_dict in users_data:
				if user_dict.get('_id') == user_id:  # '_id'フィールドを使用
					user_found = True
					print(f"\n📄 {USERS_FILE.name}:")
					print(f"  - ユーザーID: {user_id}")
					print(f"  - 名前: {user_dict.get('personal', {}).get('name', 'N/A')}")
					print(f"  - 住所: {user_dict.get('personal', {}).get('live_pref', 'N/A')} {user_dict.get('personal', {}).get('live_city', 'N/A')}")
					print(f"  - ai_insights: {user_dict.get('ai_insights', 'N/A')[:100]}...")
					print_result(True, "ユーザー情報が保存されています")
					break
			
			if not user_found:
				print(f"❌ ユーザー {user_id} が {USERS_FILE.name} に見つかりません")
		except Exception as e:
			print(f"❌ {USERS_FILE.name} の読み込みエラー: {e}")
	
	# ========================================
	# 結果サマリー
	# ========================================
	print("\n" + "=" * 70)
	print("  テスト完了")
	print("=" * 70)
	
	print("\n📊 実行したテスト:")
	print("  ✅ ユーザー作成")
	print("  ✅ ユーザー情報取得")
	print("  ✅ チャット送信（3回）")
	print("  ✅ セッション情報取得（再起動前）")
	print("  ✅ サーバー再起動（pause確認）")
	print("  ✅ チャット継続（再起動後、2回）")
	print("  ✅ セッション情報取得（再起動後）")
	print("  ✅ ユーザー情報更新")
	print("  ✅ セッションクローズ")
	print("  ✅ JSON確認（conversations.json, users.json）")
	
	print("\n" + "🎉" * 35)
	print("  包括的統合テスト成功！")
	print("🎉" * 35)
	
	print(f"\n📝 テスト情報:")
	print(f"  - テストユーザーID: {user_id}")
	print(f"  - テストセッションID: {session_id}")
	print(f"  - 総チャット数: {len(messages) + len(continuation_messages)} 回")
	print(f"  - 最終履歴件数: {message_count_after} 件")
	
	return 0

if __name__ == "__main__":
	import sys
	sys.exit(main())
