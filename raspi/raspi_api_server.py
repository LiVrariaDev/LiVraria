#!/usr/bin/env python3
"""
NFC API Server for Raspberry Pi
Provides HTTP endpoints for NFC card reading and text-to-speech
"""

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_sock import Sock
import time
import threading
import subprocess
import tempfile
import os
import json
from pathlib import Path
from smartcard.System import readers
from smartcard.util import toHexString

app = Flask(__name__)
CORS(app)  # すべてのオリジンからのアクセスを許可
sock = Sock(app)  # WebSocketサポート

# NFCカード読み取り状態を保持
nfc_state = {
    "status": "idle",  # idle, reading, success, timeout
    "idm": None,
    "last_read_time": None
}
nfc_lock = threading.Lock()

# OpenJTalk設定
OPENJTALK_DICT = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
OPENJTALK_VOICE = "/usr/share/hts-voice/Voice/mei/mei_normal.htsvoice"

# VOSK設定
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "/opt/vosk-model-ja")
vosk_model = None

# VOSK初期化
try:
    from vosk import Model, KaldiRecognizer
    if os.path.exists(VOSK_MODEL_PATH):
        print(f"[VOSK] Loading model from {VOSK_MODEL_PATH}...")
        vosk_model = Model(VOSK_MODEL_PATH)
        print(f"✅ [VOSK] Model loaded successfully")
    else:
        print(f"⚠️  [VOSK] Model not found: {VOSK_MODEL_PATH}")
except ImportError:
    print("⚠️  [VOSK] vosk module not installed")
except Exception as e:
    print(f"❌ [VOSK] Failed to load model: {e}")


def read_card_once(timeout=20):
    """
    NFCカードを1回読み取る（タイムアウト付き）
    
    Args:
        timeout: タイムアウト時間（秒）
    
    Returns:
        dict: {"status": "ok", "idm": "xxx"} or {"status": "timeout"}
    """
    GET_IDM_APDU = [0xFF, 0xCA, 0x00, 0x00, 0x00]
    start_time = time.time()
    
    print(f"[DEBUG] NFC読み取り開始（タイムアウト: {timeout}秒）")
    
    while time.time() - start_time < timeout:
        try:
            reader_list = readers()
            if not reader_list:
                print("[DEBUG] カードリーダーが見つかりません")
                time.sleep(0.5)
                continue
            
            print(f"[DEBUG] カードリーダー検出: {reader_list[0]}")
            reader = reader_list[0]
            connection = reader.createConnection()
            
            print("[DEBUG] 接続試行中...")
            connection.connect()
            
            print("[DEBUG] APDUコマンド送信中...")
            response, sw1, sw2 = connection.transmit(GET_IDM_APDU)
            
            print(f"[DEBUG] レスポンス: sw1={hex(sw1)}, sw2={hex(sw2)}, response={response}")
            
            if sw1 == 0x90 and sw2 == 0x00:
                idm_hex = toHexString(response).replace(" ", "")
                print(f"[DEBUG] ✅ IDm取得成功: {idm_hex}")
                connection.disconnect()
                return {"status": "ok", "idm": idm_hex}
            
            connection.disconnect()
        except Exception as e:
            # カードが置かれていない場合は例外が発生するため無視
            print(f"[DEBUG] 例外発生: {type(e).__name__}: {e}")
            pass
        
        time.sleep(0.5)
    
    print("[DEBUG] ❌ タイムアウト")
    return {"status": "timeout"}


def background_read_nfc(timeout):
    """バックグラウンドでNFCカード読み取りを実行"""
    global nfc_state
    
    with nfc_lock:
        nfc_state["status"] = "reading"
        nfc_state["idm"] = None
    
    result = read_card_once(timeout)
    
    with nfc_lock:
        if result["status"] == "ok":
            nfc_state["status"] = "success"
            nfc_state["idm"] = result["idm"]
            nfc_state["last_read_time"] = time.time()
        else:
            nfc_state["status"] = "timeout"


