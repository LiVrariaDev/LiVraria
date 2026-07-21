# フロントエンド

Vue 3 と Vite による Web クライアントです。Firebase Authentication を使用し、既定では `http://localhost:8000` のバックエンド API に接続します。

## セットアップと起動

リポジトリルートから実行します。

```bash
pnpm run install:front
pnpm run dev:front
```

または `frontend/` で直接実行できます。

```bash
pnpm install
pnpm run dev
```

Vite の開発サーバーは外部アクセスを許可する設定（`vite --host`）です。通常の開発 URL は `http://localhost:5173` です。

## 設定

Vite はリポジトリルートを環境変数の読込先に設定しています。Firebase Authentication を利用するには、ルート `.env` に `VITE_FIREBASE_*` の値を設定します。

`VITE_API_BASE_URL` を指定しない場合、API 接続先は `http://localhost:8000` です。別ホストのバックエンドを使う場合はこの値を設定し、バックエンド側の `PRODUCTION_ORIGINS` も整合させてください。

詳細は [設定](../docs/configuration.md) と [開発ガイド](../docs/development.md) を参照してください。

## ビルド

```bash
pnpm run build
```

生成物は `frontend/dist/` です。本番での配信方針は [デプロイ方針](../docs/deployment.md) を参照してください。
