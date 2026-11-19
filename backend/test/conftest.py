"""pytest 共通設定: 実データや実APIキーに触れずにバックエンドを import できるようにする。"""

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# backend パッケージの import 前に設定する（.env より優先される）
os.environ["LIVRARIA_DATA_DIR"] = tempfile.mkdtemp(prefix="livraria-test-")
os.environ.setdefault("FIREBASE_ACCOUNT_KEY_PATH", "test-dummy-key.json")
os.environ.setdefault("FIREBASE_API_KEY", "test-dummy")
os.environ.setdefault("GEMINI_API_KEY", "test-dummy")
