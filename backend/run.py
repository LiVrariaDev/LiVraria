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
    use_ssl = os.getenv("USE_SSL", "false").lower() == "true"
    
    # SSL証明書のパス（プロジェクトルート/certs/）
    cert_dir = project_root / "certs"
    ssl_keyfile = cert_dir / "key.pem"
    ssl_certfile = cert_dir / "cert.pem"
    
    # SSL設定の検証
    if use_ssl:
        if not ssl_keyfile.exists() or not ssl_certfile.exists():
            print(f"エラー: SSL証明書が見つかりません。")
            print(f"以下のコマンドで証明書を生成してください:")
            print(f"  mkdir -p certs")
            print(f"  openssl req -x509 -newkey rsa:4096 -nodes \\")
            print(f"    -keyout certs/key.pem \\")
            print(f"    -out certs/cert.pem \\")
            print(f"    -days 365 \\")
            print(f'    -subj "/CN=localhost"')
            sys.exit(1)
        print(f"HTTPS mode enabled (https://{host}:{port})")
    else:
        print(f"HTTP mode (http://{host}:{port})")
    
    # Uvicornでサーバー起動（import string形式でreloadをサポート）
    uvicorn.run(
        "backend.api.server:app",  # import string形式
        host=host,
        port=port,
        reload=True,  # 開発時は自動リロード
        log_level="info",
        ssl_keyfile=str(ssl_keyfile) if use_ssl else None,
        ssl_certfile=str(ssl_certfile) if use_ssl else None,
    )
