
import threading
import time
import queue
from flask import Flask, jsonify, request
from flask_cors import CORS
import pyttsx3
import speech_recognition as sr

app = Flask(__name__)
CORS(app)

# TTSキューと制御用
tts_queue = queue.Queue()

import pythoncom

def tts_loop():
    """
    TTSエンジン（pyttsx3）は単一のスレッドで動かすのが最も安全。
    キューからテキストを取り出して読み上げる専用スレッド。
    Windowsの場合、スレッド内でCOM初期化が必要。
    """
    print("[TTS Worker] Starting TTS loop...")
    pythoncom.CoInitialize()
    while True:
        try:
            # (text, event) を取得
            item = tts_queue.get()
            if item is None:
                break
            
            text, done_event = item
            print(f"[PC TTS] Speaking: {text}")
            
            try:
                # 毎回初期化することで安定性を高める（SAPI5の再利用問題を回避）
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
                # 念のため明示的に停止
                engine.stop()
                del engine
            except Exception as e:
                print(f"[PC TTS] Error during speech: {e}")
            finally:
                # 完了通知
                if done_event:
                    done_event.set()
                tts_queue.task_done()
                
        except Exception as e:
            print(f"[TTS Worker] Critical Error: {e}")

# バックグラウンドでTTSスレッドを開始
threading.Thread(target=tts_loop, daemon=True).start()

# --- 音声合成 (TTS) ---
@app.route("/speak", methods=["POST"])
def speak():
    data = request.get_json()
    text = data.get("text", "")
    if not text:
        return jsonify({"status": "error"}), 400

    # 完了待機用のイベントを作成
    done_event = threading.Event()
    
    # キューに追加
    tts_queue.put((text, done_event))
    
    # 読み上げが終わるまで待機
    # タイムアウトを設定する場合は wait(timeout=...) とするが、基本無限待ち
    done_event.wait()
    
    return jsonify({"status": "ok"})

# --- 音声認識 (STT) ---
@app.route("/listen", methods=["POST"])
def listen():
    recognizer = sr.Recognizer()
    try:
        print("[PC STT] Listening...")
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source)
            # PCマイクから録音
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
        
        print("[PC STT] Recognizing...")
        text = recognizer.recognize_google(audio, language="ja-JP")
        print(f"[PC STT] Result: {text}")
        
        return jsonify({"status": "ok", "text": text})

    except Exception as e:
        print(f"[PC STT] Error: {e}")
        return jsonify({"status": "error"}), 500

# --- NFC (PCでテストする場合、ダミーを返すかnfcpyを入れる) ---
@app.route("/read-nfc", methods=["GET"])
def read_nfc():
    # PCでNFCリーダーがない場合のためのダミー
    return jsonify({"status": "no_card"})

if __name__ == "__main__":
    print("💻 PC TTS/STT Server running on http://localhost:5001")
    app.run(host="0.0.0.0", port=5001)