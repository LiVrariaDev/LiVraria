# フロントエンドセットアップ

## 前提条件

- Node.js 24.x
- pnpm

## セットアップ手順

### 1. 依存関係のインストール

```bash
cd frontend
pnpm install
```

### 2. VOSKモデルのダウンロード

音声認識機能を使用する場合、VOSKモデルをダウンロードして配置する必要があります。
**注意:** `vosk-browser` は `.zip` ファイルをそのまま読み込むため、解凍せずに配置してください。（※以前の手順と異なります）

```bash
cd frontend/public
mkdir -p models
cd models

# VOSKモデルをダウンロード (ZIPのまま配置)
wget https://alphacephei.com/vosk/models/vosk-model-small-ja-0.22.zip
```

ディレクトリ構造：
```
frontend/public/models/
└── vosk-model-small-ja-0.22.zip
```

> [!NOTE]
> VOSKモデルは Apache License 2.0 でライセンスされています。
> 詳細: https://alphacephei.com/vosk/models

### 3. 開発サーバーの起動

```bash
cd frontend
pnpm dev
```

ブラウザで http://localhost:5173 にアクセスしてください。

## 音声認識について

このアプリケーションは **Vosk-browser (WebAssembly)** を使用してブラウザ内で音声認識を行います。

- ✅ オフライン動作（モデルダウンロード後）
- ✅ サーバー不要
- ✅ 低レイテンシー
- ⚠️ 初回ロード時にモデルを読み込むため、少し時間がかかります

VOSKモデルが見つからない場合、自動的に **Web Speech API** にフォールバックします。
