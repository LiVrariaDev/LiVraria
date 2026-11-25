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

## 常駐させる(systemd)

`backend/livraria-backend.service` を使うと、サーバーでバックエンドを systemd で常駐させられます。コピーする前に、`User` と `WorkingDirectory`、`ExecStart` のパスをサーバーに合わせて書き換えてください。

```bash
sudo cp backend/livraria-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now livraria-backend
journalctl -u livraria-backend -f
```

- 必ず1プロセスで動かします。会話中の履歴とロックをプロセスのメモリに持っているため、`--workers` を増やさないでください。
- 停止時に、進行中のセッションの要約と保存が行われます。完了を待つため `TimeoutStopSec=60` としています。
- サーバーでの起動確認はまだ行っていません。

## データと外部サービス

- `backend/api/data/users.json`
- `backend/api/data/conversations.json`
- `backend/api/data/nfc_users.json`

- `backend/api/data/cinii_libraries.json`（CiNii の図書館所在地キャッシュ）

上記は実行時データであり、Git 管理対象外です。Firebase、Gemini、書籍検索 API への接続には `.env` の設定が必要です。

### 大学図書館検索（CiNii Books）

`.env` に `CINII_APPID` を設定します。所蔵館を都道府県で絞り込むには各図書館の所在地が必要なため、
バックエンドのサーバーで一度だけ全図書館の所在地を取得しておきます（約1,900館、5分程度）。

```bash
backend/.venv/bin/python -m backend.search.cinii --prefetch
```

実施しない場合も動作しますが、初めて検索する本では絞り込みに数十秒かかります。
動作確認は `python -m backend.search.cinii --isbn 9784003101018 --pref 東京都` で行えます。

## API

認証が必要なエンドポイントは Firebase ID トークンを `Authorization: Bearer <token>` で受け取ります。実行中のアプリケーションの OpenAPI UI は `http://localhost:8000/docs` です。

公開 API の詳細は実装と OpenAPI UI を正本とします。代表的な実装は `backend/api/server.py`、書籍検索は `backend/api/routers/search.py` にあります。

## 検証

外部サービスや実データを使わない単体テスト（CI でも実行）:

```bash
backend/.venv/bin/python -m pytest backend/test/test_datastore.py backend/test/test_llm_response_sanitization.py \
  backend/test/test_llm_failures.py backend/test/test_server_api.py backend/test/test_cinii.py
```

`backend/test/` のその他のテストは、起動中のサーバーや Firebase の設定を必要とします。
