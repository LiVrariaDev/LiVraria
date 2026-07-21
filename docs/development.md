# 開発ガイド

## 前提条件

- Node.js: ルート `README.md` では v22.14.0 以降を案内している。フロントエンドは `^20.19.0 || >=22.12.0` を要求する。
- pnpm: ルート `package.json` は `pnpm@10.14.0` を指定している。
- Python: CI と Raspberry Pi のセットアップスクリプトは Python 3.11 を使用する。

開発環境の正確な組み合わせは、実際にセットアップとビルドを通して確認する。上記以外の OS 固有の前提は未確認である。

## 初回セットアップ

リポジトリルートで実行する。

```bash
pnpm install
pnpm run setup
```

`pnpm run setup` は、フロントエンドとバックエンドのセットアップを並列に実行する。

- `pnpm run install:front`: `frontend/` の依存関係をインストールする。
- `pnpm run install:back`: `backend/.venv` を作成し、`backend/requirements-dev.txt` をインストールする。ルートに `.env` がなければ `.env.template` から作成する。

作成された `.env` には値が入っていないため、起動前に設定が必要である。設定項目は [設定](configuration.md) を参照する。

## 起動

```bash
pnpm run start
```

上記は以下を同時に起動する。

- フロントエンド: `pnpm -C frontend run dev`（通常は `http://localhost:5173`）
- バックエンド: `node scripts/run-backend.js` → `python -m backend.run`（通常は `http://localhost:8000`）

個別に起動する場合は `pnpm run dev:front`、`pnpm run dev:back` を使用する。

## HTTPS を使う開発

マイク入力など、ブラウザで HTTPS を必要とする機能を試す場合は、ルートの `certs/key.pem` と `certs/cert.pem` を用意し、`USE_SSL=true` を設定する。`backend/run.py` と `frontend/vite.config.js` はこの設定を読む。

自己署名証明書はローカル開発用である。証明書の配布や本番利用の手順は、このリポジトリでは確認できていない。

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -nodes -keyout certs/key.pem -out certs/cert.pem -days 365 -subj "/CN=localhost"
```

## 検証

フロントエンドのビルドは次のコマンドで確認できる。

```bash
pnpm -C frontend run build
```

CI はフロントエンドのビルド、バックエンド依存関係のインストール、限定的な `flake8` 検査を定義している。バックエンドテストは Firebase や外部 API の設定を要する可能性があるため、必要な設定を持たない環境では実行結果を保証しない。

## Docker

Docker はこの開発手順に含めない。理由と再構築の条件は [Docker の状態](docker.md) を参照する。
