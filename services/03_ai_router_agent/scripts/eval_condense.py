"""Run the follow-up cases against the real condense LLM (manual; needs GROQ_* or GEMINI_* env).

    cd services/03_ai_router_agent && python scripts/eval_condense.py

Reports how often the rewrite was rejected, how often the raw LLM rewrite invented a
team or number (before and after validation), and routing accuracy with the live
rewrite versus the flag switched off.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from app.clients import ServiceClients  # noqa: E402
from app.condense import invented_entities, needs_condense, validate  # noqa: E402
from app.router import Router, UpstreamError  # noqa: E402
from app.teams import TeamDirectory  # noqa: E402
from test_router import FakeClients  # noqa: E402


CONTEXT = {"season": "2026", "current_matchweek": 5, "now": "2026-09-26T10:00:00+07:00"}
SOURCE = {"ref": 1, "doc_id": "eval-1", "title": "Sample", "category": "match_report",
          "origin": "football-data.org", "season": "2026", "matchweek": 5, "team_ids": [],
          "fetched_at": None, "url": None}


async def route(teams, case, standalone, enabled):
    os.environ["ROUTER_CONDENSE_ENABLED"] = "true" if enabled else "false"
    clients = FakeClients()
    clients.chunks = [{"text": "sample", "source": SOURCE}]
    clients.standalone = standalone
    result = await Router(clients, teams).route({
        "request_id": case["id"], "session_id": "eval",
        "user": {"id": "eval", "favorite_team_id": None, "language": "th"},
        "query": case["query"], "history": case["history"], "context": CONTEXT})
    return result["route"], result["trace"]["intent"]


async def main():
    teams = TeamDirectory.from_file(ROOT / "data" / "team_aliases.json")
    cases = [json.loads(line) for line in
             (ROOT / "tests" / "followup_cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    live = ServiceClients(None)
    rows = []
    for case in cases:
        row = {"id": case["id"], "query": case["query"]}
        if not needs_condense(case["query"], case["history"], teams, CONTEXT["season"]):
            row["status"] = "skipped"
            rows.append(row)
            continue
        try:
            raw = await asyncio.wait_for(live.condense(case["query"], case["history"], case["id"]), 10)
            rewritten = str(raw.get("standalone_query") or "")
        except (UpstreamError, ValueError, asyncio.TimeoutError) as exc:
            row.update(status="unavailable", error=type(exc).__name__)
            rows.append(row)
            continue
        checked = validate(case["query"], rewritten, case["history"], teams)
        row.update(rewritten=rewritten, status="accepted" if checked else "rejected",
                   invented_raw=invented_entities(case["query"], rewritten, case["history"], teams),
                   invented_after=(invented_entities(case["query"], checked, case["history"], teams)
                                   if checked else []))
        if case["condense"] == "applied":
            expected = (case["route"], case["intent"])
            row["expected"] = list(expected)
            row["with_condense"] = list(await route(teams, case, rewritten, True))
            row["flag_off"] = list(await route(teams, case, None, False))
        rows.append(row)

    called = [r for r in rows if r["status"] in ("accepted", "rejected")]
    scored = [r for r in rows if "expected" in r]
    report = {
        "cases": len(rows),
        "llm_called": len(called),
        "rejected_rate": round(sum(r["status"] == "rejected" for r in called) / len(called), 3) if called else None,
        "invented_rate_raw": round(sum(bool(r["invented_raw"]) for r in called) / len(called), 3) if called else None,
        "invented_rate_after_validate": round(sum(bool(r["invented_after"]) for r in called) / len(called), 3)
        if called else None,
        "routing_accuracy_with_condense": round(sum(r["with_condense"] == r["expected"] for r in scored)
                                                / len(scored), 3) if scored else None,
        "routing_accuracy_flag_off": round(sum(r["flag_off"] == r["expected"] for r in scored)
                                           / len(scored), 3) if scored else None,
        "rows": rows,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["invented_rate_after_validate"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
