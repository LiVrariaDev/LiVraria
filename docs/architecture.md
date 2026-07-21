# アーキテクチャ

この文書は現在の `main` の実装から確認できた構成を示す。実装されていない将来案は含めない。

```text
ブラウザ
  ├─ Vue 3 / Vite フロントエンド
  │    ├─ Firebase Authentication
  │    └─ FastAPI バックエンド
  └─ Raspberry Pi 上では NFC API サーバー（Flask）

FastAPI バックエンド
  ├─ Firebase Admin SDK
  ├─ Gemini（gemini-2.5-flash）による LLM 処理
  ├─ 楽天ブックス API による書籍検索
  └─ JSON データストア
```

## フロントエンド

フロントエンドは `frontend/` にあり、Vue 3 と Vite を使用する。`frontend/src/services/api.js` は `VITE_API_BASE_URL`、または既定値 `http://localhost:8000` に HTTP リクエストを送る。Firebase Authentication の設定は `frontend/src/firebaseConfig.js` で行う。

## バックエンド

バックエンドは `backend/api/server.py` の FastAPI アプリケーションである。ユーザー、会話、NFC の対応情報は `backend/api/data/` 以下の JSON ファイルで扱う。これらの実行時データは Git 管理対象外である。

Firebase ID トークンを必要とする API と、NFC ID を受け取って Firebase Custom Token を発行する API がある。利用可能なエンドポイントは、設定済み環境で起動した API の OpenAPI UI (`/docs`) を確認する。

LLM の現行運用は Gemini であり、`backend/api/llm.py` は `gemini-2.5-flash` を指定する。Ollama、CiNii、Calil、Google Books 向けのコードは存在するが、現行の利用対象ではない。

## Raspberry Pi と NFC

`raspi/nfc/nfc_api_server.py` は Flask による NFC 読み取り用のローカル API サーバーで、`/start-nfc`、`/check-nfc`、`/read-nfc` を提供する。フロントエンドの `frontend/src/services/nfc.js` は既定で `http://localhost:8000` に接続するため、ブラウザを Raspberry Pi 上で動かす構成を前提としている。

Raspberry Pi 上の実証は `raspi/2nddisp` ブランチで確認済みである。セカンドディスプレイ機能の `main` への統合は後日行う予定であり、現在の `main` での再現性は未確認である。

## 本番公開の想定

本番では Nginx がフロントエンドのビルド成果物を配信し、API リクエストを FastAPI にリバースプロキシする構成を前提とする。Nginx 設定、TLS 証明書、プロセス管理、Raspberry Pi のネットワーク配置は未検証である。

## Docker

Docker 構成はこのアーキテクチャのサポート対象ではない。詳細は [Docker の状態](docker.md) を参照する。
