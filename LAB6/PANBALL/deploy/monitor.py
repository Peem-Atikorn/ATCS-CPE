"""Check the running Compose services, including worker and beat containers."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from preflight import find_docker

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "postgres", "redis", "api", "worker", "beat", "retrieval", "engines",
    "generation", "football-data", "router", "web",
}


def snapshot() -> bool:
    docker = find_docker()
    if docker is None:
        print("FAIL Docker CLI missing", file=sys.stderr)
        return False
    env = ROOT / ".env"
    if not env.is_file():
        print("FAIL .env missing", file=sys.stderr)
        return False
    try:
        result = subprocess.run(
            [docker, "compose", "--env-file", str(env), "-f", str(ROOT / "docker-compose.yml"),
             "ps", "--all", "--format", "json"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=20,
        )
    except subprocess.TimeoutExpired:
        print("FAIL Docker Compose status timed out", file=sys.stderr)
        return False
    except OSError as exc:
        print(f"FAIL Docker Compose unavailable: {exc}", file=sys.stderr)
        return False
    if result.returncode:
        print(f"FAIL Docker Compose status: {result.stderr.strip()[:300]}", file=sys.stderr)
        return False
    try:
        raw = result.stdout.strip()
        items = json.loads(raw) if raw.startswith("[") else [json.loads(line) for line in raw.splitlines()]
        if isinstance(items, dict):
            items = [items]
    except json.JSONDecodeError as exc:
        print(f"FAIL Docker Compose returned invalid JSON: {exc}", file=sys.stderr)
        return False
    services = {item["Service"]: item for item in items}
    ok = True
    for name in sorted(EXPECTED):
        item = services.get(name)
        state = item.get("State") if item else "missing"
        health = item.get("Health", "") if item else ""
        passed = state == "running" and health in ("", "healthy")
        print(f"{'OK' if passed else 'FAIL'} {name}: {state}" + (f" / {health}" if health else ""))
        ok &= passed
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", type=int, metavar="SECONDS", help="repeat until interrupted")
    args = parser.parse_args()
    if args.watch is not None and args.watch < 1:
        parser.error("--watch must be at least 1 second")
    try:
        while True:
            ok = snapshot()
            if args.watch is None:
                return 0 if ok else 1
            time.sleep(args.watch)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
