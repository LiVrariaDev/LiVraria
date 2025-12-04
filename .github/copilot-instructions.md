# Copilot Instructions

## 1. プロジェクト概要
- **LiVraria**は、FastAPIベースのバックエンドとVue 3 + Viteベースのフロントエンドで構成される、AIチャットと書籍検索機能を持つWebアプリケーションです。
- **バックエンド**: [`backend/api/server.py`](backend/api/server.py) を中心としたFastAPIサーバー。Gemini APIを利用したチャット機能 ([`backend/api/gemini.py`](backend/api/gemini.py))、顔認識 ([`backend/face_rec/`](backend/face_rec/))、外部APIによる書籍検索 ([`backend/search/`](backend/search/)) を提供します。
- **フロントエンド**: [`frontend/src/main.js`](frontend/src/main.js) をエントリーポイントとするVue 3アプリケーション。
- **技術仕様**: 詳細な要件やAPI仕様は、必ず [`docs/technical_specs.md`](docs/technical_specs.md) を参照してください。
- **セットアップ**: 手順はルートの [`README.md`](README.md) に従います。Python仮想環境と`pnpm`によるパッケージ管理が前提です。

## 2. 共通開発方針
- **ディレクトリ構成**: `backend`と`frontend`の役割分担を厳守し、コードや依存関係を混在させないでください。
- **コーディング規約**:
    - Python: 型ヒントとdocstringを必ず付与してください。
    - Vue: `<script setup>` 構文とTypeScriptの利用を推奨します。
- **機密情報**: APIキーなどのシークレット値は `.env` ファイルで管理し、コミットしないでください。サンプルは `template.env` に記載します。
- **ドキュメント**: 機能追加や仕様変更の際は、[`README.md`](README.md) と [`docs/technical_specs.md`](docs/technical_specs.md) を必ず更新してください。

## 3. バックエンド開発指針

### 3.1. チャットAPI ([`backend/api/`](backend/api/))
- **エンドポイント**: 新規追加や変更は [`backend/api/server.py`](backend/api/server.py) に行います。`/chat/default` や `/chat/librarian` のように、プロンプトに応じたエンドポイントを作成します。
- **共通処理**: チャットのコアロジックは [`chat_prompt`](backend/api/server.py) 関数に集約されています。セッション管理には `sessions` 辞書を使用します。
- **Gemini連携**: Gemini APIとの通信は [`backend.api.gemini.gemini_chat`](backend/api/gemini.py) 関数を介して行います。
- **プロンプト**: プロンプトは [`backend/api/prompts/`](backend/api/prompts/) ディレクトリにMarkdownファイルとして格納します。プロンプトのテストや調整は [`backend/AI_prompt.ipynb`](backend/AI_prompt.ipynb) を活用してください。

### 3.2. 書籍検索 ([`backend/search/`](backend/search/))
- **機能**: カーリルAPI ([`backend/search/calil.py`](backend/search/calil.py)) やCiNii API ([`backend/search/cinii_search.py`](backend/search/cinii_search.py)) を利用して書籍情報を検索します。
- **プロトタイプ**: NDL（国立国会図書館）サーチを利用した検索プロトタイプが [`backend/chat-search/prototype.py`](backend/chat-search/prototype.py) にあります。キーワード抽出ロジックなどを参考にしてください。

### 3.3. 顔認識 ([`backend/face_rec/`](backend/face_rec/))
- **学習**: [`backend.face_rec.learn_face.learn_face`](backend/face_rec/learn_face.py) を実行して、`images/` 内の画像から顔の特徴量を学習し、`face_encodings.json` を生成します。
- **推論**: [`backend.face_rec.face_detection.face_rec`](backend/face_rec/face_detection.py) を使用して、入力画像が既知の顔と一致するか判定します。
- **テスト**: 動作確認は [`backend/face_rec/face_recognition_test.py`](backend/face_rec/face_recognition_test.py) を参考にしてください。

## 4. フロントエンド開発指針
- **コンポーネント**: 再利用可能なUI部品は [`frontend/src/components/`](frontend/src/components/) に配置します。
- **API通信**: バックエンドAPIとの通信は、環境変数からAPIのベースURLを取得して実装します。
- **エイリアス**: `@` エイリアス（`./src`）が [`frontend/vite.config.js`](frontend/vite.config.js) で設定されています。インポートパスの解決に活用してください。
- **スタイル**: グローバルスタイルは [`frontend/src/assets/main.css`](frontend/src/assets/main.css) と [`frontend/src/assets/base.css`](frontend/src/assets/base.css) で定義されています。

## 5. 実行コマンド
- **バックエンド起動**:
  ```sh
  # venv環境を有効化
  source venv/bin/activate
  # サーバー起動
  uvicorn backend.api.server:app --reload
  ```
- **フロントエンド起動**:
  ```sh
  # ルートディレクトリで実行
  pnpm --filter frontend dev
  ```
- **依存関係のインストール**:
  ```sh
  # Python
  pip install -r backend/requirements.txt
  # Node.js
  pnpm install
  ```

## 6. PR/レビュー時チェックリスト
- [ ] 依存パッケージを更新した場合、`backend/requirements.txt` または `pnpm-lock.yaml` が更新されているか。
- [ ] 仕様変更が [`docs/technical_specs.md`](docs/technical_specs.md) と [`README.md`](README.md) に反映されているか。
- [ ] `.env` に記載すべきAPIキーや個人情報がコードに含まれていないか。
- [ ] ローカルでバックエンドとフロントエンドを両方起動し、主要なユースケースが正常に動作することを確認したか。