#!/usr/bin/env python
"""
LiVraria Backend Entry Point

このファイルからサーバーを起動することで、環境変数の読み込みとパス設定を一元管理します。

使い方:
    python backend/run.py
    または
    python -m backend.run
"""
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加（python backend/run.py で実行する場合に必要）
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import os

# サーバーを起動
import uvicorn
from backend.api.server import app

if __name__ == "__main__":
    print(f"Starting LiVraria Backend Server...")
    
    # 環境変数から取得（デフォルト値付き）
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    
    # Uvicornでサーバー起動（import string形式でreloadをサポート）
    uvicorn.run(
        "backend.api.server:app",  # import string形式
        host=host,
        port=port,
        reload=True,  # 開発時は自動リロード
        log_level="info"
    )
