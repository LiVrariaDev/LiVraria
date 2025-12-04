#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
セッション永続化テストスクリプト
サーバー再起動前後でセッションが保持されることを確認
"""

import requests
import json
import time

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
	
	user_id = f"test_pause_user_{int(time.time())}"
	params = {
		"user_id": user_id,
		"gender": "male",
		"age": 30,
		"live_pref": "東京都",
		"live_city": "新宿区"
	}
	
	try:
		response = requests.post(f"{BASE_URL}/users", params=params)
		response.raise_for_status()
		data = response.json()
		
		print(f"ユーザーID: {user_id}")
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
		print(f"🤖 応答: {data.get('response', '')[:80]}...")
		print(f"セッションID: {data.get('session_id', '')}")
		
		return data.get('session_id')
	except Exception as e:
		print_result(False, f"チャットに失敗: {e}")
		return None

def test_get_session(user_id, session_id):
	"""セッション情報取得テスト"""
	params = {
		"user_id": user_id,
		"session_id": session_id
	}
	
	try:
		response = requests.get(f"{BASE_URL}/sessions", params=params)
		response.raise_for_status()
		data = response.json()
		
		print(f"\nセッションID: {session_id}")
		print(f"履歴件数: {len(data.get('history', []))} 件")
		
		return len(data.get('history', []))
	except Exception as e:
		print_result(False, f"セッション情報取得に失敗: {e}")
		return 0

def check_conversations_json(session_id):
	"""conversations.jsonを確認"""
	import os
	from pathlib import Path
	
	conv_file = Path("/home/kaerunomoto/school/LiVraria/backend/api/data/conversations.json")
	
	if not conv_file.exists():
		print("❌ conversations.json が存在しません")
		return None
	
	try:
		with open(conv_file, 'r', encoding='utf-8') as f:
			data = json.load(f)
			
		if session_id in data:
			status = data[session_id].get('status', 'unknown')
			messages_count = len(data[session_id].get('messages', []))
			print(f"\n📄 conversations.json:")
			print(f"  - セッションID: {session_id}")
			print(f"  - ステータス: {status}")
			print(f"  - メッセージ数: {messages_count}")
			return status
		else:
			print(f"❌ セッション {session_id} が conversations.json に見つかりません")
			return None
	except Exception as e:
		print(f"❌ conversations.json の読み込みエラー: {e}")
		return None

def main():
	"""メインテスト"""
	print("\n" + "🚀" * 30)
	print("  セッション永続化テスト開始")
	print("🚀" * 30)
	
	# 1. ユーザー作成
	user_id = test_create_user()
	if not user_id:
		print("\n❌ ユーザー作成に失敗したため、テストを中断します")
		return
	
	# 2. チャット開始（2回）
	print_section("2. チャット開始（2回）")
	
	session_id = None
	messages = [
		"こんにちは、今日はいい天気ですね",
		"おすすめの本を教えてください"
	]
	
	for i, message in enumerate(messages, 1):
		print(f"\n--- チャット {i}/2 ---")
		session_id = test_chat(user_id, session_id, message)
		if not session_id:
			print(f"\n❌ チャット{i}に失敗したため、テストを中断します")
			return
		time.sleep(1)
	
	print_result(True, f"2回のチャットが完了しました（セッションID: {session_id}）")
	
	# 3. セッション情報取得
	print_section("3. サーバー再起動前のセッション確認")
	message_count_before = test_get_session(user_id, session_id)
	print_result(True, f"再起動前の履歴件数: {message_count_before}")
	
	# 4. サーバー再起動の指示
	print_section("4. サーバー再起動")
	print("⚠️ サーバーを再起動してください:")
	print("   1. サーバーのターミナルで Ctrl+C を押す")
	print("   2. shutdown イベントで active セッションが pause に変更されることを確認")
	print("   3. 再度 'uvicorn backend.api.server:app --reload' で起動")
	print("   4. 起動ログで pause セッションが active に復元されることを確認")
	print("   5. Enter キーを押してテストを続行")
	input("\nサーバーを再起動したら Enter キーを押してください...")

	
	# 5. conversations.json確認
	print_section("5. conversations.json確認")
	status = check_conversations_json(session_id)
	if status == "pause":
		print_result(True, "セッションが pause 状態で保存されています（サーバー停止時）")
	else:
		print_result(False, f"セッションのステータスが pause ではありません: {status}")
	
	# 6. サーバー再起動後のセッション確認
	print_section("6. サーバー再起動後のセッション確認")
	message_count_after = test_get_session(user_id, session_id)
	
	if message_count_after == message_count_before:
		print_result(True, f"再起動後も履歴が保持されています: {message_count_after} 件")
	else:
		print_result(False, f"履歴件数が一致しません: 前={message_count_before}, 後={message_count_after}")
	
	# 7. チャット継続
	print_section("7. チャット継続テスト")
	print("再起動後も同じセッションでチャットを継続します...")
	
	new_session_id = test_chat(user_id, session_id, "ありがとうございます")
	
	if new_session_id == session_id:
		print_result(True, "同じセッションIDでチャットを継続できました")
	else:
		print_result(False, f"セッションIDが変わりました: 前={session_id}, 後={new_session_id}")
	
	# 8. 最終的なセッション確認
	print_section("8. 最終的なセッション確認")
	final_message_count = test_get_session(user_id, session_id)
	
	expected_count = message_count_before + 2  # 新しいメッセージ（user + model）
	if final_message_count == expected_count:
		print_result(True, f"履歴が正しく追加されています: {final_message_count} 件")
	else:
		print_result(False, f"履歴件数が期待値と異なります: 期待={expected_count}, 実際={final_message_count}")
	
	# 9. セッションクローズ
	print_section("9. セッションクローズ")
	params = {
		"user_id": user_id,
		"session_id": session_id
	}
	
	try:
		response = requests.post(f"{BASE_URL}/close_session", params=params)
		response.raise_for_status()
		print_result(True, "セッションをクローズしました")
		
		# バックグラウンドタスクの完了を待つ
		print("\n⏳ バックグラウンドタスク（summary/ai_insights生成）の完了を待機中...")
		time.sleep(10)
		print("✅ 待機完了")
	except Exception as e:
		print_result(False, f"セッションクローズに失敗: {e}")
	
	# 10. 最終確認
	print_section("10. 最終確認")
	status = check_conversations_json(session_id)
	if status == "closed":
		print_result(True, "セッションが closed 状態になりました")
	else:
		print_result(False, f"セッションのステータスが closed ではありません: {status}")
	
	print("\n" + "🎉" * 30)
	print("  セッション永続化テスト完了")
	print("🎉" * 30)
	
	print("\n📝 テスト結果サマリー:")
	print(f"  - テストユーザーID: {user_id}")
	print(f"  - テストセッションID: {session_id}")
	print(f"  - 再起動前の履歴件数: {message_count_before}")
	print(f"  - 再起動後の履歴件数: {message_count_after}")
	print(f"  - 最終的な履歴件数: {final_message_count}")

if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		print("\n\n⚠️ テストが中断されました")
	except Exception as e:
		print(f"\n\n❌ エラーが発生しました: {e}")
		import traceback
		traceback.print_exc()
