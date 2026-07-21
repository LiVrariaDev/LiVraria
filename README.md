# LiVraria

図書館での利用を想定した、書籍検索・AI 会話・Firebase 認証・NFC 認証を組み合わせるアプリケーションです。

このリポジトリの文書は、実装と照合できた内容だけを現行手順として記載します。設計メモや未検証の運用手順は、現行仕様と区別して扱います。

## 開発を始める

開発環境は Node.js、pnpm、Python を使用します。対応バージョンと詳細なセットアップは [開発ガイド](docs/development.md) を参照してください。

```bash
pnpm install
pnpm run setup
# .env を編集してから実行
pnpm run start
```

`pnpm run setup` はフロントエンド依存関係のインストール、バックエンド用仮想環境の作成、開発用 Python 依存関係のインストールを行います。`.env` がなければ `.env.template` から作成されますが、値は利用者が設定する必要があります。

通常の開発時は、フロントエンドが `http://localhost:5173`、バックエンドが `http://localhost:8000` で起動します。

## Docker について

`docker-compose.yml` と各 Dockerfile はリポジトリに残っていますが、現在の構成での起動・運用は検証していません。Docker は通常の開発・デプロイ手順としてサポートしません。扱いと再構築条件は [Docker の状態](docs/docker.md) を参照してください。

## ドキュメント

- [開発ガイド](docs/development.md): セットアップ、起動、HTTPS、検証
- [設定](docs/configuration.md): `.env` の設定項目と秘密情報の扱い
- [アーキテクチャ](docs/architecture.md): 実装で確認できた構成と責務
- [デプロイ方針](docs/deployment.md): Nginx を前提とした本番公開の方針と確認待ち事項
- [Docker の状態](docs/docker.md): 未検証・非推奨とする理由、再構築の受入条件
- [バックエンド](backend/README.md)
- [フロントエンド](frontend/README.md)
- [Raspberry Pi](raspi/README.md)
- [NFC API サーバー](raspi/nfc/README.md)

## 現在の前提

- 永続データは JSON ファイルを用いる実装であり、MongoDB は利用していません。
- Raspberry Pi 上での実証は `raspi/2nddisp` ブランチの内容で行われました。現在の `main` で同じ構成を再現できるかは未確認です。
- 本番公開は Nginx で静的ファイルを配信し、API サーバーへリバースプロキシする構成を前提とします。具体的な稼働手順は未検証です。

## ライセンス

本プロジェクトは [EUPL v1.2](LICENSE) の下で公開されています。依存ライブラリに関する情報は [NOTICE](NOTICE) を参照してください。
