# FastAPI Server for LiVraria

from backend import PROMPTS_DIR, FIREBASE_ACCOUNT_KEY_PATH, DATA_DIR, PROMPT_DEFAULT, PROMPT_LIBRARIAN
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import uvicorn

from .models import ChatRequest, ChatResponse, Personal, ChatStatus
from .datastore import DataStore
from . import chat_function, LLM_BACKEND

# firebase import
import firebase_admin
from firebase_admin import credentials, auth

# Logger
logger = logging.getLogger("uvicorn.error")

# FastAPI Application
app = FastAPI()

# Startup Event
@app.on_event("startup")
async def startup_event():
	"""Log LLM backend info on startup"""
	if LLM_BACKEND == "ollama":
		logger.info(f"🤖 [LLM Backend] Using Ollama (model: {os.getenv('OLLAMA_MODEL', 'llama3.2')})")
	else:
		logger.info("🤖 [LLM Backend] Using Gemini API")

# CORS Settings
allowed_origins = [
	"http://localhost:5173",
	"http://localhost:3000",
	"http://127.0.0.1:5173",
	"http://127.0.0.1:3000",
	"*",
]

production_origins = os.getenv("PRODUCTION_ORIGINS", "")
if production_origins:
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
	Verify Firebase Token and return User ID.
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
	Server Class: Bundles FastAPI routes and handles session management with DataStore
	"""
	def __init__(self, app: FastAPI, data_store: DataStore):
		self.app = app
		self.data_store = data_store
		self._register_routes()

	def _register_routes(self):
		@self.app.get("/")
		async def read_root(user_id: str = Depends(get_current_user_id)):
			user = await self.data_store.get_user(user_id)
			if user and user.personal:
				name = user.personal.name
				return f"Hello, {name}! The LiVraria API server is running."
			return "Hello! The LiVraria API server is running."

		# User Endpoints
		@self.app.post("/users", status_code=201)
		async def create_user(personal: Personal, user_id: str = Depends(get_current_user_id)):
			"""
			Create a user.
			"""
			user = await self.data_store.create_user(user_id, personal)
			return {"detail": "User created successfully", "user": user}
		
		@self.app.get("/users/{user_id}")
		async def get_user(user_id: str, current_user_id: str = Depends(get_current_user_id)):
			"""
			Get user info. Self only.
			"""
			if user_id != current_user_id:
				raise HTTPException(status_code=403, detail="Forbidden")
			
			user = await self.data_store.get_user(user_id)
			if not user:
				raise HTTPException(status_code=404, detail="User not found")
			
			return user
		
		@self.app.put("/users/{user_id}")
		async def update_user(user_id: str, updates: dict, current_user_id: str = Depends(get_current_user_id)):
			"""
			Update user info. Self only.
			"""
			if user_id != current_user_id:
				raise HTTPException(status_code=403, detail="Forbidden")
			
			try:
				user = await self.data_store.update_user(user_id, **updates)
				return user
			except KeyError:
				raise HTTPException(status_code=404, detail="User not found")
			except ValueError as e:
				raise HTTPException(status_code=400, detail=str(e))
		

		# NFC Authentication Endpoints
		@self.app.post("/nfc/auth")
		async def nfc_auth(nfc_id: str):
			"""
			Authenticate with NFC ID, return Firebase Custom Token.
			"""
			user_id = await self.data_store.get_user_by_nfc(nfc_id)
			if user_id is None:
				raise HTTPException(status_code=404, detail="NFC ID not registered")
			
			user = await self.data_store.get_user(user_id)
			if user is None:
				raise HTTPException(status_code=404, detail="User not found")
			
			# Generate Firebase Custom Token
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
			Register NFC ID to user.
			"""
			try:
				nfc_user = await self.data_store.register_nfc(nfc_id, user_id)
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
			Unregister NFC ID.
			"""
			# Auth check
			registered_user_id = await self.data_store.get_user_by_nfc(nfc_id)
			if registered_user_id != user_id:
				raise HTTPException(status_code=404, detail="NFC ID not found")
			
			await self.data_store.unregister_nfc(nfc_id)
			return {"detail": "NFC unregistered successfully"}
		
		@self.app.on_event("shutdown")
		async def shutdown_event():
			"""
			Pause all sessions on shutdown (not easily doable without tracking active sessions in memory or DB query).
			For MongoDB, we can skip pausing everything or do a query.
			Assuming sessions stay 'active' in DB is fine, or we mark them interrupted?
			Let's leave it empty for now or do a cleanup if needed.
			Considering stateless-ish nature, forcing pause might not be critical if DB persists state immediately.
			"""
			logger.info("[INFO] Server shutdown.")

		# Session Endpoints
		@self.app.get("/sessions/{session_id}")
		async def get_session(session_id: str, user_id: str = Depends(get_current_user_id)):
			"""
			Get session info.
			"""
			if not await self.data_store.has_user_session(user_id, session_id):
				raise HTTPException(status_code=404, detail="Session not found")
			
			history = await self.data_store.get_history(session_id)
			return {"session_id": session_id, "history": history}

		@self.app.post("/sessions/{session_id}/messages", status_code=201)
		async def send_message(
			session_id: str,
			request: ChatRequest,
			mode: str = "default",
			user_id: str = Depends(get_current_user_id)
		):
			"""
			Send message to session.
			"""
			if mode == "librarian":
				prompt_path = PROMPT_LIBRARIAN
			else:
				prompt_path = PROMPT_DEFAULT
			
			if not prompt_path.exists():
				raise HTTPException(status_code=500, detail=f"Prompt file not found")
			
			if session_id == "new":
				request.session_id = None
			else:
				if not await self.data_store.has_user_session(user_id, session_id):
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
			Close session.
			"""
			if not await self.data_store.has_user_session(user_id, session_id):
				raise HTTPException(status_code=404, detail="Session not found")
			
			try:
				await self.data_store.close_session(session_id)
				# Asynchronous generation of summary/insights
				background_tasks.add_task(self.data_store.generate_summary_and_insights, session_id)
			except KeyError:
				raise HTTPException(status_code=404, detail="Session not found")
			
			return {"detail": "Session closed successfully", "session_id": session_id}


	async def chat_prompt(self, request: ChatRequest, prompt_file: str, user_id: str) -> ChatResponse:
		# Check timeout (simplified or skipped in DB version)
		# await self.data_store.check_user_timeout()
		
		session_id = request.session_id
		logger.info(f"[DEBUG] chat_prompt: request.session_id = {session_id}")
		if session_id is None:
			session_id = await self.data_store.create_session(user_id)
			logger.info(f"[DEBUG] chat_prompt: created session_id = {session_id}")
			history = []
		else:
			if not await self.data_store.has_session(session_id):
				raise HTTPException(status_code=404, detail="Session not found")
			
			history = await self.data_store.get_history(session_id)

		# Get Agent Insights
		ai_insight = ""
		if user_id:
			user = await self.data_store.get_user(user_id)
			if user:
				personal_info = []
				if user.personal:
					if hasattr(user.personal, 'name') and user.personal.name:
						personal_info.append(f"ニックネーム: {user.personal.name}さん（会話の中で親しみを込めて呼びかけてください）")
					personal_info.append(f"性別: {user.personal.gender}")
					personal_info.append(f"年齢: {user.personal.age}歳")
				
				ai_insights_text = getattr(user, "ai_insights", "") or ""
				
				if personal_info:
					ai_insight = "## ユーザー情報\n" + "\n".join(personal_info)
				if ai_insights_text:
					if ai_insight:
						ai_insight += "\n\n## AI Insights（過去の会話から学習）\n" + ai_insights_text
					else:
						ai_insight = ai_insights_text

		# LLM Chat (Sync function, running in main thread for now, assuming fast enough or threaded internally if using API)
		# NOTE: If chat_function is blocking, it blocks the async loop!
		# Ideally should run in executor.
		import asyncio
		loop = asyncio.get_running_loop()
		response_text, new_history, recommended_books = await loop.run_in_executor(
			None,
			lambda: chat_function(prompt_file, request.message, history, ai_insight=ai_insight)
		)

		await self.data_store.update_history(session_id, new_history)
		
		logger.info(f"[DEBUG] chat_prompt returning session_id: {session_id}")
		
		return ChatResponse(
			response=response_text, 
			session_id=session_id,
			recommended_books=recommended_books
		)


# DataStore Instance
data_store = DataStore()

# Server Instance
server = Server(app, data_store)

# Run
if __name__ == "__main__":
	uvicorn.run(app, host="0.0.0.0", port=8000)
