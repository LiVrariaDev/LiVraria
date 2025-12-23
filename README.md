# LiVraria

図書館向けAI推薦システムのPoC実装

## セットアップ手順

### クイックスタート（推奨）

**Linux/Mac:**
```bash
./scripts/setup.sh
```

**Windows:**
```batch
scripts\setup.bat
```

セットアップ完了後、`.env`ファイルを編集してAPIキーなどを設定してください。

### 手動セットアップ

<details>
<summary>手動でセットアップする場合はこちらをクリック</summary>

#### 1. リポジトリのクローン
```bash
git clone <repository-url>
cd LiVraria
```

#### 2. Backend セットアップ
```bash
# Python仮想環境を作成
python3 -m venv venv
source venv/bin/activate

# 依存パッケージをインストール
pip install -r backend/requirements.txt

# 環境変数ファイルを作成
cp .env.template .env
# .envを編集してAPIキーなどを記入
```

#### 3. Frontend セットアップ
```bash
# pnpmを使用（推奨）
pnpm install
```

</details>

## 環境

### Backend
- Python 3.11.4+
- FastAPI
- Google Gemini API
- Firebase Admin SDK

### Frontend
- Node.js v22.14.0
- pnpm 10.8.1（推奨）
- Vite
- **TailwindCSS v4** (`@tailwindcss/postcss`を使用)

> [!IMPORTANT]
>  TailwindCSS v4を使用しています。`postcss.config.js`では  `'@tailwindcss/postcss': {}`を指定してください。  
> v3の`tailwindcss: {}`は使用しないでください。

### その他
- MongoDB (SQLは学習コストが高い！！！)

## サーバー起動

### クイックスタート（推奨）

**Linux/Mac:**
```bash
./scripts/start.sh
```

**Windows:**
```batch
scripts\start.bat
```

### 手動起動

<details>
<summary>手動で起動する場合はこちらをクリック</summary>

#### Backend
```bash
# 仮想環境を有効化
source venv/bin/activate
pip install -r backend/requirements.txt
# requirementsから読み込めないライブラリ群
pip install python-dotenv uvicorn fastapi google-genai firebase-admin
# サーバー起動（推奨）
python -m backend.run
```
backend/run.pyを実行すると、backend libraryが読み込めないので失敗する

サーバーは `http://0.0.0.0:8000` で起動します（`.env`で変更可能）。

#### Frontend
```bash
# 開発サーバー起動
pnpm --filter frontend dev
```

</details>

## プロジェクト構造

```
LiVraria/
├── backend/
│   ├── __init__.py          # 環境変数とパス設定の一元管理
│   ├── run.py               # サーバー起動エントリーポイント
│   ├── api/
│   │   ├── server.py        # FastAPI サーバー
│   │   ├── datastore.py     # データストア（JSON）
│   │   ├── gemini.py        # Gemini API連携
│   │   ├── models.py        # Pydanticモデル
│   │   ├── prompts/         # AIプロンプトファイル
│   │   └── data/            # JSONデータファイル
│   ├── search/              # 検索機能（CiNii, Calilなど）
│   └── test/                # テストファイル
├── frontend/                # Viteフロントエンド
├── .env                     # 環境変数（gitignore）
├── .env.template            # 環境変数テンプレート
└── README.md
```

## 環境変数設定

`.env.template`をコピーして`.env`を作成し、以下の値を設定してください：

### 必須項目
- `GEMINI_API_KEY`: Google Gemini APIキー
- `FIREBASE_ACCOUNT_KEY_PATH`: Firebase認証用JSONファイルのパス
- `PROMPTS_DIR`: プロンプトファイルのディレクトリ
- `DATA_DIR`: データファイルのディレクトリ

### オプション項目
- `BACKEND_HOST`: バックエンドホスト（デフォルト: `0.0.0.0`）
- `BACKEND_PORT`: バックエンドポート（デフォルト: `8000`）
- `PROMPT_DEFAULT`: デフォルトプロンプトファイル名
- `PROMPT_LIBRARIAN`: 司書モードプロンプトファイル名
- その他、詳細は`.env.template`を参照

## 開発ガイド

### テスト実行
```bash
# 仮想環境を有効化
source venv/bin/activate

# 特定のテストを実行
python -m backend.test.test_firebase_integration

# または pytest を使用
pytest backend/test/
```

### コード構成の原則
- すべてのパス設定は`backend/__init__.py`に集約
- 環境変数は`.env`で管理（`.env.template`を参照）
- サーバー起動は`python -m backend.run`を使用
- テストは`python -m backend.test.<test_name>`で実行

## 注意事項

- **`.env`はコミット禁止**: 機密情報を含むため、必ず`.gitignore`に含めてください
- **仮想環境の使用**: 依存関係の競合を避けるため、必ず仮想環境を使用してください
- **pnpmの推奨**: フロントエンドは`pnpm`の使用を推奨します（`pnpm-lock.yaml`で依存関係を管理）

詳しい技術仕様は `docs/technical_specs.md` を参照してください。

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
