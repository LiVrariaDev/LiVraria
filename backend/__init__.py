# Backend package initialization
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# .envのディレクトリがProject ROOT
DOTENV_ROOT = find_dotenv(usecwd=True)
PROJECT_ROOT = Path(DOTENV_ROOT).parent

# .envの読み込み
load_dotenv(dotenv_path=DOTENV_ROOT)

# Directories
PROMPTS_DIR = PROJECT_ROOT / os.getenv("PROMPTS_DIR")
DATA_DIR = PROJECT_ROOT / os.getenv("DATA_DIR")
FIREBASE_ACCOUNT_KEY_PATH = PROJECT_ROOT / os.getenv("FIREBASE_ACCOUNT_KEY_PATH")

# Data file path
CONVERSATIONS_FILE = DATA_DIR / "conversations.json"
USERS_FILE = DATA_DIR / "users.json"
NFC_USERS_FILE = DATA_DIR / "nfc_users.json"

# Prompt file paths
PROMPT_DEFAULT = PROMPTS_DIR / os.getenv("PROMPT_DEFAULT", "default.md")
PROMPT_LIBRARIAN = PROMPTS_DIR / os.getenv("PROMPT_LIBRARIAN", "librarian.md")
PROMPT_SUMMARY = PROMPTS_DIR / os.getenv("PROMPT_SUMMARY", "summary.md")
PROMPT_AI_INSIGHT = PROMPTS_DIR / os.getenv("PROMPT_AI_INSIGHT", "ai_insight.md")
PROMPT_DEBUG = PROMPTS_DIR / os.getenv("PROMPT_DEBUG", "debug.md")


