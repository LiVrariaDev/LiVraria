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
from backend import PROJECT_ROOT, DOTENV_ROOT
import os

# サーバーを起動
import uvicorn
from backend.api.server import app

if __name__ == "__main__":
    print(f"Starting LiVraria Backend Server...")
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"ENV Path: {DOTENV_ROOT}")
    print()
    
    # Uvicornでサーバー起動（import string形式でreloadをサポート）
    uvicorn.run(
        "backend.api.server:app",  # import string形式
        host=os.getenv("BACKEND_HOST"),
        port=os.getenv("BACKEND_PORT"),
        reload=True,  # 開発時は自動リロード
        log_level="info"
    )
