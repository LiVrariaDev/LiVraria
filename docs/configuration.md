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

以下は任意で、未設定時は既定値を使う。

| 変数 | 用途 |
| --- | --- |
| `GEMINI_CHAT_MODEL` | 会話用モデル。既定は `gemini-3.5-flash-lite`。 |
| `GEMINI_SUMMARY_MODEL` | 要約と AI Insights 用モデル。既定は `gemini-4-hydrogen`。 |
| `GEMINI_LIGHT_MODEL` | キーワード抽出などの軽量処理用モデル。既定は `gemini-3.5-flash-lite`（`gemini-2.5-flash-lite` は新規ユーザーには提供終了で 404 になる）。 |
| `GEMINI_CHAT_THINKING` / `GEMINI_SUMMARY_THINKING` / `GEMINI_LIGHT_THINKING` | 役割ごとの思考の段階（Gemini 3 以降のモデルの `thinking_level`）。`minimal` / `low` / `medium` / `high` / `xhigh`、または `default`（モデルの既定に任せる）。未設定時は要約だけ `low`（`gemini-4-hydrogen` は `minimal` 非対応）、会話と軽量はモデルの既定（`gemini-3.5-flash-lite` は `minimal`）。不正な値は無視して未設定時の値を使う。2.5 系のモデルには渡さない（`thinking_budget=0` を使う）。 |
| `GEMINI_API_MAX_RETRIES` | Gemini SDK 内のリトライ回数。既定は 1。 |
| `GEMINI_API_TIMEOUT` | Gemini API のタイムアウト秒数。既定は 30。 |
| `LIVRARIA_GRAPH` | 会話グラフの版。`v1` は今のグラフ（`backend/api/llm.py`）、`v2` は理解→振り分け→聞き取り／検索方針→検索→選書の新しいグラフ（`backend/api/graph_v2.py`、プロンプトは `backend/api/prompts/v2/`）。未設定や不正な値のときは `v1`。 |

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

`VITE_DEVICE_KEY` は NFC ログイン時に `X-Device-Key` ヘッダーとして送る端末共有キーで、バックエンドの `LIVRARIA_DEVICE_KEY` と同じ値にする。未設定または不一致の場合、NFC ログインはできない（メールアドレスでのログインは可能）。

Vite の `VITE_` 変数はブラウザ向けビルドに埋め込まれる。公開してよい Firebase クライアント設定だけを入れ、秘密情報を入れない。`VITE_DEVICE_KEY` も端末のブラウザから読めるため、端末を不特定多数のブラウザに公開しない前提でのみ有効である。

## 任意の値

| 変数 | 実装上の用途 |
| --- | --- |
| `BACKEND_HOST` / `BACKEND_PORT` | `backend.run` の待受先。既定は `0.0.0.0:8000`。 |
| `USE_SSL` | `true` のとき、開発用の `certs/key.pem` と `certs/cert.pem` を使用する。 |
| `ALLOWED_ORIGINS` | バックエンド CORS 許可オリジンをカンマ区切りで追加する（`localhost:5173` は既定で許可）。旧名 `PRODUCTION_ORIGINS` も使用可。 |
| `LIVRARIA_DEVICE_KEY` | NFC ログイン（`/nfc/auth`）を許可する端末共有キー。未設定時は NFC ログインを無効にする。 |
| `LIVRARIA_DEBUG` | `true` のとき、デバッグ API（`/debug/*`）を有効にし、会話のトレースを記録する。開発用 PC でのみ `true` にする。既定は `false`。 |
| `LIVRARIA_ADMIN_KEY` | デバッグ API の管理者キー（`X-Admin-Key` ヘッダー）。`LIVRARIA_DEVICE_KEY` とは別の値にする。未設定時、デバッグ API は 503 を返す。 |
| `LIVRARIA_TRACE_LIMIT` | メモリに残すトレースのターン数。既定は 500。 |
| `CINII_APPID` | CiNii Books API（大学図書館検索）のアプリケーション ID。未設定時は大学図書館検索が 503 を返す。 |
| `LIVRARIA_DATA_DIR` | JSON データの保存先。既定は `backend/api/data`。 |
| `LLM_BACKEND` | 現行運用は `gemini`。未指定時も `gemini` となる。`ollama` を指定する実装はあるが、運用対象外である。 |
| `RAKUTEN_APP_ID` | 現行で利用する楽天ブックス API のアプリケーション ID。 |
| `SESSION_TIMEOUT` | セッション監視の秒数。既定は 1800。 |

`.env.template` には MongoDB 用の値も残っているが、現行のデータストア実装は JSON ファイルを利用する。MongoDB 用の値は通常の設定対象にしない。

## デモアカウントの学習停止

展示で共有デモアカウントを使う場合は、`backend/tools/demo_account.py` で学習(要約と AI Insights の更新)を止められる。**バックエンドの停止中に実行すること**(稼働中に実行すると、バックエンドの次の保存で上書きされる)。

```bash
python -m backend.tools.demo_account show <user_id>
python -m backend.tools.demo_account learning <user_id> on|off
python -m backend.tools.demo_account set-insights <user_id> <file>
```

## 現行の外部サービス

LLM は Gemini を利用する。`backend/api/llm.py` は、会話・要約・軽量処理の役割ごとに Gemini のモデルを選ぶ（上記の環境変数）。書籍検索は楽天ブックス API、会話グラフ v2 の検索方針の参考にレファレンス協同データベース（レファ協）API、公共図書館の蔵書確認はカーリル、大学図書館の所蔵検索は CiNii Books を利用する。Google Books 向けの実装もリポジトリには存在するが、現行運用の対象ではない。

## 本番公開時の設定

Nginx を用いる公開構成では、少なくとも `VITE_API_BASE_URL` と `PRODUCTION_ORIGINS` が公開 URL と一致している必要がある。Nginx、TLS、バックエンドプロセス管理の具体的な設定は未検証であり、[デプロイ方針](deployment.md) の確認待ち事項を解消してから確定する。

## デバッグ画面

開発用 PC で `LIVRARIA_DEBUG=true` と `LIVRARIA_ADMIN_KEY` を設定してバックエンドを起動し、`http://localhost:5173/?view=debug` を開いて管理者キーを入力すると、セッションごとのターン一覧、LangGraph のグラフ、ノードごとの処理内容、役割別の LLM 使用量を確認できる。

トレースは `DATA_DIR/traces/YYYY-MM-DD.jsonl` に1ターン1行で追記される。全利用者の発言を含むため、取り扱いに注意する。自動では削除されないので、不要になったら手で消す。
