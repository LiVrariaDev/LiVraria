"""会話シナリオ（backend/test/scenarios/）の形式と、比較スクリプトの検証。実際の Gemini は呼ばない。"""

import importlib.util
import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import backend.api.llm as llm
from backend.api.trace_store import current_turn

SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"


def _load_runner():
	spec = importlib.util.spec_from_file_location("run_scenarios", SCENARIO_DIR / "run_scenarios.py")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def test_scenario_files_are_valid():
	files = sorted(SCENARIO_DIR.glob("*.json"))
	assert 10 <= len(files) <= 20
	ids = set()
	for path in files:
		data = json.loads(path.read_text(encoding="utf-8"))
		assert data["id"] == path.stem
		assert data["id"] not in ids
		ids.add(data["id"])
		assert data["title"]
		assert data["turns"] and all(isinstance(t, str) and t.strip() for t in data["turns"])
		assert data["checks"]
		assert isinstance(data.get("user_context", ""), str)


def test_runner_records_turns_and_writes_summary(monkeypatch, tmp_path):
	runner = _load_runner()
	seen = []

	def fake_llm_chat(prompt_file, message, history, ai_insight="", conversation_state=None, **kwargs):
		seen.append((llm.get_graph_version(), message, ai_insight))
		turn = current_turn.get()
		turn.route = "interview" if turn.graph == "v2" else None
		books = [{"title": "本1", "authors": ["著者"], "recommendation_reason": "理由", "recommendation_slot": "ど真ん中"}]
		return f"返事:{message}", history + [HumanMessage(message), AIMessage("x")], books, "happy"

	monkeypatch.setattr(llm, "llm_chat", fake_llm_chat)
	monkeypatch.delenv("LIVRARIA_GRAPH", raising=False)
	scenario = {"id": "s1", "title": "テスト", "user_context": "ctx", "turns": ["a", "b|c"], "checks": ["観点"]}

	try:
		results = {g: [runner.run_scenario(scenario, g)] for g in ("v1", "v2")}
	finally:
		monkeypatch.delenv("LIVRARIA_GRAPH", raising=False)

	assert [s[0] for s in seen] == ["v1", "v1", "v2", "v2"]
	assert seen[0][2] == "ctx"
	turn = results["v2"][0]["turns"][1]
	assert turn["response"] == "返事:b|c" and turn["route"] == "interview"
	assert turn["books"][0] == {"title": "本1", "author": "著者", "isbn": None, "slot": "ど真ん中", "reason": "理由"}

	summary = runner.write_summary(results, tmp_path).read_text(encoding="utf-8")
	assert "## s1: テスト" in summary and "- 観点" in summary
	assert "返事:b｜c `interview`" in summary  # 表を壊す | は置き換える
	assert "[ど真ん中] 『本1』: 理由" in summary


def test_runner_only_filter():
	runner = _load_runner()
	assert [s["id"] for s in runner.load_scenarios(["04_ask_about_pick"])] == ["04_ask_about_pick"]
	with pytest.raises(SystemExit):
		runner.main(["--graph", "v9"])
