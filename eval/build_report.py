"""Combine available evaluation results into an auditable HTML report."""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval/results"
OUTPUT = ROOT / "eval/report.html"


def esc(value: object) -> str:
    return html.escape(str(value))


def pct(value: object) -> str:
    return f"{float(value) * 100:.1f}%"


def other_result(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return f"<section><h2>{esc(path.stem)}</h2><p>Source: <code>eval/results/{esc(path.name)}</code>; no object summary available.</p></section>"
    rows = []
    for key, value in data.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            rows.append((key, value))
        elif isinstance(value, dict):
            rows.extend((f"{key}.{subkey}", subvalue) for subkey, subvalue in value.items()
                        if isinstance(subvalue, (int, float)) and not isinstance(subvalue, bool))
    table = "" if not rows else (
        "<table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>"
        + "".join(f"<tr><td>{esc(key)}</td><td>{esc(value)}</td></tr>" for key, value in rows)
        + "</tbody></table>"
    )
    return (f"<section><h2>{esc(path.stem)}</h2>"
            f"<p>Source: <code>eval/results/{esc(path.name)}</code>; generated {esc(data.get('generated_at', 'not specified'))}. "
            "Values are displayed as supplied by the producing service.</p>"
            + (table or "<p>No scalar numeric metrics found.</p>") + "</section>")


def main() -> int:
    retrieval_path = RESULTS / "retrieval.json"
    live_path = RESULTS / "live_chat.json"
    sections = []
    if retrieval_path.exists():
        data = json.loads(retrieval_path.read_text(encoding="utf-8"))
        rows = []
        for result in data.get("results", []):
            if result.get("mode") != "hybrid":
                continue
            rows.append("<tr>" + "".join(f"<td>{esc(v)}</td>" for v in (
                result.get("set"), result.get("variant"), result.get("n"),
                pct(result.get("hit@1", 0)), pct(result.get("hit@5", 0)),
                f"{float(result.get('p95_ms', 0)):.1f}",
            )) + "</tr>")
        fixture = "synthetic" if data.get("live_fixture_synthetic") else "not marked synthetic"
        sections.append(
            "<section><h2>Retrieval 05</h2>"
            f"<p>Source: <code>eval/results/retrieval.json</code>; generated {esc(data.get('generated_at'))}. "
            f"Match fixture: {fixture}. Timings are in-process and exclude HTTP/model loading.</p>"
            "<table><thead><tr><th>Set</th><th>Variant</th><th>n</th><th>Hit@1</th><th>Hit@5</th><th>p95 ms</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></section>"
        )
    if live_path.exists():
        data = json.loads(live_path.read_text(encoding="utf-8"))
        results = data.get("results", [])
        count = len(results)
        route_ok = sum(bool(row.get("route_ok")) for row in results)
        answer_ok = sum(bool(row.get("answer_contains_expected")) for row in results)
        failed = [row for row in results if not row.get("route_ok") or not row.get("answer_contains_expected")]
        failures = "" if not failed else (
            "<p>Cases below need manual review; exact substring misses translations and formatting variants.</p>"
            "<table><thead><tr><th>Case</th><th>Route</th><th>Sources</th><th>Error</th></tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{esc(value)}</td>" for value in (
                row.get("id"), row.get("route", ""), row.get("source_count", 0), row.get("error", "")
            )) + "</tr>" for row in failed)
            + "</tbody></table>"
        )
        sections.append(
            "<section><h2>Live chat through API 02</h2>"
            f"<p>Source: <code>eval/results/live_chat.json</code>; generated {esc(data.get('generated_at'))}; "
            f"API: {esc(data.get('api_url'))}. Trivia answer matching is exact substring, not semantic grading.</p>"
            f"<p>Cases: {count}; football_rag route: {route_ok}/{count}; expected answer substring: {answer_ok}/{count}.</p>"
            + failures
            + "</section>"
        )
    else:
        sections.append("<section><h2>Live integration</h2><p>No live chat result is present. "
                        "Run <code>make eval-live</code> against the Compose stack, then regenerate this report.</p></section>")
    for path in sorted(RESULTS.glob("*.json")):
        if path.name not in {"retrieval.json", "live_chat.json"}:
            sections.append(other_result(path))
    if not sections:
        raise ValueError("No evaluation results found")
    document = (
        "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
        "<title>Football Assistant evaluation</title><style>body{font:16px/1.5 system-ui;max-width:960px;"
        "margin:40px auto;padding:0 20px;color:#18202a}section{margin:2rem 0;padding:1.25rem;"
        "border:1px solid #d5dce3;border-radius:8px}table{border-collapse:collapse;width:100%}"
        "th,td{padding:.5rem;border-bottom:1px solid #d5dce3;text-align:left}thead{background:#eff4f8}"
        "code{background:#f1f4f6;padding:.1rem .3rem}p{max-width:75ch}</style>"
        "<main><h1>Football Assistant evaluation</h1>"
        "<p>Metrics retain their original source and test conditions.</p>"
        + "".join(sections) + "</main></html>\n"
    )
    OUTPUT.write_text(document, encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