def synthesize_speech(text: str) -> str:
    """
    OpenJTalkを使用してテキストを音声ファイルに変換
    先頭に無音を追加してデバイス初期化遅延に対応
    
    Args:
        text: 合成するテキスト
    
    Returns:
        str: 生成されたWAVファイルのパス
    
    Raises:
        RuntimeError: 音声合成に失敗した場合
    """
    import wave
    import struct
    import re
    
    # HTMLタグ（<br>など）を改行に変換
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    # その他のHTMLタグを除去
    text = re.sub(r'<[^>]+>', '', text)
    
    # 一時ファイルを作成
    txt_fd, txt_path = tempfile.mkstemp(suffix='.txt', text=True)
    try:
        # ファイルディスクリプタに書き込み
        with os.fdopen(txt_fd, 'w', encoding='utf-8') as txt_file:
            txt_file.write(text)
            txt_file.flush()  # 明示的にフラッシュ
        
        temp_wav_path = tempfile.mktemp(suffix='.wav')
        final_wav_path = tempfile.mktemp(suffix='.wav')
        
        try:
            # OpenJTalkコマンドを実行
            cmd = [
                'open_jtalk',
                '-x', OPENJTALK_DICT,
                '-m', OPENJTALK_VOICE,
                '-ow', temp_wav_path,
                txt_path
            ]
            
            print(f"[DEBUG] Running OpenJTalk with text file: {txt_path}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                raise RuntimeError(f"OpenJTalk failed: {result.stderr}")
            
            if not os.path.exists(temp_wav_path):
                raise RuntimeError("WAV file was not generated")
            
            # 先頭に無音を追加（0.2秒）
            with wave.open(temp_wav_path, 'rb') as wav_in:
                params = wav_in.getparams()
                frames = wav_in.readframes(wav_in.getnframes())
                
                # 無音データを生成（0で埋める）
                silence_duration = 0.2  # 秒
                silence_frames = int(params.framerate * silence_duration)
                silence_data = struct.pack('h' * silence_frames * params.nchannels, 
                                           *([0] * silence_frames * params.nchannels))
                
                # 無音 + 元の音声データを結合
                with wave.open(final_wav_path, 'wb') as wav_out:
                    wav_out.setparams(params)
                    wav_out.writeframes(silence_data + frames)
            
            # 一時ファイルを削除
            os.remove(temp_wav_path)
            
            return final_wav_path
        
        except Exception as e:
            # エラー時は一時ファイルをクリーンアップ
            if os.path.exists(temp_wav_path):
                os.remove(temp_wav_path)
            if os.path.exists(final_wav_path):
                os.remove(final_wav_path)
            raise e
    
    finally:
        # テキストファイルを削除
        if os.path.exists(txt_path):
            os.remove(txt_path)


@app.route("/health", methods=["GET"])
def health():
    """
    ヘルスチェック用エンドポイント
    VOSK利用可否を含む
    """
    return jsonify({
        "status": "ok",
        "service": "nfc-api",
        "vosk_available": vosk_model is not None
    })


@app.route("/start-nfc", methods=["POST"])
def start_nfc():
    """
    NFC読み取りを開始する
    
    Request Body:
        {
            "timeout": 20  // タイムアウト時間（秒）、デフォルト20秒
        }
    
    Response:
        {
            "status": "started",
            "message": "NFC reading started"
        }
    """
    global nfc_state
    
    data = request.get_json() or {}
    timeout = data.get("timeout", 20)
    
    with nfc_lock:
        if nfc_state["status"] == "reading":
            return jsonify({"status": "error", "message": "Already reading"}), 400
        
        # 状態をリセット
        nfc_state["status"] = "idle"
        nfc_state["idm"] = None
    
    # バックグラウンドスレッドで読み取り開始
    thread = threading.Thread(target=background_read_nfc, args=(timeout,))
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "started", "message": "NFC reading started"})


