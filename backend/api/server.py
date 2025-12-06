# FastAPI Server for LiVraria

from backend import PROMPTS_DIR, FIREBASE_ACCOUNT_KEY_PATH, DATA_DIR, USERS_FILE, CONVERSATIONS_FILE, NFC_USERS_FILE, PROMPT_DEFAULT, PROMPT_LIBRARIAN
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import uvicorn
from pathlib import Path

from .models import ChatRequest, ChatResponse, Personal, ChatStatus
from .datastore import DataStore
from .gemini import gemini_chat

# firebase import
import firebase_admin
from firebase_admin import credentials, auth

# ロガー設定
logger = logging.getLogger("uvicorn.error")

# FastAPIアプリケーション
app = FastAPI()

# CORS設定（フロントエンドからのアクセスを許可）
app.add_middleware(
	CORSMiddleware,
	allow_origins=[
		"http://localhost:5173",  # Vite開発サーバー
		"http://localhost:3000",  # 他の開発サーバー
		"http://127.0.0.1:5173",
		"http://127.0.0.1:3000",
	],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# Firebase Auth
try:
	if FIREBASE_ACCOUNT_KEY_PATH.exists():
		cred = credentials.Certificate(FIREBASE_ACCOUNT_KEY_PATH)
		firebase_admin.initialize_app(cred)
		logger.info("[SUCCESS] Firebase initialized successfully")
	else:
		logger.warning(f"[WARNING] Firebase key file not found: {FIREBASE_ACCOUNT_KEY_PATH}")
except Exception as e:
	logger.error(f"[ERROR] Firebase initialization failed: {e}")


oauth2_scheme = HTTPBearer()

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme)) -> str:
	"""
	HTTP Headerに含まれたTokenをFirebase Authで認証し
	認証に成功した場合はUser IDを返す
	"""
	try:
		id_token = credentials.credentials
		decoded_token = auth.verify_id_token(id_token)
		return decoded_token["uid"]
	except Exception as e:
		logger.error(f"[ERROR] Firebase authentication failed: {e}")
		raise HTTPException(status_code=401, detail="Invalid authentication token")

