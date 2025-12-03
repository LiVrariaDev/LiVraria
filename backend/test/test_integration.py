#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
統合テストスクリプト
ユーザー作成 → チャット → セッション確認 → クローズ → 再起動後の確認
"""

import requests
import json
import time
from datetime import datetime

# サーバーのベースURL
BASE_URL = "http://localhost:8000"

def print_section(title):
	"""セクションタイトルを表示"""
	print("\n" + "=" * 60)
	print(f"  {title}")
	print("=" * 60)

def print_result(success, message):
	"""テスト結果を表示"""
	status = "✅ 成功" if success else "❌ 失敗"
	print(f"{status}: {message}")

def test_create_user():
	"""ユーザー作成テスト"""
	print_section("1. ユーザー作成テスト")
	
	user_id = f"test_user_{int(time.time())}"
	params = {
		"user_id": user_id,
		"gender": "male",
		"age": 25,
		"live_pref": "東京都",
		"live_city": "渋谷区"
	}
	
	try:
		response = requests.post(f"{BASE_URL}/users", params=params)
		response.raise_for_status()
		data = response.json()
		
		print(f"ユーザーID: {user_id}")
		print(f"レスポンス: {json.dumps(data, ensure_ascii=False, indent=2)}")
		print_result(True, f"ユーザー '{user_id}' を作成しました")
		return user_id
	except Exception as e:
		print_result(False, f"ユーザー作成に失敗: {e}")
		return None

def test_chat(user_id, session_id=None, message="こんにちは"):
	"""チャットテスト"""
	endpoint = "/chat/default"
	
	# payloadを構築（session_idがNoneの場合は含めない）
	payload = {
		"user_id": user_id,
		"message": message
	}
	if session_id is not None:
		payload["session_id"] = session_id
	
	try:
		response = requests.post(f"{BASE_URL}{endpoint}", json=payload)
		response.raise_for_status()
		data = response.json()
		
		print(f"\n📨 送信: {message}")
		print(f"🤖 応答: {data.get('response', '')[:100]}...")
		print(f"セッションID: {data.get('session_id', '')}")
		
		return data.get('session_id')
	except Exception as e:
		print_result(False, f"チャットに失敗: {e}")
		return None

def test_get_session(user_id, session_id):
	"""セッション情報取得テスト"""
	print_section("4. セッション情報取得テスト")
	
	params = {
		"user_id": user_id,
		"session_id": session_id
	}
	
	try:
		response = requests.get(f"{BASE_URL}/sessions", params=params)
		response.raise_for_status()
		data = response.json()
		
		print(f"セッションID: {session_id}")
		print(f"履歴件数: {len(data.get('history', []))} 件")
		print(f"履歴の一部:")
		for i, msg in enumerate(data.get('history', [])[:3]):
			role = msg.get('role', 'unknown')
			content = str(msg.get('content', ''))[:50]
			print(f"  {i+1}. [{role}] {content}...")
		
		print_result(True, "セッション情報を取得しました")
		return True
	except Exception as e:
		print_result(False, f"セッション情報取得に失敗: {e}")
		return False

def test_close_session(user_id, session_id):
	"""セッションクローズテスト"""
	print_section("5. セッションクローズテスト")
	
	params = {
		"user_id": user_id,
		"session_id": session_id
	}
	
	try:
		response = requests.post(f"{BASE_URL}/close_session", params=params)
		response.raise_for_status()
		data = response.json()
		
		print(f"セッションID: {session_id}")
		print(f"レスポンス: {json.dumps(data, ensure_ascii=False, indent=2)}")
		print_result(True, "セッションをクローズしました")
		
		# バックグラウンドタスクの完了を待つ
		print("\n⏳ バックグラウンドタスク（summary/ai_insights生成）の完了を待機中...")
		time.sleep(10)  # 10秒待機
		print("✅ 待機完了")
		
		return True
	except Exception as e:
		print_result(False, f"セッションクローズに失敗: {e}")
		return False

def test_get_closed_session(user_id, session_id):
	"""クローズ済みセッション取得テスト"""
	print_section("7. クローズ済みセッション取得テスト")
	
	params = {
		"user_id": user_id,
		"session_id": session_id
	}
	
	try:
		response = requests.get(f"{BASE_URL}/sessions", params=params)
		response.raise_for_status()
		data = response.json()
		
		print(f"セッションID: {session_id}")
		print(f"履歴件数: {len(data.get('history', []))} 件")
		
		# 履歴の内容を確認
		history = data.get('history', [])
		if history:
			print(f"\n履歴の内容:")
			for i, msg in enumerate(history[:5]):
				if hasattr(msg, 'role') and hasattr(msg, 'content'):
					role = msg.role
					content = str(msg.content)[:50]
				elif isinstance(msg, dict):
					role = msg.get('role', 'unknown')
					content = str(msg.get('content', ''))[:50]
				else:
					role = 'unknown'
					content = str(msg)[:50]
				print(f"  {i+1}. [{role}] {content}...")
		
		print_result(True, "クローズ済みセッション情報を取得しました")
		return True
	except Exception as e:
		print_result(False, f"クローズ済みセッション取得に失敗: {e}")
		return False

def check_data_files():
	"""データファイルの確認"""
	print_section("8. データファイルの確認")
	
	import os
	from pathlib import Path
	
	data_dir = Path("/home/kaerunomoto/school/LiVraria/backend/data")
	
	files = {
		"users.json": data_dir / "users.json",
		"conversations.json": data_dir / "conversations.json",
		"sessions.json": data_dir / "sessions.json"
	}
	
	for name, path in files.items():
		if path.exists():
			size = path.stat().st_size
			print(f"✅ {name}: {size} bytes")
			
			# ファイルの内容を確認
			try:
				with open(path, 'r', encoding='utf-8') as f:
					data = json.load(f)
					if isinstance(data, dict):
						print(f"   - キー数: {len(data)}")
					elif isinstance(data, list):
						print(f"   - 要素数: {len(data)}")
			except Exception as e:
				print(f"   - 読み込みエラー: {e}")
		else:
			print(f"❌ {name}: ファイルが存在しません")

def main():
	"""メインテスト"""
	print("\n" + "🚀" * 30)
	print("  統合テスト開始")
	print("🚀" * 30)
	
	# 1. ユーザー作成
	user_id = test_create_user()
	if not user_id:
		print("\n❌ ユーザー作成に失敗したため、テストを中断します")
		return
	
	# 2. チャット（3回）
	print_section("2. チャットテスト（3回）")
	
	session_id = None
	messages = [
		"こんにちは、おすすめの本を教えてください",
		"SF小説が好きです",
		"ありがとうございます"
	]
	
	for i, message in enumerate(messages, 1):
		print(f"\n--- チャット {i}/3 ---")
		session_id = test_chat(user_id, session_id, message)
		if not session_id:
			print(f"\n❌ チャット{i}に失敗したため、テストを中断します")
			return
		time.sleep(1)  # 1秒待機
	
	print_result(True, f"3回のチャットが完了しました（セッションID: {session_id}）")
	
	# 3. セッション情報取得
	if not test_get_session(user_id, session_id):
		print("\n⚠️ セッション情報取得に失敗しましたが、テストを継続します")
	
	# 4. セッションクローズ
	if not test_close_session(user_id, session_id):
		print("\n❌ セッションクローズに失敗したため、テストを中断します")
		return
	
	# 5. データファイルの確認
	check_data_files()
	
	# 6. サーバー再起動の指示
	print_section("6. サーバー再起動")
	print("⚠️ 手動でサーバーを再起動してください:")
	print("   1. Ctrl+C でサーバーを停止")
	print("   2. 再度 'uvicorn backend.api.server:app --reload' で起動")
	print("   3. Enter キーを押してテストを続行")
	input("\nサーバーを再起動したら Enter キーを押してください...")
	
	# 7. クローズ済みセッション取得
	if not test_get_closed_session(user_id, session_id):
		print("\n⚠️ クローズ済みセッション取得に失敗しました")
	
	# 8. 最終確認
	print_section("9. 最終確認")
	print(f"✅ テストユーザーID: {user_id}")
	print(f"✅ テストセッションID: {session_id}")
	print("\n📝 確認事項:")
	print("  1. backend/data/users.json にユーザー情報が保存されているか")
	print("  2. backend/data/conversations.json にセッション情報が保存されているか")
	print("  3. Conversation.summary が生成されているか")
	print("  4. User.ai_insights が更新されているか")
	
	print("\n" + "🎉" * 30)
	print("  統合テスト完了")
	print("🎉" * 30)

if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		print("\n\n⚠️ テストが中断されました")
	except Exception as e:
		print(f"\n\n❌ エラーが発生しました: {e}")
		import traceback
		traceback.print_exc()
