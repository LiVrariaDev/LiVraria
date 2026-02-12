# Backend package initialization
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# .envのディレクトリがProject ROOT
DOTENV_ROOT = find_dotenv(usecwd=True)
PROJECT_ROOT = Path(DOTENV_ROOT).parent

# .envの読み込み
load_dotenv(dotenv_path=DOTENV_ROOT)

# ============================================================================
# Configuration Settings
# ============================================================================
# 必要に応じてここを直接編集してください

# Directory paths
PROMPTS_DIR_REL = "backend/api/prompts"  # プロンプトファイルのディレクトリ
DATA_DIR_REL = "backend/api/data"        # データファイルのディレクトリ

# Server settings
BACKEND_HOST = "0.0.0.0"
BACKEND_PORT = 8000

# Session settings
SESSION_TIMEOUT = 1800  # 30分（秒単位）

# LLM settings
LLM_MAX_RETRIES = 3  # LLMが空のレスポンスを返した場合の最大リトライ回数
LLM_HISTORY_LIMIT = 100  # 会話履歴の最大メッセージ数（システムプロンプト除く）


# Database settings
MONGODB_DB = "livraria_dev"


# ============================================================================
# End of Configuration
# ============================================================================

# Directories
if not Path(PROJECT_ROOT, ".env").exists():
	raise FileNotFoundError(".env file not found")

# 環境変数の取得
firebase_key_env = os.getenv("FIREBASE_ACCOUNT_KEY_PATH")

if not firebase_key_env:
	raise ValueError(
		"Environment value 'FIREBASE_ACCOUNT_KEY_PATH' is not set\n"
		"Hint: .env file not found or FIREBASE_ACCOUNT_KEY_PATH value is empty"
	)

# GEMINI_API_KEYが設定されているかチェック
if not os.getenv("GEMINI_API_KEY"):
	raise ValueError(
		"Environment value 'GEMINI_API_KEY' is not set\n"
		"Hint: .env file not found or GEMINI_API_KEY value is empty"
	)

if not os.getenv("FIREBASE_API_KEY"):
	raise ValueError(
		"Environment value 'FIREBASE_API_KEY' is not set\n"
		"Hint: .env file not found or FIREBASE_API_KEY value is empty"
	)

PROMPTS_DIR = Path(PROJECT_ROOT, PROMPTS_DIR_REL)
DATA_DIR = Path(PROJECT_ROOT, DATA_DIR_REL)

if not DATA_DIR.exists():
	DATA_DIR.mkdir(parents=True, exist_ok=True)
	Path(DATA_DIR, "conversations.json").touch(exist_ok=True)
	Path(DATA_DIR, "users.json").touch(exist_ok=True)
	Path(DATA_DIR, "nfc_users.json").touch(exist_ok=True)

FIREBASE_ACCOUNT_KEY_PATH = Path(PROJECT_ROOT, firebase_key_env)

# Data file path
CONVERSATIONS_FILE = Path(DATA_DIR, "conversations.json")
USERS_FILE = Path(DATA_DIR, "users.json")
NFC_USERS_FILE = Path(DATA_DIR, "nfc_users.json")

# Prompt file paths
# LLMバックエンドに応じてdefaultプロンプトを切り替え
LLM_BACKEND = os.getenv("LLM_BACKEND", "gemini")
# セッションタイムアウト時間（秒）
# 30分 = 1800秒
SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "1800"))

if LLM_BACKEND == "ollama":
	PROMPT_DEFAULT = Path(PROMPTS_DIR, os.getenv("PROMPT_DEFAULT", "default_llama.md"))
	PROMPT_SUMMARY = Path(PROMPTS_DIR, os.getenv("PROMPT_SUMMARY", "summary_llama.md"))
	PROMPT_AI_INSIGHT = Path(PROMPTS_DIR, os.getenv("PROMPT_AI_INSIGHT", "ai_insight_llama.md"))
else:
	PROMPT_DEFAULT = Path(PROMPTS_DIR, os.getenv("PROMPT_DEFAULT", "default.md"))
	PROMPT_SUMMARY = Path(PROMPTS_DIR, os.getenv("PROMPT_SUMMARY", "summary.md"))
	PROMPT_AI_INSIGHT = Path(PROMPTS_DIR, os.getenv("PROMPT_AI_INSIGHT", "ai_insight.md"))

PROMPT_LIBRARIAN = Path(PROMPTS_DIR, os.getenv("PROMPT_LIBRARIAN", "librarian.md"))
PROMPT_DEBUG = Path(PROMPTS_DIR, os.getenv("PROMPT_DEBUG", "debug.md"))

# MongoDB configuration (環境変数で上書き可能)
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", MONGODB_DB)  # デフォルトは設定セクションの値を使用

# TTL settings (optional)
CONVERSATIONS_TTL_DAYS = int(os.getenv("CONVERSATIONS_TTL_DAYS")) if os.getenv("CONVERSATIONS_TTL_DAYS") else None
RECOMMEND_LOG_TTL_DAYS = int(os.getenv("RECOMMEND_LOG_TTL_DAYS")) if os.getenv("RECOMMEND_LOG_TTL_DAYS") else None
AI_INSIGHTS_TTL_DAYS = int(os.getenv("AI_INSIGHTS_TTL_DAYS")) if os.getenv("AI_INSIGHTS_TTL_DAYS") else None