class Server:
	"""
	Server クラス: FastAPI ルートを束ね、DataStore を用いてセッション管理を行う
	"""
	def __init__(self, app: FastAPI, data_store: DataStore):
		self.app = app
		self.data_store = data_store
		self._register_routes()

	def _register_routes(self):
		@self.app.get("/")
		async def read_root(user_id: str = Depends(get_current_user_id)):
			name = self.data_store.get_user(user_id).personal.name
			return f"Hello, {name}! The LiVraria API server is running."

		# User Endpoints
		@self.app.post("/users", status_code=201)
		async def create_user(personal: Personal, user_id: str = Depends(get_current_user_id)):
			"""
			ユーザーを作成する（RESTful）。
			"""
			user = self.data_store.create_user(user_id, personal)
			return {"detail": "User created successfully", "user": user}
		
		@self.app.get("/users/{user_id}")
		async def get_user(user_id: str, current_user_id: str = Depends(get_current_user_id)):
			"""
			ユーザー情報を取得する（RESTful）。
			自分自身の情報のみ取得可能。
			"""
			# 自分自身の情報のみ取得可能
			if user_id != current_user_id:
				raise HTTPException(status_code=403, detail="Forbidden")
			
			user = self.data_store.get_user(user_id)
			if not user:
				raise HTTPException(status_code=404, detail="User not found")
			
			return user
		
		@self.app.put("/users/{user_id}")
		async def update_user(user_id: str, updates: dict, current_user_id: str = Depends(get_current_user_id)):
			"""
			ユーザー情報を更新する（RESTful）。
			自分自身の情報のみ更新可能。
			"""
			# 自分自身の情報のみ更新可能
			if user_id != current_user_id:
				raise HTTPException(status_code=403, detail="Forbidden")
			
			try:
				user = self.data_store.update_user(user_id, **updates)
				return user
			except KeyError:
				raise HTTPException(status_code=404, detail="User not found")
			except ValueError as e:
				raise HTTPException(status_code=400, detail=str(e))
		

		# NFC Authentication Endpoints
		@self.app.post("/nfc/auth")
		async def nfc_auth(nfc_id: str):
			"""
			NFC IDで認証し、Firebase Custom Tokenを返す。
			認証不要（NFCタグの物理的所持が前提）。
			"""
			user_id = self.data_store.get_user_by_nfc(nfc_id)
			if user_id is None:
				raise HTTPException(status_code=404, detail="NFC ID not registered")
			
			user = self.data_store.get_user(user_id)
			if user is None:
				raise HTTPException(status_code=404, detail="User not found")
			
			# Firebase Custom Token生成
			try:
				custom_token = auth.create_custom_token(user_id)
				return {
					"custom_token": custom_token.decode('utf-8'),
					"user_id": user_id
				}
			except Exception as e:
				logger.error(f"[ERROR] Custom token creation failed: {e}")
				raise HTTPException(status_code=500, detail="Token creation failed")
		
		@self.app.post("/nfc/register")
		async def nfc_register(nfc_id: str, user_id: str = Depends(get_current_user_id)):
			"""
			NFC IDをユーザーに紐付ける（FirebaseToken認証必須）。
			"""
			try:
				nfc_user = self.data_store.register_nfc(nfc_id, user_id)
				return {
					"detail": "NFC registered successfully",
					"nfc_id": nfc_id,
					"user_id": user_id
				}
			except KeyError as e:
				raise HTTPException(status_code=404, detail=str(e))
		
		@self.app.delete("/nfc/unregister")
		async def nfc_unregister(nfc_id: str, user_id: str = Depends(get_current_user_id)):
			"""
			NFC IDの登録を解除する（FirebaseToken認証必須）。
			"""
			# 認証チェック: このNFC IDが本当にこのユーザーのものか確認
			registered_user_id = self.data_store.get_user_by_nfc(nfc_id)
			if registered_user_id != user_id:
				raise HTTPException(status_code=404, detail="NFC ID not found")
			
			self.data_store.unregister_nfc(nfc_id)
			return {"detail": "NFC unregistered successfully"}
		
		@self.app.on_event("shutdown")
		async def shutdown_event():
			"""サーバー終了時に全アクティブセッションを一時停止して保存"""
			logger.info("[INFO] Server shutdown: Saving active sessions...")
			session_ids = list(self.data_store.sessions.keys())
			for session_id in session_ids:
				try:
					self.data_store.pause_session(session_id)
				except Exception as e:
					logger.error(f"[ERROR] Session save failed: {session_id}, Error: {e}")
			logger.info(f"[SUCCESS] Saved {len(session_ids)} session(s)")

		# Session Endpoints
		@self.app.get("/sessions/{session_id}")
		async def get_session(session_id: str, user_id: str = Depends(get_current_user_id)):
			"""
			セッション情報を取得する（RESTful）。
			"""
			# user_idとsession_idの組み合わせをチェック
			if not self.data_store.has_user_session(user_id, session_id):
				raise HTTPException(status_code=404, detail="Session not found")
			return {"session_id": session_id, "history": self.data_store.get_history(session_id)}

		@self.app.post("/sessions/{session_id}/messages", status_code=201)
		async def send_message(
			session_id: str,
			request: ChatRequest,
			mode: str = "default",
			user_id: str = Depends(get_current_user_id)
		):
			"""
			セッションにメッセージを送信する（RESTful）。
			session_id="new"の場合は新規セッション作成。
			mode: "default" または "librarian"
			"""
			# モードに応じたプロンプトファイルを選択
			if mode == "librarian":
				prompt_path = PROMPT_LIBRARIAN
			else:
				prompt_path = PROMPT_DEFAULT
			
			if not prompt_path.exists():
				raise HTTPException(status_code=500, detail=f"Prompt file not found")
			
			# 新規セッション作成の場合
			if session_id == "new":
				request.session_id = None  # chat_promptで新規作成させる
			else:
				# 既存セッションの認証チェック
				if not self.data_store.has_user_session(user_id, session_id):
					raise HTTPException(status_code=404, detail="Session not found")
				request.session_id = session_id
			
			return await self.chat_prompt(request, str(prompt_path), user_id)

		@self.app.put("/sessions/{session_id}/close")
		async def close_session(
			session_id: str,
			background_tasks: BackgroundTasks,
			user_id: str = Depends(get_current_user_id)
		):
			"""
			セッションをクローズする（RESTful）。
			summary/ai_insightの生成は非同期で実行される。
			"""
			# user_idとsession_idの組み合わせをチェック
			if not self.data_store.has_user_session(user_id, session_id):
				raise HTTPException(status_code=404, detail="Session not found")
			
			try:
				# セッションをクローズ（同期処理）
				self.data_store.close_session(session_id)
				# summary/ai_insightの生成をバックグラウンドタスクで実行（非同期処理）
				background_tasks.add_task(self.data_store.generate_summary_and_insights, session_id)
			except KeyError:
				raise HTTPException(status_code=404, detail="Session not found")
			
			return {"detail": "Session closed successfully", "session_id": session_id}


	async def chat_prompt(self, request: ChatRequest, prompt_file: str, user_id: str) -> ChatResponse:
		# タイムアウトチェック（ユーザー単位）
		self.data_store.check_user_timeout()
		
		# セッション確保
		session_id = request.session_id
		logger.info(f"[DEBUG] chat_prompt: request.session_id = {session_id}")
		if session_id is None:
			# user_id を渡して active_session を in-memory 更新する
			session_id = self.data_store.create_session(user_id)
			logger.info(f"[DEBUG] chat_prompt: created session_id = {session_id}")
			history = []
		else:
			if not self.data_store.has_session(session_id):
				raise HTTPException(status_code=404, detail="Session not found")
			
			history = self.data_store.get_history(session_id)

		# ユーザーの ai_insights を取得して Gemini に渡す
		ai_insight = ""
		if user_id:
			user = self.data_store.get_user(user_id)
			if user:
				ai_insight = getattr(user, "ai_insights", "") or ""

		# gemini_chat(prompt_file, message, history, ai_insight=None)
		response_text, new_history = gemini_chat(prompt_file, request.message, history, ai_insight=ai_insight)

		# メモリ上の履歴を更新（ディスク書き込みは close_session 時に行う）
		self.data_store.update_history(session_id, new_history)
		
		logger.info(f"[DEBUG] chat_prompt returning session_id: {session_id}")
		return ChatResponse(response=response_text, session_id=session_id)


# DataStoreインスタンスを作成
data_store = DataStore()

# Server を登録してルートを作成
server = Server(app, data_store)

# Run "uvicorn backend.api.server:app --reload" in LiVraria Root
if __name__ == "__main__":
	uvicorn.run(app, host="0.0.0.0", port=8000)
