"""Ingest, index, generate and publish the latest complete weekly report.

Run only against the intended demonstration database: this uses the real
football-data provider and publishes a report through the admin API.
"""

from __future__ import annotations

import os
import sys
import time

from smoke import expect, login


def wait_for_job(admin, job_id: str, label: str, *, seconds: int = 300) -> dict:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        job = expect(admin, f"/api/admin/jobs/{job_id}", 200)
        if job.get("status") == "done":
            print(f"OK {label}: {job_id}")
            return job
        if job.get("status") == "failed":
            raise ValueError(f"{label} failed: {job.get('detail') or job}")
        time.sleep(5)
    raise TimeoutError(f"{label} did not finish in {seconds}s: {job_id}")


def wait_for_index(admin, *, seconds: int = 180) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        status = expect(admin, "/api/admin/pipeline", 200).get("status", {})
        sync = status.get("index_sync", {})
        if sync.get("pending") == 0:
            print("OK index queue drained")
            return
        time.sleep(5)
    raise TimeoutError("Index queue did not drain; check 05 and 07 logs")


def latest_report(admin, *, status: str | None = None) -> dict | None:
    path = "/api/admin/reports" + (f"?status={status}" if status else "")
    items = expect(admin, path, 200).get("items", [])
    if not items:
        return None
    return max(items, key=lambda item: (item.get("season", ""), item.get("matchweek", 0)))


def verify_published(admin, report: dict) -> None:
    season, week = report["season"], report["matchweek"]
    public = expect(admin, f"/api/football/reports/weekly?season={season}&matchweek={week}", 200)
    if public.get("status") != "published":
        raise ValueError("Published report is not visible through the public API")
    wait_for_index(admin)
    print(f"OK published weekly report {season} MW{week}")


def main() -> int:
    password = os.getenv("SEED_ADMIN_PASSWORD")
    if not password or not os.getenv("FOOTBALL_DATA_API_KEY"):
        print("Set SEED_ADMIN_PASSWORD and FOOTBALL_DATA_API_KEY in .env.", file=sys.stderr)
        return 2
    try:
        admin = login("admin", password)
        ingest = expect(
            admin, "/api/admin/pipeline/ingest", 202,
            method="POST", body={"scope": "fixtures"},
        )
        wait_for_job(admin, ingest["job_id"], "fixtures ingest")
        wait_for_index(admin)

        report_job = expect(
            admin, "/api/admin/reports/generate", 202,
            method="POST", body={},
        )
        try:
            wait_for_job(admin, report_job["job_id"], "weekly report")
        except ValueError as exc:
            published = latest_report(admin, status="published")
            # 07 stores only ServiceError.detail in job history, not its code.
            if published and "รายงานนี้เผยแพร่แล้ว" in str(exc):
                verify_published(admin, published)
                return 0
            raise

        candidates = [
            report for report in (
                latest_report(admin, status="draft"),
                latest_report(admin, status="unpublished"),
                latest_report(admin, status="published"),
            ) if report is not None
        ]
        report = max(candidates, key=lambda item: (item["season"], item["matchweek"])) if candidates else None
        if report is None:
            raise ValueError("Report job finished but no report was found")
        if report["status"] == "published":
            verify_published(admin, report)
            return 0
        season, week = report["season"], report["matchweek"]
        published = expect(
            admin, f"/api/admin/reports/{season}/{week}/publish", 200, method="POST"
        )
        if published.get("status") != "published":
            raise ValueError(f"Unexpected report status after publish: {published.get('status')}")
        verify_published(admin, published)
        return 0
    except (OSError, ValueError, KeyError, TimeoutError) as exc:
        print(f"FAIL warmup: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
