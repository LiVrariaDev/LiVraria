# FastAPI Server for LiVraria

from backend import PROMPTS_DIR, FIREBASE_ACCOUNT_KEY_PATH, DATA_DIR, USERS_FILE, CONVERSATIONS_FILE, NFC_USERS_FILE, PROMPT_DEFAULT, PROMPT_LIBRARIAN
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import uvicorn
import asyncio


from .models import ChatRequest, ChatResponse, Personal, ChatStatus, NfcIdRequest
from .datastore import DataStore
from .llm import llm_chat
from . import LLM_BACKEND
from langchain_core.messages import messages_to_dict

# 検索機能
from backend.api.routers import search

# firebase import
import firebase_admin
from firebase_admin import credentials, auth

# ロガー設定
logger = logging.getLogger("uvicorn.error")

# FastAPIアプリケーション
app = FastAPI()

# 起動時イベント
@app.on_event("startup")
async def startup_event():
	"""サーバー起動時にLLMバックエンド情報を表示"""
	if LLM_BACKEND == "ollama":
		logger.info(f"🤖 [LLM Backend] Using Ollama (model: {os.getenv('OLLAMA_MODEL', 'llama3.2')})")
	else:
		logger.info("🤖 [LLM Backend] Using Gemini API")

	# バックグラウンドでタイムアウト監視を開始
	asyncio.create_task(monitor_timeouts())

async def monitor_timeouts():
	"""
	60秒ごとにセッションのタイムアウトをチェックするバックグラウンドタスク
	"""
	while True:
		try:
			# ブロッキング処理（LLM呼び出し含む）なのでスレッドで実行
			await asyncio.to_thread(data_store.check_user_timeout)
		except Exception as e:
			logger.error(f"[ERROR] Timeout monitor failed: {e}")
		
		await asyncio.sleep(60)


# CORS設定（フロントエンドからのアクセスを許可）
# 開発環境のオリジン（デフォルト）
allowed_origins = [
	"http://localhost:5173",  # Vite開発サーバー
	"http://localhost:3000",  # 他の開発サーバー
	"http://127.0.0.1:5173",
	"http://127.0.0.1:3000",
	"*",  # Allow all origins for network access
]

# 本番環境のオリジンを環境変数から追加
production_origins = os.getenv("PRODUCTION_ORIGINS", "")
if production_origins:
	# カンマ区切りで複数のオリジンを指定可能
	# 例: PRODUCTION_ORIGINS=https://example.com,https://www.example.com
	allowed_origins.extend([origin.strip() for origin in production_origins.split(",") if origin.strip()])
	logger.info(f"[CORS] Production origins added: {production_origins}")

