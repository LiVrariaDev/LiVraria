# 設定

設定はリポジトリルートの `.env` に置く。`.env.template` をコピーして作成し、`.env`、サービスアカウント鍵、証明書を Git に追加しない。

```bash
cp .env.template .env
```

## バックエンド起動に必要な値

`backend/__init__.py` は、起動時に以下の値を確認する。

| 変数 | 用途 |
| --- | --- |
| `FIREBASE_ACCOUNT_KEY_PATH` | Firebase Admin SDK のサービスアカウント鍵ファイルへのパス |
| `FIREBASE_API_KEY` | バックエンドの起動時チェック対象となる Firebase API キー |
| `GEMINI_API_KEY` | 現行の Gemini LLM 設定 |

サービスアカウント鍵の実ファイルはリポジトリ外で管理する。相対パスを指定する場合は、バックエンドをリポジトリルートから起動する前提で解決される。

## フロントエンドで使う値

`frontend/src/firebaseConfig.js` は以下の `VITE_` 接頭辞付き変数を Firebase 設定として読む。

- `VITE_FIREBASE_API_KEY`
- `VITE_FIREBASE_AUTH_DOMAIN`
- `VITE_FIREBASE_PROJECT_ID`
- `VITE_FIREBASE_STORAGE_BUCKET`
- `VITE_FIREBASE_MESSAGING_SENDER_ID`
- `VITE_FIREBASE_APP_ID`
- `VITE_FIREBASE_MEASUREMENT_ID`

`VITE_API_BASE_URL` を設定すると、フロントエンドの API 接続先を変更できる。未設定時は `http://localhost:8000` となる。

Vite の `VITE_` 変数はブラウザ向けビルドに埋め込まれる。公開してよい Firebase クライアント設定だけを入れ、秘密情報を入れない。

## 任意の値

| 変数 | 実装上の用途 |
| --- | --- |
| `BACKEND_HOST` / `BACKEND_PORT` | `backend.run` の待受先。既定は `0.0.0.0:8000`。 |
| `USE_SSL` | `true` のとき、開発用の `certs/key.pem` と `certs/cert.pem` を使用する。 |
| `PRODUCTION_ORIGINS` | バックエンド CORS 許可オリジンをカンマ区切りで追加する。 |
| `LLM_BACKEND` | 現行運用は `gemini`。未指定時も `gemini` となる。`ollama` を指定する実装はあるが、運用対象外である。 |
| `RAKUTEN_APP_ID` | 現行で利用する楽天ブックス API のアプリケーション ID。 |
| `SESSION_TIMEOUT` | セッション監視の秒数。既定は 1800。 |

`.env.template` には MongoDB 用の値も残っているが、現行のデータストア実装は JSON ファイルを利用する。MongoDB 用の値は通常の設定対象にしない。

## 現行の外部サービス

LLM は Gemini を利用する。`backend/api/llm.py` は Gemini のモデルとして `gemini-2.5-flash` を指定している。書籍検索は楽天ブックス API を利用する。CiNii、Calil、Google Books 向けの実装もリポジトリには存在するが、現行運用の対象ではない。

## 本番公開時の設定

Nginx を用いる公開構成では、少なくとも `VITE_API_BASE_URL` と `PRODUCTION_ORIGINS` が公開 URL と一致している必要がある。Nginx、TLS、バックエンドプロセス管理の具体的な設定は未検証であり、[デプロイ方針](deployment.md) の確認待ち事項を解消してから確定する。
