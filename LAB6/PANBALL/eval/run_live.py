"""Run a small, repeatable end-to-end chat evaluation against API 02.

This checks trivia answer text and route behavior. It does not grade the factual
quality of free-form answers or synthetic match fixtures.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "deploy"))
os.environ.setdefault("API_URL", "http://127.0.0.1:8000")
from smoke import expect, login  # noqa: E402


def load_cases(limit: int) -> list[dict]:
    cases = []
    for line in (ROOT / "eval/golden_trivia.jsonl").read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        question = case.get("variants", {}).get("verbatim")
        if question and case.get("answer"):
            cases.append({"id": case["id"], "question": f"football trivia: {question}",
                          "expected_answer": case["answer"]})
        if len(cases) >= limit:
            break
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20, help="number of trivia cases (default: 20)")
    parser.add_argument("--output", type=Path, default=ROOT / "eval/results/live_chat.json")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    password = os.getenv("SEED_DEMO_PASSWORD")
    if not password:
        print("FAIL SEED_DEMO_PASSWORD is required", file=sys.stderr)
        return 2
    try:
        demo = login("demo1", password)
    except (OSError, ValueError) as exc:
        print(f"FAIL login: {exc}", file=sys.stderr)
        return 1
    cases = load_cases(args.limit)
    results = []
    for case in cases:
        start = time.perf_counter()
        try:
            data = expect(demo, "/api/chat", 200, method="POST", body={"message": case["question"]})
            answer = data.get("answer", "")
            row = {
                "id": case["id"], "route": data.get("route"),
                "route_ok": data.get("route") == "football_rag",
                "answer_contains_expected": case["expected_answer"].casefold() in answer.casefold(),
                "source_count": len(data.get("sources") or []),
                "request_id": data.get("request_id"),
                "latency_ms": round((time.perf_counter() - start) * 1000),
            }
        except (OSError, ValueError, KeyError, TypeError) as exc:
            row = {"id": case["id"], "route_ok": False, "answer_contains_expected": False,
                   "source_count": 0, "error": str(exc),
                   "latency_ms": round((time.perf_counter() - start) * 1000)}
        results.append(row)
        print(f"{'OK' if row['route_ok'] and row['answer_contains_expected'] else 'FAIL'} {case['id']}")
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_url": os.environ["API_URL"],
        "evaluation": "trivia route and exact expected answer substring; no semantic grading",
        "n": len(results), "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {args.output}")
    return 0 if results and all(r["route_ok"] and r["answer_contains_expected"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
