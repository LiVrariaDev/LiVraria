#!/bin/bash
set -e

# スクリプトのディレクトリを取得してプロジェクトルートに移動
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "=== LiVraria セットアップ開始 ==="
echo "プロジェクトルート: $PROJECT_ROOT"

# Frontend Install
echo "Frontend依存関係をインストール中..."
cd frontend
pnpm install
cd ..

# Backend Install
echo "Backend仮想環境を作成中..."
if [ ! -d venv ]; then
    python3 -m venv venv
else
    echo "仮想環境は既に存在します"
fi

# Windows Git Bash対応: bin/とScripts/の両方をチェック
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
elif [ -f venv/Scripts/activate ]; then
    source venv/Scripts/activate
else
    echo "エラー: 仮想環境のactivateスクリプトが見つかりません"
    exit 1
fi

echo "Backend依存関係をインストール中..."
pip install -r backend/requirements.txt
pip install python-dotenv fastapi uvicorn google-genai firebase-admin

# 環境変数ファイルのコピー
if [ ! -f .env ]; then
    cp .env.template .env
    echo "✓ .env.templateから.envを作成しました"
    echo "⚠️  .envを編集してAPIキーなどを設定してください"
else
    echo "✓ .envは既に存在します"
fi

echo "=== セットアップ完了 ==="
