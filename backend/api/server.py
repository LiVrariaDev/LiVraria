# FastAPI Server for LiVraria
#
# 構成: 複数の端末（Raspberry Pi）から、別サーバー上のこの API を共有して使う。
#   - 会話・LLM 呼び出しは時間がかかるため、スレッドで実行してイベントループを止めない
#   - DataStore はスレッドセーフ（内部でロック）

from backend import FIREBASE_ACCOUNT_KEY_PATH, PROMPT_DEFAULT, PROMPT_LIBRARIAN
import asyncio
import logging
import os
import traceback
import uuid
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import messages_to_dict

from .models import ChatRequest, ChatResponse, Personal, ChatStatus, UserStatus, NfcIdRequest, UserUpdate
from .datastore import DataStore
from .llm import llm_chat, FALLBACK_MESSAGES
from .trace_store import current_trace_id, current_turn, get_trace_store, install_log_filter
from .auth import get_current_user_id, verify_device_key, device_key_configured
from . import LLM_BACKEND

# 検索機能
from backend.api.routers import search, debug

# firebase import
import firebase_admin
from firebase_admin import credentials, auth

# ロガー設定
logger = logging.getLogger("uvicorn.error")

# ログの各行に trace_id を付ける
install_log_filter()

# DataStoreインスタンス
data_store = DataStore()


async def monitor_timeouts():
	"""60秒ごとにセッションのタイムアウトをチェックするバックグラウンドタスク"""
	while True:
		try:
			# LLM 呼び出しを含むブロッキング処理なのでスレッドで実行
			await asyncio.to_thread(data_store.check_user_timeout)
		except Exception as e:
			logger.error(f"[ERROR] Timeout monitor failed: {e}")
		await asyncio.sleep(60)


def save_sessions_on_shutdown():
	"""サーバー終了時に全アクティブセッションの要約を作り、pause として保存する。"""
	logger.info("[INFO] Server shutdown: Saving active sessions...")
	session_ids = data_store.active_session_ids()
	for session_id in session_ids:
		try:
			if data_store.conversation_status(session_id) == ChatStatus.active:
				data_store.generate_summary_and_insights(session_id)
			data_store.pause_session(session_id)
		except Exception as e:
			logger.error(f"[ERROR] Session save failed: {session_id}, Error: {e}")
	logger.info(f"[SUCCESS] Saved {len(session_ids)} session(s)")


@asynccontextmanager
async def lifespan(app: FastAPI):
	if LLM_BACKEND == "ollama":
		logger.info(f"[LLM Backend] Using Ollama (model: {os.getenv('OLLAMA_MODEL', 'llama3.2')})")
	else:
		logger.info("[LLM Backend] Using Gemini API")
	if not device_key_configured():
		logger.warning("[WARNING] LIVRARIA_DEVICE_KEY is not set: the device key check is skipped, so NFC login can be called from any device")

	monitor = asyncio.create_task(monitor_timeouts())
	yield
	monitor.cancel()
	await asyncio.to_thread(save_sessions_on_shutdown)


# FastAPIアプリケーション
app = FastAPI(lifespan=lifespan)

# CORS設定
# 端末のブラウザが開いているフロントエンドのオリジンだけを許可する。
# 端末ごとに Vite を動かしている場合は http://localhost:5173 で足りる。
# 別のオリジンから配信する場合は ALLOWED_ORIGINS（旧名 PRODUCTION_ORIGINS）にカンマ区切りで追加する。
allowed_origins = [
	"http://localhost:5173",
	"http://127.0.0.1:5173",
	"https://localhost:5173",
	"https://127.0.0.1:5173",
]
extra_origins = os.getenv("ALLOWED_ORIGINS") or os.getenv("PRODUCTION_ORIGINS", "")
allowed_origins.extend(origin.strip() for origin in extra_origins.split(",") if origin.strip())
logger.info(f"[CORS] Allowed origins: {allowed_origins}")

