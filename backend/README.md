# LiVraria Backend

LiVraria（図書館AI）のバックエンドAPIサーバー

## 📁 ディレクトリ構成

```
backend/
├── api/                    # FastAPI アプリケーション
│   ├── server.py          # メインサーバー
│   ├── models.py          # データモデル
│   ├── datastore.py       # データストア
│   ├── gemini.py          # Gemini LLM統合
│   └── llm.py             # Ollama LLM統合
├── search/                 # 書籍検索API
│   ├── rakuten_books.py   # 楽天ブックスAPI
│   ├── cinii_search.py    # CiNii Books API
│   └── google_books.py    # Google Books API
├── test/                   # テストコード
├── requirements.txt        # 本番環境用依存関係
├── requirements-dev.txt    # 開発環境用依存関係
└── run.py                  # サーバー起動スクリプト
```

## 🚀 セットアップ

### 1. 仮想環境の作成

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windowsの場合: .venv\Scripts\activate
```

### 2. 依存関係のインストール

#### 本番環境

```bash
pip install -r requirements.txt
```

#### 開発環境（推奨）

```bash
pip install -r requirements-dev.txt
```

`requirements-dev.txt`には以下が含まれます：
- 本番環境の全依存関係（`-r requirements.txt`）
- 開発ツール（rich, typer, fastapi-cli等）
- デバッグツール

### 3. 環境変数の設定

プロジェクトルートの`.env`ファイルを設定してください：

```bash
# .env.templateを参考に.envを作成
cp ../.env.template ../.env
# .envを編集してAPIキー等を設定
```

必要な環境変数：
- `GEMINI_API_KEY` - Google Gemini APIキー
- `RAKUTEN_APP_ID` - 楽天アプリケーションID
- `FIREBASE_ACCOUNT_KEY_PATH` - Firebaseサービスアカウントキーのパス

## 🏃 実行方法

### 開発サーバーの起動

```bash
# 方法1: uvicornコマンド（推奨）
uvicorn api.server:app --reload --host 0.0.0.0 --port 8000

# 方法2: run.pyスクリプト
python run.py

# 方法3: FastAPI CLI（requirements-dev.txtインストール時）
fastapi dev api/server.py
```

サーバーが起動したら、以下のURLにアクセスできます：
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🧪 テスト

```bash
# テストの実行（pytest使用時）
pytest test/

# 特定のテストファイルを実行
pytest test/test_basic_integration.py
```

## 📦 依存関係の管理

### requirements.txt（本番環境）

最小限の依存関係のみを含みます：
- FastAPI, Uvicorn
- Firebase Admin SDK
- Google Gemini API
- Pydantic
- Requests
- python-dotenv

### requirements-dev.txt（開発環境）

本番環境の依存関係に加えて、以下を含みます：
- **rich**: 美しいターミナル出力
- **typer**: CLIツール作成
- **fastapi-cli**: FastAPI開発ツール

### 依存関係の更新

```bash
# 現在インストールされているパッケージの確認
pip freeze

# 依存関係の更新
pip install --upgrade -r requirements-dev.txt

# 新しいパッケージの追加後、requirements.txtを更新
pip freeze > requirements.txt  # 注意: 手動で整理が必要
```

## 🔧 LLMバックエンドの切り替え

環境変数`LLM_BACKEND`で使用するLLMを切り替えられます：

```bash
# Gemini（デフォルト）
export LLM_BACKEND=gemini

# Ollama（ローカルLLM）
export LLM_BACKEND=ollama
```

## 📝 API エンドポイント

主要なエンドポイント：

- `GET /` - ヘルスチェック
- `POST /users` - ユーザー作成
- `GET /users/{user_id}` - ユーザー情報取得
- `POST /sessions/{session_id}/messages` - メッセージ送信
- `POST /nfc/auth` - NFC認証
- `POST /nfc/register` - NFC登録

詳細は http://localhost:8000/docs を参照してください。

## 🔐 認証

Firebase Authenticationを使用しています。
- フロントエンドでFirebase認証を行い、IDトークンを取得
- APIリクエストのAuthorizationヘッダーに`Bearer <token>`を設定

## 🐛 トラブルシューティング

### ポート8000が既に使用されている

```bash
# 別のポートを使用
uvicorn api.server:app --reload --port 8001
```

### Firebase初期化エラー

- `FIREBASE_ACCOUNT_KEY_PATH`が正しく設定されているか確認
- サービスアカウントキーファイルが存在するか確認

### LLM APIエラー

- `GEMINI_API_KEY`が正しく設定されているか確認
- APIキーの使用制限を確認

## 📚 関連ドキュメント

- [FastAPI公式ドキュメント](https://fastapi.tiangolo.com/)
- [Firebase Admin SDK](https://firebase.google.com/docs/admin/setup)
- [Google Gemini API](https://ai.google.dev/docs)
