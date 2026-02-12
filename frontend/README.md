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

### 既知の問題と将来の改善点

**Vosk-browserの遅延について**
現在、`vosk-browser` (WebAssembly) を使用した音声認識では、発話終了から認識結果が反映されるまでに数秒の遅延が発生することがあります。
これはメインスレッドで音声処理を行っているためで、入力漏れを防ぐために停止時に3秒間の待機時間を設けています。

**今後の改善案:**
- `AudioWorklet` を使用して音声処理を別スレッド化する
- PCスペックに依存しないサーバーサイド処理に戻す
- Web Speech APIをメインとして使用する設定を追加する
