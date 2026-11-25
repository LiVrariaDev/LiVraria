"""デバッグ用 API(LIVRARIA_DEBUG=true のときだけ server.py が登録する)。管理者キーで保護する。"""

from fastapi import APIRouter, Depends, HTTPException

from backend.api import llm_usage
from backend.api.auth import verify_admin_key
from backend.api.llm import LLM_ROLES, get_gemini_model, get_graph_mermaid
from backend.api.trace_store import get_trace_store

router = APIRouter(prefix="/debug", tags=["debug"], dependencies=[Depends(verify_admin_key)])


@router.get("/graph")
async def debug_graph():
	return {"mermaid": get_graph_mermaid()}


@router.get("/usage")
async def debug_usage():
	return llm_usage.snapshot(models={role: get_gemini_model(role) for role in LLM_ROLES})


@router.get("/sessions")
async def debug_sessions():
	store = get_trace_store()
	return {"sessions": store.list_sessions() if store else []}


@router.get("/sessions/{session_id}/turns")
async def debug_turns(session_id: str):
	store = get_trace_store()
	return {"turns": store.list_turns(session_id) if store else []}


@router.get("/turns/{trace_id}")
async def debug_turn(trace_id: str):
	store = get_trace_store()
	turn = store.get_turn(trace_id) if store else None
	if turn is None:
		raise HTTPException(status_code=404, detail="Trace not found")
	return turn
