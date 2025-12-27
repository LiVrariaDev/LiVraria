#!/usr/bin/env python3
"""
NFC API Server for Raspberry Pi
Provides HTTP endpoints for NFC card reading
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import time
import threading
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
    
    while time.time() - start_time < timeout:
        try:
            reader_list = readers()
            if not reader_list:
                time.sleep(0.5)
                continue
            
            reader = reader_list[0]
            connection = reader.createConnection()
            connection.connect()
            
            response, sw1, sw2 = connection.transmit(GET_IDM_APDU)
            
            if sw1 == 0x90 and sw2 == 0x00:
                idm_hex = toHexString(response).replace(" ", "")
                connection.disconnect()
                return {"status": "ok", "idm": idm_hex}
            
            connection.disconnect()
        except Exception:
            # カードが置かれていない場合は例外が発生するため無視
            pass
        
        time.sleep(0.5)
    
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
    return jsonify({"status": "ok", "service": "nfc-api"})


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
    print("   POST /start-nfc    - Start NFC reading")
    print("   GET  /check-nfc    - Check NFC reading status")
    print("   GET  /read-nfc     - Get latest NFC reading result")
    
    app.run(host="0.0.0.0", port=8000, debug=False)
