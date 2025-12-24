# Raspberry Pi用モジュール

このディレクトリには、Raspberry Pi上で動作するハードウェア関連のモジュールが含まれています。

## 📁 ディレクトリ構成

```
raspi/
├── nfc/              # NFCカードリーダー関連
│   └── nfcdegozaru.py  # FeliCa IDm読み取りスクリプト
├── requirements.txt  # Raspberry Pi用の依存関係
├── chromium.sh       # Chromiumブラウザ起動スクリプト
└── demo.html         # デモページ
```

## 🚀 セットアップ

### 1. システム依存関係のインストール

#### NFCカードリーダー（RC-S300等）

```bash
sudo apt-get update
sudo apt-get install -y pcscd pcsc-tools libpcsclite-dev
sudo systemctl start pcscd
sudo systemctl enable pcscd
```

### 2. Python依存関係のインストール

```bash
# 仮想環境の作成
python3 -m venv .venv
source .venv/bin/activate

# 依存関係のインストール
pip install -r requirements.txt
```

## 📝 使用方法

### NFCカードリーダー

```bash
# カードリーダーの確認
pcsc_scan

# IDm読み取りスクリプトの実行
python nfc/nfcdegozaru.py
```

## 🔗 バックエンドとの連携

これらのモジュールは、バックエンドAPIサーバーと連携して動作します。
詳細は`../backend/README.md`を参照してください。

## ⚠️ 注意事項

- NFCカードリーダーはRaspberry Pi上でのみ動作します
- `requirements.txt`内の依存関係は、必要に応じてコメントを解除してインストールしてください
