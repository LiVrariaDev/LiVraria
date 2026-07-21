# バックエンド

FastAPI による API サーバーです。Firebase Admin SDK でトークンを検証し、JSON ファイルをデータストアとして使用します。MongoDB は現在利用していません。

## セットアップと起動

通常はリポジトリルートで以下を実行します。

```bash
pnpm run install:back
pnpm run dev:back
```

`install:back` は `backend/.venv` を作成し、`backend/requirements-dev.txt` をインストールします。起動前に、リポジトリルートの `.env` を設定してください。必要な設定は [設定](../docs/configuration.md) を参照してください。

手動でセットアップする場合は、リポジトリルートから実行します。

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
backend/.venv/bin/python -m backend.run
```

既定では `http://0.0.0.0:8000` で起動し、`BACKEND_HOST` と `BACKEND_PORT` で変更できます。`backend.run` は開発用に自動リロードを有効にします。

## データと外部サービス

- `backend/api/data/users.json`
- `backend/api/data/conversations.json`
- `backend/api/data/nfc_users.json`

上記は実行時データであり、Git 管理対象外です。Firebase、Gemini、書籍検索 API への接続には `.env` の設定が必要です。

## API

認証が必要なエンドポイントは Firebase ID トークンを `Authorization: Bearer <token>` で受け取ります。実行中のアプリケーションの OpenAPI UI は `http://localhost:8000/docs` です。

公開 API の詳細は実装と OpenAPI UI を正本とします。代表的な実装は `backend/api/server.py`、書籍検索は `backend/api/routers/search.py` にあります。

## 検証

テストは `backend/test/` にあります。外部サービスと Firebase の設定を必要とするものが含まれるため、実行可否は個別に確認してください。

```bash
backend/.venv/bin/python -m pytest backend/test/
```
