#!/usr/bin/env python3
"""
Mock NFC API Server for Testing (FastAPI Version)
Mimics the behavior of raspi/nfc/nfc_api_server.py without hardware.
"""

import time
import threading
import uuid
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NFCカード読み取り状態を保持
nfc_state = {
    "status": "idle",
    "idm": None,
    "last_read_time": None
}
nfc_lock = threading.Lock()


# 起動時に固定IDを生成（再起動まで保持）
PERSISTENT_MOCK_IDM = uuid.uuid4().hex[:16].upper()
print(f"[Mock] Server initialized with Persistent IDm: {PERSISTENT_MOCK_IDM}")

def mock_background_read(timeout):
    """3秒後に成功を返すモック処理"""
    global nfc_state
    
    print("[Mock] Reading started...")
    time.sleep(3) # 3秒待機
    
    with nfc_lock:
        # 固定IDmを使用
        mock_idm = PERSISTENT_MOCK_IDM
        print(f"[Mock] Card detected! IDm: {mock_idm}")
        
        nfc_state["status"] = "success"
        nfc_state["idm"] = mock_idm
        nfc_state["last_read_time"] = time.time()


class StartNfcRequest(BaseModel):
    timeout: int = 20


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock-nfc-api"}


@app.post("/start-nfc")
def start_nfc(request: StartNfcRequest):
    global nfc_state
    
    with nfc_lock:
        if nfc_state["status"] == "reading":
            raise HTTPException(status_code=400, detail="Already reading")
        
        nfc_state["status"] = "idle"
        nfc_state["idm"] = None
    
    # 状態をreadingにしてからバックグラウンド処理開始
    with nfc_lock:
        nfc_state["status"] = "reading"

    thread = threading.Thread(target=mock_background_read, args=(request.timeout,))
    thread.daemon = True
    thread.start()
    
    return {"status": "started", "message": "Mock NFC reading started"}


@app.get("/check-nfc")
def check_nfc():
    with nfc_lock:
        response = {"status": nfc_state["status"]}
        
        if nfc_state["status"] == "success":
            response["idm"] = nfc_state["idm"]
            # 5秒後にリセット
            if time.time() - nfc_state["last_read_time"] > 5:
                nfc_state["status"] = "idle"
                nfc_state["idm"] = None
        
        return response


if __name__ == "__main__":
    port = 8080
    print(f"🚀 Mock NFC API Server (FastAPI) starting on http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
