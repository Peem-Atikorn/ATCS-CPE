"""Report whether the checked-out repository can start the central Compose stack."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SERVICES = {
    "api": "02_api_backend",
    "router": "03_ai_router_agent",
    "engines": "04_ai_engines",
    "retrieval": "05_retrieval_knowledge",
    "generation": "06_llm_generation",
    "football-data": "07_football_data",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files-only", action="store_true", help="skip local Docker and .env checks")
    args = parser.parse_args()
    failures: list[str] = []

    def required(path: Path, label: str) -> None:
        if not path.is_file():
            failures.append(f"{label}: missing {path.relative_to(ROOT)}")

    required(ROOT / "docker-compose.yml", "Compose")
    required(ROOT / "deploy/Dockerfile.python", "Python image")
    required(ROOT / "services/01_web_app/Dockerfile", "web image")
    required(ROOT / "services/01_web_app/package.json", "web dependencies")
    required(ROOT / "services/01_web_app/pnpm-lock.yaml", "web lockfile")
    required(ROOT / "services/01_web_app/app/health/route.ts", "web health endpoint")
    for name, folder in PYTHON_SERVICES.items():
        service = ROOT / "services" / folder
        required(service / "requirements.txt", f"{name} dependencies")
        required(service / "app/main.py", f"{name} application")
    required(ROOT / "services/04_ai_engines/app/models/intent_clf.joblib", "engines model")
    required(ROOT / "services/02_api_backend/scripts/entrypoint.sh", "api entrypoint")
    required(ROOT / "services/05_retrieval_knowledge/scripts/entrypoint.sh", "retrieval entrypoint")
    required(ROOT / "services/05_retrieval_knowledge/data/football_trivia_qa.txt", "retrieval seed data")

    if not args.files_only:
        env = ROOT / ".env"
        if not env.is_file():
            failures.append(".env missing: copy .env.example and set local secrets")
        else:
            values = {}
            for line in env.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip()
            for key in ("POSTGRES_PASSWORD", "JWT_SECRET_KEY", "SEED_ADMIN_PASSWORD", "SEED_DEMO_PASSWORD"):
                value = values.get(key, "")
                if not value or value.startswith(("change-this", "replace-this")):
                    failures.append(f".env: set a real {key} value")
            if values.get("JWT_SECRET_KEY") and len(values["JWT_SECRET_KEY"]) < 32:
                failures.append(".env: JWT_SECRET_KEY must be at least 32 characters")

        docker = shutil.which("docker")
        if docker is None:
            failures.append("Docker CLI missing")
        else:
            for command, label in (
                ([docker, "info", "--format", "{{.ServerVersion}}"], "Docker daemon"),
                ([docker, "compose", "version"], "Docker Compose plugin"),
            ):
                try:
                    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=15)
                except subprocess.TimeoutExpired:
                    failures.append(f"{label} timed out")
                else:
                    if result.returncode:
                        failures.append(f"{label} unavailable: {(result.stderr or result.stdout).strip()[:180]}")
            if env.is_file():
                try:
                    result = subprocess.run(
                        [docker, "compose", "--env-file", str(env), "-f", str(ROOT / "docker-compose.yml"), "config", "--quiet"],
                        cwd=ROOT, capture_output=True, text=True, check=False, timeout=20,
                    )
                except subprocess.TimeoutExpired:
                    failures.append("Compose config check timed out")
                else:
                    if result.returncode:
                        failures.append(f"Compose config invalid: {(result.stderr or result.stdout).strip()[:300]}")

    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    if failures:
        print(f"Preflight failed: {len(failures)} blocker(s)", file=sys.stderr)
        return 1
    print("Preflight passed: required service files are present" + ("" if args.files_only else " and Docker is available"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
