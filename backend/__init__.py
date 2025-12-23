# Backend package initialization
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# .envのディレクトリがProject ROOT
DOTENV_ROOT = find_dotenv(usecwd=True)
PROJECT_ROOT = Path(DOTENV_ROOT).parent

# .envの読み込み
load_dotenv(dotenv_path=DOTENV_ROOT)

# API KEY RATE
GEMINI_API_KEY_RATE = int(os.getenv("GEMINI_API_KEY_RATE", "15"))

# Directories
if not Path(PROJECT_ROOT, ".env").exists():
	raise FileNotFoundError(".env file not found")

# 環境変数の存在チェック
prompts_dir_env = os.getenv("PROMPTS_DIR")
data_dir_env = os.getenv("DATA_DIR")
firebase_key_env = os.getenv("FIREBASE_ACCOUNT_KEY_PATH")
	
if not prompts_dir_env:
	raise ValueError(
		"Environment value 'PROMPTS_DIR' is not set\n"
		"Hint: .env file not found or PROMPTS_DIR value is empty"
	)

if not data_dir_env:
	raise ValueError(
		"Environment value 'DATA_DIR' is not set\n"
		"Hint: .env file not found or DATA_DIR value is empty"
	)

if not firebase_key_env:
	raise ValueError(
		"Environment value 'FIREBASE_ACCOUNT_KEY_PATH' is not set\n"
		"Hint: .env file not found or FIREBASE_ACCOUNT_KEY_PATH value is empty"
	)

# 最低限1だけ設定されているかチェック
if not os.getenv("GEMINI_API_KEY1"):
	raise ValueError(
		"Environment value 'GEMINI_API_KEY1' is not set\n"
		"Hint: .env file not found or GEMINI_API_KEY1 value is empty"
	)

if not os.getenv("FIREBASE_API_KEY"):
	raise ValueError(
		"Environment value 'FIREBASE_API_KEY' is not set\n"
		"Hint: .env file not found or FIREBASE_API_KEY value is empty"
	)

PROMPTS_DIR = Path(PROJECT_ROOT, prompts_dir_env)
DATA_DIR = Path(PROJECT_ROOT, data_dir_env)

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


