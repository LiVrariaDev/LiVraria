# LiVraria

## セットアップ手順
1. リポジトリをクローンする
2. Python仮想環境を作成し、依存パッケージを`requirements.txt`からインストール
3. Node.js依存パッケージをインストール
4. `.env`の作成

```sh
python -m venv LiVraria_py
source LiVraria_py/bin/activate
pip install -r requirements.txt
pnpm install
```

## 環境
- Python 3.11.4
- nodejs v22.14.0
- pnpm 10.8.1