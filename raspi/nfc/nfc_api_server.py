#!/usr/bin/env python3
"""
NFC API Server for Raspberry Pi
Provides HTTP endpoints for NFC card reading
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import time
import threading
import os
import shutil
import subprocess
import tempfile
from smartcard.System import readers
from smartcard.util import toHexString

app = Flask(__name__)
CORS(app)  # すべてのオリジンからのアクセスを許可

# NFCカード読み取り状態を保持
nfc_state = {
    "status": "idle",  # idle, reading, success, timeout
    "idm": None,
    "last_read_time": None
}
nfc_lock = threading.Lock()

# 音声合成は端末上で実行し、ブラウザの SpeechSynthesis に依存しない。
OPENJTALK_DICT = os.getenv("OPENJTALK_DICT", "/var/lib/mecab/dic/open-jtalk/naist-jdic")
OPENJTALK_VOICE = os.getenv(
    "OPENJTALK_VOICE", "/usr/share/hts-voice/Voice/mei/mei_normal.htsvoice"
)
ALSA_DEVICE = os.getenv("ALSA_DEVICE", "plughw:3,0")


def is_tts_available():
    """OpenJTalk と再生に必要なファイル・コマンドが利用可能か返す。"""
    return (
        shutil.which("open_jtalk") is not None
        and shutil.which("aplay") is not None
        and os.path.isdir(OPENJTALK_DICT)
        and os.path.isfile(OPENJTALK_VOICE)
    )


def remove_file_after_playback(process, path):
    """aplay の終了後に生成した一時 WAV ファイルを削除する。"""
    try:
        process.wait()
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def synthesize_and_play(text):
    """OpenJTalk で合成し、指定した ALSA デバイスで非同期再生する。"""
    text_file = None
    wav_fd = None
    wav_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as text_file:
            text_file.write(text)

        wav_fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(wav_fd)
        wav_fd = None

        result = subprocess.run(
            [
                "open_jtalk",
                "-x", OPENJTALK_DICT,
                "-m", OPENJTALK_VOICE,
                "-ow", wav_path,
                text_file.name,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "OpenJTalk failed")

        process = subprocess.Popen(
            ["aplay", "-D", ALSA_DEVICE, wav_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cleanup_thread = threading.Thread(
            target=remove_file_after_playback, args=(process, wav_path), daemon=True
        )
        cleanup_thread.start()
        wav_path = None
    finally:
        if text_file is not None:
            try:
                os.remove(text_file.name)
            except FileNotFoundError:
                pass
        if wav_fd is not None:
            os.close(wav_fd)
        if wav_path is not None:
            try:
                os.remove(wav_path)
            except FileNotFoundError:
                pass


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


@app.route("/health", methods=["GET"])
def health():
    """ヘルスチェック用エンドポイント"""
    return jsonify({
        "status": "ok",
        "service": "nfc-api",
        "tts_available": is_tts_available(),
    })


@app.route("/speak", methods=["POST"])
def speak():
    """テキストを OpenJTalk で合成し、Raspberry Pi のスピーカーで再生する。"""
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")

    if not isinstance(text, str) or not text.strip():
        return jsonify({"status": "error", "message": "Text is empty"}), 400
    if not is_tts_available():
        return jsonify({"status": "error", "message": "OpenJTalk is unavailable"}), 503

    try:
        synthesize_and_play(text)
        return jsonify({"status": "ok", "message": "Speech playback started"})
    except (OSError, subprocess.SubprocessError, RuntimeError) as error:
        print(f"[TTS] Error: {error}")
        return jsonify({"status": "error", "message": str(error)}), 500


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


if __name__ == "__main__":
    print("🚀 NFC API Server starting on http://localhost:8000")
    print("📡 Endpoints:")
    print("   GET  /health       - Health check")
    print("   POST /speak        - Text-to-speech synthesis and playback")
    print("   POST /start-nfc    - Start NFC reading")
    print("   GET  /check-nfc    - Check NFC reading status")
    print("   GET  /read-nfc     - Get latest NFC reading result")
    
    app.run(host="0.0.0.0", port=8000, debug=False)