app.add_middleware(
	CORSMiddleware,
	allow_origins=allowed_origins,
	# 認証は Authorization ヘッダーで行い Cookie は使わない
	allow_credentials=False,
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


# 会話モード → プロンプトファイル
CHAT_PROMPTS = {"default": PROMPT_DEFAULT}
if PROMPT_LIBRARIAN.exists():
	CHAT_PROMPTS["librarian"] = PROMPT_LIBRARIAN


def _require_self(user_id: str, current_user_id: str) -> None:
	if user_id != current_user_id:
		raise HTTPException(status_code=403, detail="Forbidden")


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
			user = self.data_store.get_user(user_id)
			name = user.personal.name if user else "guest"
			return f"Hello, {name}! The LiVraria API server is running."

		# User Endpoints
		@self.app.post("/users", status_code=201)
		async def create_user(personal: Personal, user_id: str = Depends(get_current_user_id)):
			"""ユーザーを作成する。既に存在する場合は既存のユーザーを返す。"""
			user = self.data_store.create_user(user_id, personal)
			return {"detail": "User created successfully", "user": user}

		@self.app.get("/users/{user_id}")
		async def get_user(user_id: str, current_user_id: str = Depends(get_current_user_id)):
			"""ユーザー情報を取得する（自分自身のみ）。"""
			_require_self(user_id, current_user_id)
			user = self.data_store.get_user(user_id)
			if not user:
				raise HTTPException(status_code=404, detail="User not found")
			return user

		@self.app.put("/users/{user_id}")
		async def update_user(user_id: str, updates: UserUpdate, current_user_id: str = Depends(get_current_user_id)):
			"""
			プロフィール（personal）を更新する（自分自身のみ）。
			status / ai_insights / active_session などはクライアントから変更できない。
			"""
			_require_self(user_id, current_user_id)
			try:
				return self.data_store.update_personal(user_id, updates.personal.model_dump(exclude_unset=True))
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
			"""ログアウトする。アクティブなセッションがあればクローズし、AI Insights を生成する。"""
			_require_self(user_id, current_user_id)
			user = self.data_store.get_user(user_id)
			if not user:
				raise HTTPException(status_code=404, detail="User not found")

			session_id = user.active_session
			if session_id and self.data_store.has_user_session(user_id, session_id):
				self.data_store.close_session(session_id)
				background_tasks.add_task(self.data_store.generate_summary_and_insights, session_id)
			else:
				self.data_store.update_user(user_id, status=UserStatus.logout, active_session=None)

			return {"detail": "User logged out successfully"}

		# NFC Authentication Endpoints
		@self.app.post("/nfc/auth", dependencies=[Depends(verify_device_key)])
		async def nfc_auth(request: NfcIdRequest):
			"""
			NFC IDで認証し、Firebase Custom Tokenを返す。
			カード ID は秘密情報ではないため、LIVRARIA_DEVICE_KEY が設定されていれば端末共有キー（X-Device-Key）の一致を求める（空なら確認しない）。
			"""
			user_id = self.data_store.get_user_by_nfc(request.nfc_id)
			if user_id is None or self.data_store.get_user(user_id) is None:
				raise HTTPException(status_code=404, detail="NFC ID not registered")

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
			"""NFC IDをユーザーに紐付ける（FirebaseToken認証必須）。"""
			try:
				self.data_store.register_nfc(request.nfc_id, user_id)
			except KeyError as e:
				raise HTTPException(status_code=404, detail=str(e))
			except PermissionError:
				raise HTTPException(status_code=409, detail="This card is already registered to another user")
			return {
				"detail": "NFC registered successfully",
				"nfc_id": request.nfc_id,
				"user_id": user_id
			}

		@self.app.post("/nfc/unregister")
		async def nfc_unregister(request: NfcIdRequest, user_id: str = Depends(get_current_user_id)):
			"""NFC IDの登録を解除する（自分のカードのみ）。"""
			if self.data_store.get_user_by_nfc(request.nfc_id) != user_id:
				raise HTTPException(status_code=404, detail="NFC ID not found")
			self.data_store.unregister_nfc(request.nfc_id)
			return {"detail": "NFC unregistered successfully"}

		@self.app.get("/users/{user_id}/nfc")
		async def get_user_nfc(user_id: str, current_user_id: str = Depends(get_current_user_id)):
			"""ユーザーのNFC IDを取得する（自分自身のみ）。"""
			_require_self(user_id, current_user_id)
			return {"nfc_id": self.data_store.get_nfc_by_user_id(user_id)}

		# Session Endpoints
		@self.app.get("/sessions/{session_id}")
		async def get_session(session_id: str, user_id: str = Depends(get_current_user_id)):
			"""セッション履歴を取得する（自分のセッションのみ）。"""
			if not self.data_store.has_user_session(user_id, session_id):
				raise HTTPException(status_code=404, detail="Session not found")
			history_dicts = messages_to_dict(self.data_store.get_history(session_id))
			return {"session_id": session_id, "history": history_dicts}

		@self.app.post("/sessions/{session_id}/messages", status_code=201)
		async def send_message(
			session_id: str,
			request: ChatRequest,
			mode: str = "default",
			user_id: str = Depends(get_current_user_id)
		):
			"""
			セッションにメッセージを送信する。
			session_id="new" の場合は、続行中のセッションがあればそれを、なければ新規作成して使う。
			"""
			prompt_path = CHAT_PROMPTS.get(mode)
			if prompt_path is None:
				raise HTTPException(status_code=400, detail=f"Unknown mode: {mode}")
			if not prompt_path.exists():
				raise HTTPException(status_code=500, detail="Prompt file not found")

			target_session = None
			if session_id != "new":
				if not self.data_store.has_user_session(user_id, session_id):
					raise HTTPException(status_code=404, detail="Session not found")
				target_session = session_id

			# LLM 呼び出しは数秒かかるため、スレッドで実行して他端末のリクエストを止めない
			return await asyncio.to_thread(self.chat_prompt, request.message, target_session, str(prompt_path), user_id)

		@self.app.post("/sessions/{session_id}/close")
		async def close_session(
			session_id: str,
			background_tasks: BackgroundTasks,
			user_id: str = Depends(get_current_user_id)
		):
			"""セッションをクローズする。summary/ai_insight の生成は非同期で実行される。"""
			if not self.data_store.has_user_session(user_id, session_id):
				raise HTTPException(status_code=404, detail="Session not found")
			try:
				self.data_store.close_session(session_id)
				background_tasks.add_task(self.data_store.generate_summary_and_insights, session_id)
			except KeyError:
				raise HTTPException(status_code=404, detail="Session not found")
			return {"detail": "Session closed successfully", "session_id": session_id}

		self.app.include_router(search.router)

	def _resolve_session(self, user_id: str, session_id: str | None) -> str:
		"""会話に使うセッションを決める。closed（タイムアウト・ログアウト済み）なら新規に作る。"""
		if session_id and self.data_store.is_session_open(session_id):
			self.data_store.resume_session(session_id)
			return session_id

		user = self.data_store.get_user(user_id)
		if user is None:
			raise HTTPException(status_code=404, detail="User not found")

		active = user.active_session
		if active and self.data_store.has_user_session(user_id, active) and self.data_store.is_session_open(active):
			logger.info(f"[INFO] Resuming existing session: {active}")
			self.data_store.resume_session(active)
			return active

		new_session = self.data_store.create_session(user_id)
		logger.info(f"[INFO] Created new session: {new_session}")
		return new_session

	@staticmethod
	def _build_user_context(user) -> str:
		"""LLM に渡すユーザー情報（プロフィール + AI Insights）。"""
		personal_info = []
		if user.personal:
			if user.personal.name:
				personal_info.append(f"ニックネーム: {user.personal.name}さん（会話の中で親しみを込めて呼びかけてください）")
			personal_info.append(f"性別: {user.personal.gender}")
			personal_info.append(f"年齢: {user.personal.age}歳")

		context = "## ユーザー情報\n" + "\n".join(personal_info) if personal_info else ""
		insights = user.ai_insights or ""
		if insights:
			context = f"{context}\n\n## AI Insights（過去の会話から学習）\n{insights}" if context else insights
		return context

	def chat_prompt(self, message: str, session_id: str | None, prompt_file: str, user_id: str) -> ChatResponse:
		"""会話の1ターンを処理する（ブロッキング。スレッドから呼ぶこと）。"""
		trace_id = uuid.uuid4().hex
		id_token = current_trace_id.set(trace_id)
		turn_token = None
		store = get_trace_store()
		turn = None
		try:
			session_id = self._resolve_session(user_id, session_id)
			history = self.data_store.get_history(session_id)
			user = self.data_store.get_user(user_id)

			if store is not None:
				turn = store.start_turn(trace_id, session_id, user_id, message)
				turn_token = current_turn.set(turn)

			response_text, new_history, recommended_books, current_expression = llm_chat(
				prompt_file,
				message,
				history,
				ai_insight=self._build_user_context(user) if user else ""
			)
			failed = response_text in FALLBACK_MESSAGES

			if turn is not None:
				turn.response_text = response_text
				turn.expression = current_expression
				turn.recommended_count = len(recommended_books)
				turn.failed = failed

			# メモリ上の履歴を更新（ディスク書き込みは close/pause 時に行う）
			self.data_store.update_history(session_id, new_history)

			logger.info(f"[DEBUG] chat_prompt: session={session_id}, books={len(recommended_books)}, expression={current_expression}")
			return ChatResponse(
				response=response_text,
				session_id=session_id,
				recommended_books=recommended_books,
				expression=current_expression,
				trace_id=trace_id,
				failed=failed
			)
		except Exception as exc:
			if turn is not None:
				turn.failed = True
				if turn.error is None:
					turn.error = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
			raise
		finally:
			if turn is not None and store is not None:
				store.finish_turn(turn)
			if turn_token is not None:
				current_turn.reset(turn_token)
			current_trace_id.reset(id_token)


def register_debug_routes(target_app: FastAPI) -> bool:
	"""LIVRARIA_DEBUG=true のときだけ /debug/* を登録する。登録したら True。"""
	if os.getenv("LIVRARIA_DEBUG", "false").lower() != "true":
		return False
	target_app.include_router(debug.router)
	logger.warning("[WARNING] Debug API is enabled (LIVRARIA_DEBUG=true): do not use this setting in production")
	return True


register_debug_routes(app)

# Server を登録してルートを作成
server = Server(app, data_store)

# Run "uvicorn backend.api.server:app --reload" in LiVraria Root
if __name__ == "__main__":
	uvicorn.run(app, host="0.0.0.0", port=8000)
