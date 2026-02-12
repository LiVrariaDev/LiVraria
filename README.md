# LiVraria

図書のAI推薦システム - Firebase認証、NFC認証、AI会話機能を備えた次世代図書館システム

[![CI](https://github.com/LiVrariaDev/LiVraria/actions/workflows/ci.yaml/badge.svg)](https://github.com/LiVrariaDev/LiVraria/actions/workflows/ci.yaml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> [!IMPORTANT]
> 本プロジェクトは開発段階であり、まだ完全ではありません。
> また、このリポジトリのドキュメントはAIによって生成されたものです。
> そのため、誤字脱字や不正確な情報が含まれている可能性があります。

## 主な機能

- **Firebase認証**: メール/パスワード認証
- **NFC認証**: Raspberry Pi + NFCカードリーダーによる非接触ログイン
- **AI会話**: Google Gemini APIによる書籍推薦・会話機能
- **書籍検索**: CiNii、Calil APIとの連携
- **モダンUI**: Vue 3 + TailwindCSS v4

## クイックスタート

### 前提条件

- **Node.js** v22.14.0+
- **Python** 3.11+
- **pnpm** 10.14.0+
- **Docker** (オプション)

### セットアップ

```bash
# 1. ルートでpnpmをインストール（初回のみ）
pnpm install

# 2. フロントエンド・バックエンドの依存関係をインストール
pnpm run setup
```

**個別セットアップ:**
```bash
# フロントエンドのみ
pnpm run install:front

# バックエンドのみ
pnpm run install:back
```

セットアップ完了後、`.env`ファイルを編集してAPIキーを設定してください。

### サーバー起動

```bash
# フロントエンド・バックエンドを同時起動
pnpm run start
```

**個別起動:**
```bash
# フロントエンドのみ
pnpm run dev:front

# バックエンドのみ
pnpm run dev:back
```

- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:5173

### HTTPS対応（マイク入力を使用する場合）

マイク入力を使用するには、ブラウザのセキュリティ要件によりHTTPSが必要です。
開発環境では自己署名証明書（オレオレ証明書）を使用します。

#### 1. 証明書の生成

```bash
# プロジェクトルートで実行
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -nodes -keyout certs/key.pem -out certs/cert.pem -days 365 -subj "/CN=localhost"
```

#### 2. バックエンドをHTTPSで起動

環境変数`USE_SSL=true`を設定してバックエンドを起動します：

```bash
# .envファイルに追加
USE_SSL=true

# または、コマンドラインで指定
USE_SSL=true pnpm run dev:back
```

- **Backend (HTTPS)**: https://localhost:8000
- **Frontend**: http://localhost:5173

> [!WARNING]
> 自己署名証明書を使用するため、ブラウザで「安全ではない」という警告が表示されます。
> 開発環境では「詳細設定」→「localhost にアクセスする（安全ではありません）」を選択して続行してください。

## Docker での起動

```bash
# ビルド
docker compose build

# 起動
docker compose up -d

# ログ確認
docker compose logs -f

# 停止
docker compose down
```

- **Frontend**: http://localhost
- **Backend**: http://localhost:8000

## プロジェクト構造

```
LiVraria/
├── backend/                 # FastAPI バックエンド
│   ├── __init__.py         # 環境変数・パス設定
│   ├── run.py              # サーバー起動エントリーポイント
│   ├── api/
│   │   ├── server.py       # FastAPI サーバー
│   │   ├── datastore.py    # データストア（JSON/MongoDB）
│   │   ├── llm.py          # LLM統合（Gemini/Ollama）
│   │   ├── prompts/        # AIプロンプトファイル
│   │   └── data/           # JSONデータファイル
│   ├── search/             # 検索機能（CiNii, Calil）
│   ├── Dockerfile          # バックエンド用Dockerfile
│   └── requirements.txt    # Python依存関係
├── frontend/               # Vue 3 + Vite フロントエンド
│   ├── src/
│   │   ├── components/     # Vueコンポーネント
│   │   ├── services/       # API通信
│   │   └── firebaseConfig.js
│   ├── Dockerfile          # フロントエンド用Dockerfile
│   └── package.json
├── raspi/                  # Raspberry Pi 関連
│   └── nfc/
│       ├── nfc_api_server.py  # NFC APIサーバー
│       ├── nfc-api.service    # systemdサービス
│       ├── requirements.txt   # Python依存関係
│       └── README.md          # セットアップガイド
├── .github/
│   ├── workflows/
│   │   ├── ci.yaml         # CI（ビルドテスト）
│   │   └── cd.yaml.disabled # CD（デプロイ）※準備中
│   └── dependabot.yml      # 依存関係自動更新
├── docker-compose.yml      # Docker Compose設定
├── .env.template           # 環境変数テンプレート
└── README.md
```

## 環境変数設定

`.env.template`をコピーして`.env`を作成し、以下を設定：

### 必須項目

```bash
# Firebase
FIREBASE_ACCOUNT_KEY_PATH=path/to/serviceAccountKey.json
FIREBASE_API_KEY=your_firebase_api_key

# Gemini API
GEMINI_API_KEY1=your_gemini_api_key

# Rakuten Books API
RAKUTEN_APP_ID=your_rakuten_app_id
```

### オプション項目

```bash
# Backend設定
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# LLMバックエンド（gemini または ollama）
LLM_BACKEND=gemini

# 本番環境CORS（カンマ区切り）
PRODUCTION_ORIGINS=https://example.com,https://www.example.com

# MongoDB（オプション）
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=livraria_dev
```

詳細は`.env.template`を参照してください。

## 開発ガイド

### 推奨: pnpmコマンドを使用

```bash
# セットアップ
pnpm install
pnpm run setup

# 開発サーバー起動
pnpm run start  # フロントエンド・バックエンド同時起動

# 個別起動
pnpm run dev:front  # フロントエンドのみ
pnpm run dev:back   # バックエンドのみ
```

### 手動セットアップ（上級者向け）

<details>
<summary>手動でセットアップする場合</summary>

#### Backend

```bash
# 仮想環境作成・有効化
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存関係インストール
pip install -r backend/requirements.txt

# サーバー起動
python -m backend.run
```

#### Frontend

```bash
# 依存関係インストール
cd frontend
pnpm install

# 開発サーバー起動
pnpm run dev

# ビルド
pnpm run build
```

</details>

### テスト

```bash
# Backend
source .venv/bin/activate
pytest backend/test/

# Frontend（CIで自動実行）
cd frontend
pnpm run build
```

## NFC認証（Raspberry Pi）

Raspberry Pi + NFCカードリーダーでNFC認証を有効化できます。

### セットアップ

```bash
cd raspi/nfc
# systemdオプション: systemdに登録して自動起動する
./setup.sh --systemd
```

詳細は[raspi/nfc/README.md](raspi/nfc/README.md)を参照してください。

## デプロイ

### VPSへのデプロイ

1. **GitHub Secretsを設定**
   - `HOST`: VPSのIPアドレス
   - `USERNAME`: SSHユーザー名
   - `PRIVATE_KEY`: SSH秘密鍵

2. **CDワークフローを有効化**
   ```bash
   mv .github/workflows/cd.yaml.disabled .github/workflows/cd.yaml
   git add .github/workflows/cd.yaml
   git commit -m "feat: enable CD"
   git push
   ```

3. **mainブランチにpush**すると自動デプロイされます

詳細は[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)を参照してください。

## 技術スタック

### Backend
- **FastAPI** - 高速なPython Webフレームワーク
- **Firebase Admin SDK** - 認証・データベース
- **Google Gemini API** - AI会話機能
- **MongoDB** - データベース（オプション）
- **pyscard** - NFCカードリーダー連携

### Frontend
- **Vue 3** - プログレッシブJavaScriptフレームワーク
- **Vite** - 高速ビルドツール
- **TailwindCSS v4** - ユーティリティファーストCSS
- **Firebase** - 認証・データベース

### DevOps
- **Docker** - コンテナ化
- **GitHub Actions** - CI/CD
- **Dependabot** - 依存関係自動更新

## ドキュメント

- [デプロイガイド](docs/DEPLOYMENT.md)
- [RaspberryPi用セットアップガイド](raspi/README.md)
- [NFC APIサーバー](raspi/nfc/README.md)
- [技術仕様](docs/technical_specs.md)

## ライセンス

このプロジェクトは**MIT License**の下で公開されています。詳細は[LICENSE](LICENSE)を参照してください。

```
MIT License
Copyright (c) 2025 LiVrariaDev
```

### 改造版を作成する場合

このソフトウェアを改造・再配布する場合は、[NOTICE](NOTICE)もご確認ください。
改造版には元の著作権表示を保持し、LiVrariaをベースにしている旨を明記してください。

### 使用ライブラリ

このプロジェクトは以下のオープンソースライブラリを使用しています：
- **Frontend**: Vue.js, Firebase, Vite, TailwindCSS
- **Backend**: FastAPI, Firebase Admin SDK, Google Gemini AI, Pydantic, nfcpy

各ライブラリのライセンスについては[NOTICE](NOTICE)を参照してください。
