"""
Backend API module initialization
LLMバックエンドの選択を一元管理
"""
import os
import logging

# ロガー設定
logger = logging.getLogger("uvicorn.error")

# LLMバックエンドの選択
LLM_BACKEND = os.getenv("LLM_BACKEND", "gemini")

if LLM_BACKEND == "ollama":
	from .llm import llm_chat as chat_function
	from .llm import llm_summary as summary_function
	logger.info(f"🔧 [LLM Backend Init] Ollama selected (model: {os.getenv('OLLAMA_MODEL', 'llama3.2')})")
else:
	from .gemini import gemini_chat as chat_function
	from .gemini import gemini_summary as summary_function
	logger.info("🔧 [LLM Backend Init] Gemini selected")

__all__ = ['chat_function', 'summary_function', 'LLM_BACKEND']
