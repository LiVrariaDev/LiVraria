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


def clear_data_dir() -> None:
	"""テスト用の DATA_DIR の中身（ファイルとディレクトリ。traces/ など）をすべて消す。"""
	import shutil
	from backend import DATA_DIR

	for path in DATA_DIR.iterdir():
		if path.is_dir() and not path.is_symlink():
			shutil.rmtree(path)
		else:
			path.unlink()
