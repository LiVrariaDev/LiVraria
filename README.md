# LiVraria

## セットアップ手順
1. リポジトリをクローンする
2. Python仮想環境を作成し、依存パッケージを`requirements.txt`からインストール
3. Node.js依存パッケージをインストール
4. `.env`の作成

```sh
python -m venv LiVraria_py
source LiVraria_py/bin/activate
sudo apt install cmake postgresql
pip install -r requirements.txt
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