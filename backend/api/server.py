# Geminiを用いたチャットができるAPIサーバー

# Standard Library
from pydantic import BaseModel
import uuid

# Third Party
from fastapi import FastAPI, HTTPException
import uvicorn

# user-defined
from gemini import gemini_chat

app = FastAPI()

# セッション保存用
sessions = {}

# Request/Response Models
class ChatRequest(BaseModel):
    message: str
    session_id: str = None

class ChatResponse(BaseModel):
    response: str
    session_id: str

# 共通のチャット処理
def chat_prompt(request: ChatRequest, prompt_file: str):
    # セッションの作成
    session_id = request.session_id
    if not session_id: # 空文字列の場合
        session_id = str(uuid.uuid4())
        sessions[session_id] = []
    elif session_id not in sessions: # 存在しないセッションIDの場合
        raise HTTPException(status_code=404, detail="Session not found")

    # セッションの取得
    history = sessions[session_id]

    # 会話
    response, new_history = gemini_chat(prompt_file, request.message, history)

    # セッションの更新
    sessions[session_id] = new_history

    return ChatResponse(response=response, session_id=session_id)

# API Endpoints / - 起動確認用
@app.get("/")
async def read_root(name: str = "World"):
    return f"Hello, {name}! The API server is running."

# API EndPoints /sessions - セッション履歴取得
# query: session_id (str, required)
@app.get("/sessions")
async def get_sessions(session_id: str = None):
    if session_id is None:
        raise HTTPException(status_code=404, detail="Session ID is required")
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"session_id": session_id, "history": sessions[session_id]}

# API EndPoints /chat/default - デフォルトプロンプト
# query: message (str, required), session_id (str, optional)
@app.post("/chat/default")
async def chat_default(request: ChatRequest):
    return chat_prompt(request, "api/prompts/default.md")

# API EndPoints /chat/librarian - 図書館司書プロンプト
# query: message (str, required), session_id (str, optional)
@app.post("/chat/librarian")
async def chat_librarian(request: ChatRequest):
    return chat_prompt(request, "api/prompts/librarian.md")

# API EndPoints /delete_session - セッション削除
# query: session_id (str, required)
@app.delete("/delete_session")
async def delete_session(session_id: str = None):
    if session_id is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    del sessions[session_id]
    return {"detail": "Session deleted successfully"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

