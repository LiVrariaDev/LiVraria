#!/bin/bash

# スクリプトのディレクトリを取得してプロジェクトルートに移動
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "=== LiVraria 起動中 ==="
echo "プロジェクトルート: $PROJECT_ROOT"

# Backend起動
echo "Backend起動中..."

# Windows Git Bash対応: bin/とScripts/の両方をチェック
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
elif [ -f venv/Scripts/activate ]; then
    source venv/Scripts/activate
else
    echo "エラー: 仮想環境のactivateスクリプトが見つかりません"
    echo "先に ./scripts/setup.sh を実行してください"
    exit 1
fi

python -m backend.run &
BACKEND_PID=$!

# Frontend起動
echo "Frontend起動中..."
cd frontend
pnpm run dev &
FRONTEND_PID=$!

echo "=== サーバー起動完了 ==="
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "終了するには Ctrl+C を押してください"

# Ctrl+Cで両方のプロセスを終了
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
