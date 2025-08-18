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
cp .env.example .env
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
cp .env.example .env
# .envを編集してAPIキーを記入
python gemini-chat.py
```