app.add_middleware(
	CORSMiddleware,
	allow_origins=allowed_origins,
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
		
		@self.app.post("/users/{user_id}/logout")
		async def logout(
			user_id: str, 
			background_tasks: BackgroundTasks,
			current_user_id: str = Depends(get_current_user_id)
		):
			"""
			ユーザーをログアウトさせる（RESTful）。
			自分自身の情報のみログアウト可能。
			アクティブなセッションがあればクローズし、AI Insightsを生成する。
			"""
			# 自分自身の情報のみログアウト可能
			if user_id != current_user_id:
				raise HTTPException(status_code=403, detail="Forbidden")
			
			user = self.data_store.get_user(user_id)
			if not user:
				raise HTTPException(status_code=404, detail="User not found")
			
			# アクティブセッションの確認
			session_id = user.active_session
			if session_id:
				# セッションをクローズ（これで user.status も logout になる）
				self.data_store.close_session(session_id)
				# ログアウト時は非同期でインサイト生成（ユーザーを待たせない）
				background_tasks.add_task(self.data_store.generate_summary_and_insights, session_id)
			else:
				# セッションがない場合はステータスのみ更新
				self.data_store.update_user(user_id, status=UserStatus.logout)
			
			return {"detail": "User logged out successfully"}

		# NFC Authentication Endpoints
		@self.app.post("/nfc/auth")
		async def nfc_auth(request: NfcIdRequest):
			"""
			NFC IDで認証し、Firebase Custom Tokenを返す。
			認証不要（NFCタグの物理的所持が前提）。
			"""
			nfc_id = request.nfc_id
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
		async def nfc_register(request: NfcIdRequest, user_id: str = Depends(get_current_user_id)):
			"""
			NFC IDをユーザーに紐付ける（FirebaseToken認証必須）。
			"""
			try:
				nfc_id = request.nfc_id
				nfc_user = self.data_store.register_nfc(nfc_id, user_id)
				return {
					"detail": "NFC registered successfully",
					"nfc_id": nfc_id,
					"user_id": user_id
				}
			except KeyError as e:
				raise HTTPException(status_code=404, detail=str(e))
		
		@self.app.post("/nfc/unregister")
		async def nfc_unregister(request: NfcIdRequest, user_id: str = Depends(get_current_user_id)):
			"""
			NFC IDの登録を解除する（FirebaseToken認証必須）。
			"""
			# 認証チェック: このNFC IDが本当にこのユーザーのものか確認
			nfc_id = request.nfc_id
			registered_user_id = self.data_store.get_user_by_nfc(nfc_id)
			if registered_user_id != user_id:
				raise HTTPException(status_code=404, detail="NFC ID not found")
			
			self.data_store.unregister_nfc(nfc_id)
			return {"detail": "NFC unregistered successfully"}
		
		@self.app.get("/users/{user_id}/nfc")
		async def get_user_nfc(user_id: str, current_user_id: str = Depends(get_current_user_id)):
			"""
			ユーザーのNFC IDを取得する（認証必須）。
			"""
			# 自分自身の情報のみ取得可能
			if user_id != current_user_id:
				raise HTTPException(status_code=403, detail="Forbidden")
				
			nfc_id = self.data_store.get_nfc_by_user_id(user_id)
			if nfc_id is None:
				return {"nfc_id": None}
				
			return {"nfc_id": nfc_id}
		
		
		@self.app.on_event("shutdown")
		async def shutdown_event():
			"""サーバー終了時に全アクティブセッションを一時停止して保存"""
			logger.info("[INFO] Server shutdown: Saving active sessions...")
			session_ids = list(self.data_store.sessions.keys())
			# タイムアウト回避のため、各セッションの処理をtry-exceptで囲む
			for session_id in session_ids:
				try:
					# サーバー終了時は時間かかっても良いので、ここで要約とAI Insights生成を行う
					logger.info(f"[INFO] Generating insights for session: {session_id}")
					self.data_store.generate_summary_and_insights(session_id)
					
					# その後、セッションをpause（保存）
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
			
			history_objs = self.data_store.get_history(session_id)
			history_dicts = messages_to_dict(history_objs)
			return {"session_id": session_id, "history": history_dicts}

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

		@self.app.post("/sessions/{session_id}/close")
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
		
		self.app.include_router(
            search.router, 
            dependencies=[Depends(get_current_user_id)]
        )


	async def chat_prompt(self, request: ChatRequest, prompt_file: str, user_id: str) -> ChatResponse:
		
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

		# ユーザーの ai_insights と personal 情報を取得して LLM に渡す
		ai_insight = ""
		if user_id:
			user = self.data_store.get_user(user_id)
			if user:
				# Personal情報を追加（ニックネーム、年齢、性別）
				personal_info = []
				if user.personal:
					# ニックネームがあれば追加
					if hasattr(user.personal, 'name') and user.personal.name:
						personal_info.append(f"ニックネーム: {user.personal.name}さん（会話の中で親しみを込めて呼びかけてください）")
					personal_info.append(f"性別: {user.personal.gender}")
					personal_info.append(f"年齢: {user.personal.age}歳")
				
				# AI Insightsを追加
				ai_insights_text = getattr(user, "ai_insights", "") or ""
				
				# 統合
				if personal_info:
					ai_insight = "## ユーザー情報\n" + "\n".join(personal_info)
				if ai_insights_text:
					if ai_insight:
						ai_insight += "\n\n## AI Insights（過去の会話から学習）\n" + ai_insights_text
					else:
						ai_insight = ai_insights_text

		# LLMバックエンドを使用してチャット
		# llm_chatは (response_text, new_history, recommended_books) を返す
		response_text, new_history, recommended_books = llm_chat(
			prompt_file, 
			request.message, 
			history, 
			ai_insight=ai_insight
		)

		# メモリ上の履歴を更新（ディスク書き込みは close_session 時に行う）
		self.data_store.update_history(session_id, new_history)
		
		logger.info(f"[DEBUG] chat_prompt returning session_id: {session_id}")
		logger.info(f"[DEBUG] recommended_books count: {len(recommended_books)}")
		
		return ChatResponse(
			response=response_text, 
			session_id=session_id,
			recommended_books=recommended_books
		)


# DataStoreインスタンスを作成
data_store = DataStore()

# Server を登録してルートを作成
server = Server(app, data_store)

# Run "uvicorn backend.api.server:app --reload" in LiVraria Root
if __name__ == "__main__":
	uvicorn.run(app, host="0.0.0.0", port=8000)
