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
PROMPTS_DIR = Path(PROJECT_ROOT, os.getenv("PROMPTS_DIR"))
DATA_DIR = Path(PROJECT_ROOT, os.getenv("DATA_DIR"))
FIREBASE_ACCOUNT_KEY_PATH = Path(PROJECT_ROOT, os.getenv("FIREBASE_ACCOUNT_KEY_PATH"))

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


