# LiVraria

## セットアップ手順
1. リポジトリをクローンする
2. Python仮想環境を作成し、
3. 依存パッケージを`requirements.txt`からインストール
4. Node.js依存パッケージをインストール
5. `.env`の作成

```sh
python -m venv venv
source venv/bin/activate
sudo apt install cmake postgresql
pip install -r requirements.txt
cp .env.template .env
# .envを編集してAPIキーを記入
pnpm install
```

## 環境
- Python 3.11.4
- nodejs v22.14.0
- pnpm 10.8.1
    - pnpmを推奨、特にこだわりがなければpnpmを使ってください。
    - npmなどでも依存パッケージのインストールは可能ですが、依存関係の再現のため、`pnpm-lock.yaml`も追跡しています。
- cmake 3.16.3 (dlibのビルドに必要)
- PostgreSQL 12.22

## gemini-chat.py の使い方
1. Python仮想環境を作成（任意）
2. 依存パッケージをインストール
3. `.env`ファイルを作成し、`GEMINI_API_KEY`を記入
4. スクリプトを実行

```sh
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.template .env
```

5. .envにそれぞれ記入 

## .env ポリシー（開発者向け）

- **目的**: `.env` はローカル環境やPoC用の機密設定（APIキー、DB接続文字列など）を格納するためのファイルです。リポジトリには機密情報を含めないでください。
- **テンプレート**: リポジトリルートの `./.env.template` をコピーして `.env` を作成します。
    - 例: ``cp .env.template .env`` その後、各値を編集してください。
- **コミット禁止**: `.env` は必ず `.gitignore` に含め、コミットしないでください。誤ってコミットした場合は速やかにリポジトリ管理者に連絡してください。
- **PoCの暫定値**:
    - `CONVERSATIONS_TTL_DAYS=90`
    - `RECOMMEND_LOG_TTL_DAYS=1095` (3年)
    - `AI_INSIGHTS_TTL_DAYS=1095` (3年)
- **反映方法**: `.env` を更新したら、バックエンド（FastAPI）やフロントエンド（Vite）を再起動してください。
## 例
- Backend の例:
```bash
# 仮想環境を有効化してから
source venv/bin/activate
# 必要に応じて環境を読み込む（シェルによっては不要）
export $(cat .env | xargs)
uvicorn backend.api.server:app --reload --host $BACKEND_HOST --port $BACKEND_PORT
```
- Frontend の例（Vite）:
```bash
# Vite は VITE_ で始まる環境変数を参照します
cp .env.template .env # 初回のみ
pnpm --filter frontend dev
```

詳しい運用方針は `docs/technical_specs.md` にある PoC 決定事項を参照してください。