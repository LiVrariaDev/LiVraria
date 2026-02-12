# NFC API Server for Raspberry Pi

Raspberry Pi上で動作するNFCカード読み取りAPIサーバーです。フロントエンドからのHTTPリクエストに応答してNFCカードのIDmを返却します。

## 機能

- NFCカード読み取り（ポーリング方式）
- タイムアウト制御
- CORS対応（フロントエンドからのアクセスを許可）
- systemdによる自動起動
- **音声合成（OpenJTalk）**: テキストを音声ファイルに変換してブラウザに返す

## セットアップ

### 1. システム依存関係のインストール

```bash
sudo apt-get update
sudo apt-get install -y pcscd pcsc-tools libpcsclite-dev python3-pip
sudo systemctl start pcscd
sudo systemctl enable pcscd
```

### 2. Python依存関係のインストール

```bash
cd /home/pi/LiVraria/raspi
pip3 install -r requirements.txt
```

### 3. NFCカードリーダーの確認

```bash
pcsc_scan
```

カードリーダーが認識されていることを確認してください。

### 4. APIサーバーの起動（手動テスト）

```bash
cd /home/pi/LiVraria/raspi/nfc
python3 nfc_api_server.py
```

ブラウザまたはcurlで動作確認:

```bash
# ヘルスチェック
curl http://localhost:8000/health

# NFC読み取り開始
curl -X POST http://localhost:8000/start-nfc \
  -H "Content-Type: application/json" \
  -d '{"timeout": 20}'

# 読み取り状態確認（別ターミナルで）
curl http://localhost:8000/check-nfc
```

### 5. systemdサービスの設定（自動起動）

```bash
# サービスファイルをコピー
sudo cp /home/pi/LiVraria/raspi/nfc/nfc-api.service /etc/systemd/system/

# サービスファイルのパスを環境に合わせて編集
sudo nano /etc/systemd/system/nfc-api.service

# サービスを有効化
sudo systemctl daemon-reload
sudo systemctl enable nfc-api
sudo systemctl start nfc-api

# ステータス確認
sudo systemctl status nfc-api

# ログ確認
sudo journalctl -u nfc-api -f
```

## APIエンドポイント

### GET /health

ヘルスチェック用エンドポイント

**Response:**
```json
{
  "status": "ok",
  "service": "nfc-api"
}
```

### POST /start-nfc

NFC読み取りを開始します（バックグラウンドで実行）

**Request Body:**
```json
{
  "timeout": 20  // タイムアウト時間（秒）、デフォルト20秒
}
```

**Response:**
```json
{
  "status": "started",
  "message": "NFC reading started"
}
```

### GET /check-nfc

NFC読み取り状態を確認します（ポーリング用）

**Response:**
```json
// 読み取り中
{
  "status": "reading"
}

// 読み取り成功
{
  "status": "success",
  "idm": "01234567890ABCDEF"
}

// タイムアウト
{
  "status": "timeout"
}

// アイドル状態
{
  "status": "idle"
}
```

### GET /read-nfc

最新のNFC読み取り結果を返します（シンプルなポーリング用）

**Response:**
```json
// カード検出
{
  "status": "ok",
  "idm": "01234567890ABCDEF"
}

// カード未検出
{
  "status": "no_card"
}
```

### POST /speak

テキストを音声合成してRaspberry Pi側のスピーカーで再生します（OpenJTalk + aplay使用）

**Request Body:**
```json
{
  "text": "合成するテキスト"
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "Speech playback started"
}
```

**エラーレスポンス:**
```json
// textフィールドがない場合
{
  "status": "error",
  "message": "Missing 'text' field"
}

// テキストが空の場合
{
  "status": "error",
  "message": "Text is empty"
}

// 音声合成に失敗した場合
{
  "status": "error",
  "message": "エラーメッセージ"
}
```

## 使用例（フロントエンド）

### パターン1: start-nfc + check-nfc（推奨）

```javascript
// NFC読み取り開始
const startNfc = async () => {
  nfcLoading.value = true;
  
  // 読み取り開始
  await fetch('http://localhost:8000/start-nfc', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ timeout: 20 })
  });
  
  // ポーリングで状態確認
  const interval = setInterval(async () => {
    const res = await fetch('http://localhost:8000/check-nfc');
    const data = await res.json();
    
    if (data.status === 'success') {
      clearInterval(interval);
      nfcLoading.value = false;
      // 認証処理
      await authenticateWithNfc(data.idm);
    } else if (data.status === 'timeout') {
      clearInterval(interval);
      nfcLoading.value = false;
      alert('タイムアウト');
    }
  }, 1000); // 1秒ごとにポーリング
};
```

### パターン2: read-nfc（シンプル）

```javascript
// ボタンクリック時に読み取り開始
const startNfc = async () => {
  nfcLoading.value = true;
  const startTime = Date.now();
  const timeout = 20000; // 20秒
  
  const interval = setInterval(async () => {
    const res = await fetch('http://localhost:8000/read-nfc');
    const data = await res.json();
    
    if (data.status === 'ok') {
      clearInterval(interval);
      nfcLoading.value = false;
      // 認証処理
      await authenticateWithNfc(data.idm);
    } else if (Date.now() - startTime > timeout) {
      clearInterval(interval);
      nfcLoading.value = false;
      alert('タイムアウト');
    }
  }, 1000);
};
```

### パターン3: 音声合成（/speak）

```javascript
// テキストを音声合成してRaspberry Pi側で再生
const speakText = async (text) => {
  try {
    const res = await fetch('http://localhost:8000/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    
    const result = await res.json();
    
    if (result.status === 'ok') {
      console.log('音声再生開始:', result.message);
    } else {
      console.error('TTS Error:', result.message);
    }
  } catch (error) {
    console.error('Failed to speak:', error);
  }
};

// 使用例
await speakText('図書館へようこそ');
```

> [!NOTE]
> 音声はRaspberry Pi側のスピーカーから再生されます。ブラウザ側では再生されません。

## トラブルシューティング

### カードリーダーが認識されない

```bash
# pcscdサービスの状態確認
sudo systemctl status pcscd

# カードリーダーの確認
pcsc_scan
```

### サービスが起動しない

```bash
# ログ確認
sudo journalctl -u nfc-api -n 50

# 手動起動でエラー確認
cd /home/pi/LiVraria/raspi/nfc
python3 nfc_api_server.py
```

### ポート8000が使用中

```bash
# ポート使用状況確認
sudo lsof -i :8000

# プロセスを終了
sudo kill <PID>
```

## 注意事項

- このAPIサーバーはRaspberry Piのローカル環境でのみ動作します
- 外部からのアクセスは想定していません（localhost:8000のみ）
- NFCカードリーダーがUSB接続されている必要があります
