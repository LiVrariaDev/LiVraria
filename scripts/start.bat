@echo off
REM スクリプトのディレクトリを取得してプロジェクトルートに移動
cd /d "%~dp0\.."

echo === LiVraria 起動中 ===
echo プロジェクトルート: %CD%

REM Backend起動（新しいウィンドウで）
echo Backend起動中...
start "LiVraria Backend" cmd /k "venv\Scripts\activate.bat && python -m backend.run"

REM Frontend起動（新しいウィンドウで）
echo Frontend起動中...
start "LiVraria Frontend" cmd /k "cd frontend && pnpm run dev"

echo === サーバー起動完了 ===
echo 各ウィンドウを閉じると対応するサーバーが停止します
pause
