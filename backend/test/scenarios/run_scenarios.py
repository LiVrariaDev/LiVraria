"""会話シナリオを v1 / v2 の会話グラフで流し、結果を保存する（実際の Gemini と楽天を呼ぶ。実行は人が行う）。

使い方（リポジトリのルートで。.env に GEMINI_API_KEY と RAKUTEN_APP_ID が必要）:

    backend/.venv/bin/python backend/test/scenarios/run_scenarios.py
    backend/.venv/bin/python backend/test/scenarios/run_scenarios.py --graph v2 --only 01_tired_at_work 04_ask_about_pick
    backend/.venv/bin/python backend/test/scenarios/run_scenarios.py --sleep 5

結果は backend/test/scenarios/results/<日時>/ に保存する（git には入れない）:
- <版>.json: シナリオ・ターンごとの応答、推薦書籍、表情、所要時間、役割ごとの LLM 呼び出し回数、通ったノード
- summary.md: v1 と v2 を並べた比較表と、人が見る観点

会話はサーバーやデータファイルを通さず llm_chat を直接呼ぶ（backend/api/data には書き込まない）。
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

SCENARIO_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCENARIO_DIR.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

GRAPHS = ("v1", "v2")


def load_scenarios(only=None) -> list[dict]:
	scenarios = []
	for path in sorted(SCENARIO_DIR.glob("*.json")):
		data = json.loads(path.read_text(encoding="utf-8"))
		if only and data["id"] not in only:
			continue
		scenarios.append(data)
	return scenarios


def _book_summary(book: dict) -> dict:
	authors = book.get("authors") or []
	return {
		"title": book.get("title"),
		"author": authors[0] if authors else None,
		"isbn": book.get("isbn"),
		"slot": book.get("recommendation_slot"),
		"reason": book.get("recommendation_reason"),
	}


def run_scenario(scenario: dict, graph: str, sleep: float = 0.0) -> dict:
	"""1つのシナリオを指定の版で最後まで流す。"""
	from backend import PROMPT_DEFAULT
	from backend.api import llm, llm_usage
	from backend.api.trace_store import TurnTrace, current_turn

	os.environ["LIVRARIA_GRAPH"] = graph
	history = []
	state = {"profile": {}, "last_picks": []}
	turns = []
	for index, message in enumerate(scenario["turns"]):
		if index and sleep:
			time.sleep(sleep)
		llm_usage.reset()
		trace = TurnTrace(trace_id=f"{scenario['id']}-{graph}-{index}", session_id=None, user_id=None,
		                  started_at=datetime.now().isoformat(), ended_at=None, user_message=message, graph=graph)
		token = current_turn.set(trace)
		started = time.monotonic()
		try:
			text, history, books, expression = llm.llm_chat(
				str(PROMPT_DEFAULT), message, history,
				ai_insight=scenario.get("user_context") or "", conversation_state=state,
			)
		finally:
			current_turn.reset(token)
		elapsed = round(time.monotonic() - started, 2)
		usage = llm_usage.snapshot().get("roles", {})
		turns.append({
			"user": message,
			"response": text,
			"expression": expression,
			"books": [_book_summary(b) for b in books],
			"elapsed_sec": elapsed,
			"llm_calls": {role: u.get("calls", 0) for role, u in usage.items()},
			"llm_errors": {role: u.get("errors", 0) for role, u in usage.items() if u.get("errors")},
			"nodes": [step.node for step in trace.steps],
			"intent": trace.intent,
			"route": trace.route,
			"profile": trace.profile,
			"crd_hints": trace.crd_hints,
			"error": trace.error,
		})
	return {"id": scenario["id"], "title": scenario["title"], "graph": graph, "turns": turns, "checks": scenario.get("checks", [])}


def _cell(text) -> str:
	return str(text or "").replace("|", "｜").replace("\n", " ")


def _books_cell(books: list[dict]) -> str:
	if not books:
		return "-"
	parts = []
	for b in books:
		slot = f"[{b['slot']}] " if b.get("slot") else ""
		parts.append(f"{slot}『{b.get('title')}』: {b.get('reason') or ''}")
	return _cell("<br>".join(parts))


def _calls_cell(turn: dict) -> str:
	calls = turn.get("llm_calls") or {}
	return f"{sum(calls.values())} ({', '.join(f'{k}:{v}' for k, v in calls.items())})" if calls else "0"


def write_summary(results: dict, out_dir: Path) -> Path:
	"""v1 と v2 を並べた Markdown を書く。"""
	lines = ["# 会話シナリオの比較", "", f"実行: {out_dir.name}", ""]
	graphs = [g for g in GRAPHS if g in results]
	by_graph = {g: {r["id"]: r for r in results[g]} for g in graphs}
	ids = list(dict.fromkeys(r["id"] for g in graphs for r in results[g]))
	for sid in ids:
		first = next(by_graph[g][sid] for g in graphs if sid in by_graph[g])
		lines += [f"## {sid}: {first['title']}", ""]
		if first.get("checks"):
			lines += ["見る観点:", *[f"- {c}" for c in first["checks"]], ""]
		header = "| # | 利用者 | " + " | ".join(f"{g} 応答 | {g} 本 | {g} 秒 / LLM回数" for g in graphs) + " |"
		lines += [header, "|" + "---|" * (2 + 3 * len(graphs))]
		turn_count = max(len(by_graph[g][sid]["turns"]) for g in graphs if sid in by_graph[g])
		for i in range(turn_count):
			row = [str(i + 1)]
			user = next((by_graph[g][sid]["turns"][i]["user"] for g in graphs if sid in by_graph[g]), "")
			row.append(_cell(user))
			for g in graphs:
				turn = by_graph[g].get(sid, {}).get("turns", [None] * turn_count)[i] if sid in by_graph[g] else None
				if not turn:
					row += ["-", "-", "-"]
					continue
				route = f" `{turn['route']}`" if turn.get("route") else ""
				row += [_cell(turn["response"]) + route, _books_cell(turn["books"]), f"{turn['elapsed_sec']} / {_calls_cell(turn)}"]
			lines.append("| " + " | ".join(row) + " |")
		lines.append("")
	path = out_dir / "summary.md"
	path.write_text("\n".join(lines), encoding="utf-8")
	return path


def main(argv=None) -> int:
	parser = argparse.ArgumentParser(description="会話シナリオを v1 / v2 で流して結果を保存する（実際の Gemini を呼ぶ）")
	parser.add_argument("--graph", nargs="+", choices=GRAPHS, default=list(GRAPHS), help="流す版（既定: v1 v2）")
	parser.add_argument("--only", nargs="+", help="流すシナリオの id（既定: すべて）")
	parser.add_argument("--sleep", type=float, default=2.0, help="ターンの間の待ち秒数（429 を避けるため）")
	parser.add_argument("--out", type=Path, default=SCENARIO_DIR / "results", help="結果の保存先")
	args = parser.parse_args(argv)

	scenarios = load_scenarios(args.only)
	if not scenarios:
		print("シナリオが見つかりません", file=sys.stderr)
		return 1
	out_dir = args.out / datetime.now().strftime("%Y%m%d-%H%M%S")
	out_dir.mkdir(parents=True, exist_ok=True)

	results = {}
	for graph in args.graph:
		results[graph] = []
		for scenario in scenarios:
			print(f"[{graph}] {scenario['id']} ...", flush=True)
			results[graph].append(run_scenario(scenario, graph, args.sleep))
			time.sleep(args.sleep)
		(out_dir / f"{graph}.json").write_text(json.dumps(results[graph], ensure_ascii=False, indent=2), encoding="utf-8")

	summary = write_summary(results, out_dir)
	print(f"保存しました: {out_dir}\n比較表: {summary}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
