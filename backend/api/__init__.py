"""
Backend API module initialization
LangChainベースのLLM統合
"""
import os
import logging

# ロガー設定
logger = logging.getLogger("uvicorn.error")

# LangChainベースのLLM関数をインポート
# LangChainベースのLLM関数をインポート
# server.pyなどで直接llm.pyからインポートするため、ここではエイリアス定義のみ削除
from .llm import llm_summary as summary_function

# LLMバックエンドの選択（GeminiまたはOllama）
LLM_BACKEND = os.getenv("LLM_BACKEND", "gemini")

if LLM_BACKEND == "ollama":
	logger.info(f"🔧 [LLM Backend] LangChain + Ollama (model: {os.getenv('OLLAMA_MODEL', 'llama3.2')})")
else:
	logger.info("🔧 [LLM Backend] LangChain + Gemini")

__all__ = ['summary_function', 'LLM_BACKEND']