@app.route("/check-nfc", methods=["GET"])
def check_nfc():
    """
    NFC読み取り状態を確認する（ポーリング用）
    
    Response:
        {
            "status": "idle" | "reading" | "success" | "timeout",
            "idm": "xxx"  // status が success の場合のみ
        }
    """
    with nfc_lock:
        response = {"status": nfc_state["status"]}
        
        if nfc_state["status"] == "success":
            response["idm"] = nfc_state["idm"]
            # 読み取り成功後、5秒経過したら状態をリセット
            if time.time() - nfc_state["last_read_time"] > 5:
                nfc_state["status"] = "idle"
                nfc_state["idm"] = None
        
        return jsonify(response)


@app.route("/read-nfc", methods=["GET"])
def read_nfc():
    """
    最新のNFC読み取り結果を返す（シンプルなポーリング用）
    
    Response:
        {
            "status": "no_card" | "ok",
            "idm": "xxx"  // status が ok の場合のみ
        }
    """
    with nfc_lock:
        if nfc_state["status"] == "success" and nfc_state["idm"]:
            # 最後の読み取りから5秒以内なら有効
            if time.time() - nfc_state["last_read_time"] < 5:
                return jsonify({"status": "ok", "idm": nfc_state["idm"]})
        
        return jsonify({"status": "no_card"})


@sock.route("/stt/stream")
def stt_stream(ws):
    """
    VOSK音声認識WebSocketエンドポイント
    
    受信: 音声データ (バイナリ)
    送信: {"type": "partial"|"final", "text": "認識結果"}
    """
    if not vosk_model:
        ws.send(json.dumps({
            "error": "VOSK model not loaded",
            "fallback": "web_speech_api"
        }))
        return
    
    # サンプルレート16000Hz
    recognizer = KaldiRecognizer(vosk_model, 16000)
    recognizer.SetWords(True)
    
    print("[VOSK] WebSocket connected")
    
    try:
        while True:
            data = ws.receive()
            
            if data is None:
                break
            
            # バイナリデータを処理
            if isinstance(data, bytes):
                if recognizer.AcceptWaveform(data):
                    # 確定結果
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "")
                    if text:
                        ws.send(json.dumps({
                            "type": "final",
                            "text": text
                        }))
                        print(f"[VOSK] Final: {text}")
                else:
                    # 部分結果
                    partial = json.loads(recognizer.PartialResult())
                    text = partial.get("partial", "")
                    if text:
                        ws.send(json.dumps({
                            "type": "partial",
                            "text": text
                        }))
                        print(f"[VOSK] Partial: {text}")
    
    except Exception as e:
        print(f"[VOSK] Error: {e}")
    finally:
        print("[VOSK] WebSocket disconnected")


@app.route("/speak", methods=["POST"])
def speak():
    """
    テキストを音声合成してaplayで再生する
    
    Request Body:
        {
            "text": "合成するテキスト"
        }
    
    Response:
        {
            "status": "ok",
            "message": "Speech playback started"
        }
    """
    data = request.get_json()
    
    if not data or "text" not in data:
        return jsonify({"status": "error", "message": "Missing 'text' field"}), 400
    
    text = data["text"]
    
    if not text.strip():
        return jsonify({"status": "error", "message": "Text is empty"}), 400
    
    try:
        print(f"[TTS] Synthesizing: {text}")
        wav_path = synthesize_speech(text)
        
        # aplayで音声を再生（バックグラウンド、デバイス指定）
        print(f"[TTS] Playing audio: {wav_path}")
        subprocess.Popen(['aplay', '-D', 'plughw:3,0', wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 即座にレスポンスを返す
        return jsonify({"status": "ok", "message": "Speech playback started"})
    
    except Exception as e:
        print(f"[TTS] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    print("🚀 NFC API Server starting on http://0.0.0.0:8000")
    print("📡 Endpoints:")
    print("   GET  /health          - Health check (includes vosk_available)")
    print("   WS   /stt/stream      - VOSK speech recognition (WebSocket)")
    print("   POST /start-nfc       - Start NFC reading")
    print("   GET  /check-nfc       - Check NFC reading status")
    print("   GET  /read-nfc        - Get latest NFC reading result")
    print("   POST /speak           - Text-to-speech synthesis and playback")
    
    app.run(host="0.0.0.0", port=8000, debug=False)


