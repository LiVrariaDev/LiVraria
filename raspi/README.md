# NFC API Server for Raspberry Pi

Raspberry Pi上で動作するNFCカード読み取りAPIサーバーです。フロントエンドからのHTTPリクエストに応答してNFCカードのIDmを返却します。

## 機能

- NFCカード読み取り（ポーリング方式）
- タイムアウト制御
- CORS対応（フロントエンドからのアクセスを許可）
- systemdによる自動起動
- **音声合成（OpenJTalk）**: テキストを音声ファイルに変換してブラウザに返す
- **VOSK音声認識（WebSocket）**: リアルタイム音声認識（日本語）

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

### WS /stt/stream

VOSK音声認識WebSocketエンドポイント。リアルタイムで音声認識を行います。

**接続URL:**
```
ws://localhost:8000/stt/stream
```

**送信データ（クライアント → サーバー）:**
- **形式:** Binary (ArrayBuffer)
- **内容:** PCM 16-bit, 16000Hz, モノラル音声データ
- **サイズ:** 任意（通常4096サンプル = 8192バイト）

**受信データ（サーバー → クライアント）:**

```json
// 部分結果（認識中）
{
  "type": "partial",
  "text": "こんにち"
}

// 確定結果（発話終了時）
{
  "type": "final",
  "text": "こんにちは"
}

// エラー（VOSKモデル未ロード時）
{
  "error": "VOSK model not loaded",
  "fallback": "web_speech_api"
}
```

**使用例:**

```javascript
// WebSocket接続
const ws = new WebSocket('ws://localhost:8000/stt/stream');

// 音声キャプチャ
const stream = await navigator.mediaDevices.getUserMedia({
    audio: { sampleRate: 16000, channelCount: 1 }
});

const audioContext = new AudioContext({ sampleRate: 16000 });
const source = audioContext.createMediaStreamSource(stream);
const processor = audioContext.createScriptProcessor(4096, 1, 1);

processor.onaudioprocess = (e) => {
    if (ws.readyState === WebSocket.OPEN) {
        const inputData = e.inputBuffer.getChannelData(0);
        // Float32 → Int16 変換
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
            const s = Math.max(-1, Math.min(1, inputData[i]));
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        ws.send(pcm16.buffer);
    }
};

source.connect(processor);
processor.connect(audioContext.destination);

// 認識結果の受信
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'final') {
        console.log('確定:', data.text);
    } else if (data.type === 'partial') {
        console.log('認識中:', data.text);
    }
};
```

> [!NOTE]
> VOSKモデルが正しくロードされていない場合、エラーメッセージが返されます。フロントエンド側でWeb Speech APIへのフォールバックを実装してください。


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

## 今後の改善点

### VOSK音声認識の改善

以下の項目は、VOSK音声認識機能の品質向上のために検討すべき改善点です：

#### 1. WebSocket自動再接続
**現状:** WebSocket切断時に手動で再接続が必要  
**改善案:** 切断検知時に自動的に再接続を試みる機能を実装

```javascript
// 例: 指数バックオフによる再接続
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;

ws.onclose = () => {
    if (reconnectAttempts < maxReconnectAttempts) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
        setTimeout(() => {
            reconnectAttempts++;
            reconnect();
        }, delay);
    }
};
```

#### 2. VOSK初期化失敗時の詳細なエラーハンドリング
**現状:** VOSK初期化失敗時にWeb Speech APIにフォールバックするが、エラー詳細が不明  
**改善案:** 
- モデルファイルの存在確認
- モデルバージョンの検証
- メモリ不足の検知
- ユーザーへの詳細なエラーメッセージ表示

#### 3. 音声認識精度の向上
**現状:** 基本的な設定のみ  
**改善案:**
- ノイズキャンセリングの最適化
- マイク入力レベルの自動調整
- 音響モデルのファインチューニング
- 言語モデルのカスタマイズ（図書館用語など）

#### 4. パフォーマンス最適化
**現状:** ScriptProcessorNode使用（非推奨API）  
**改善案:** AudioWorkletへの移行

```javascript
// AudioWorklet example
class VoskProcessor extends AudioWorkletProcessor {
    process(inputs, outputs, parameters) {
        const input = inputs[0][0];
        // PCM変換とWebSocket送信
        return true;
    }
}
registerProcessor('vosk-processor', VoskProcessor);
```

#### 5. TTS完了検知の改善
**現状:** 文字数ベースの推定時間で待機  
**改善案:**
- Raspberry Pi側から再生完了通知を送信
- WebSocketまたはServer-Sent Eventsで通知
- より正確なタイミングでの音声認識再開

```python
# 例: aplayの完了を待つ
process = subprocess.Popen(['aplay', '-D', 'plughw:3,0', wav_path])
process.wait()  # 再生完了まで待機
ws.send(json.dumps({"type": "tts_completed"}))
```

#### 6. マルチユーザー対応
**現状:** 単一セッションのみ  
**改善案:**
- セッションIDによる複数ユーザーの同時音声認識
- ユーザーごとの音響モデル適応

#### 7. 音声認識履歴の保存
**現状:** 認識結果は即座に破棄  
**改善案:**
- 認識履歴のログ保存
- 誤認識パターンの分析
- モデル改善のためのデータ収集

### 実装優先度

| 優先度 | 項目 | 理由 |
|--------|------|------|
| 高 | 4. AudioWorkletへの移行 | ScriptProcessorNodeは非推奨 |
| 高 | 5. TTS完了検知の改善 | ユーザー体験の向上 |
| 中 | 1. WebSocket自動再接続 | 安定性の向上 |
| 中 | 2. エラーハンドリング | デバッグの効率化 |
| 低 | 3. 音声認識精度の向上 | 長期的な品質改善 |
| 低 | 6. マルチユーザー対応 | スケーラビリティ |
| 低 | 7. 音声認識履歴の保存 | データ分析 |

