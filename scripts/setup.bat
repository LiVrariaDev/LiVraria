@echo off
REM スクリプトのディレクトリを取得してプロジェクトルートに移動
cd /d "%~dp0\.."

echo === LiVraria セットアップ開始 ===
echo プロジェクトルート: %CD%

REM Frontend Install
echo Frontend依存関係をインストール中...
cd frontend
call pnpm install
cd ..
if errorlevel 1 (
    echo エラー: pnpmのインストールに失敗しました
    pause
    exit /b 1
)

REM Backend Install
echo Backend仮想環境を作成中...
python -m venv venv
if errorlevel 1 (
    echo エラー: 仮想環境の作成に失敗しました
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo Backend依存関係をインストール中...
pip install -r backend\requirements.txt
pip install python-dotenv fastapi uvicorn google-genai firebase-admin

REM 環境変数ファイルのコピー
if not exist .env (
    copy .env.template .env
    echo ✓ .env.templateから.envを作成しました
    echo ⚠️  .envを編集してAPIキーなどを設定してください
) else (
    echo ✓ .envは既に存在します
)

echo === セットアップ完了 ===
pause
