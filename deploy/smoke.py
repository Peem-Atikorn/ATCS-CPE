"""Exercise the running Compose stack through API 02, not service stubs.

This is a connectivity and contract smoke test. It does not establish that an
answer is factually correct; the eval runner handles that separately.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request
from uuid import uuid4

API = os.getenv("API_URL", "http://api:8000").rstrip("/")


def request(opener, path: str, *, method: str = "GET", body: dict | None = None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    rid = str(uuid4())
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "X-Request-ID": rid},
    )
    try:
        response = opener.open(req, timeout=60)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        payload = json.load(response)
        header_rid = response.headers.get("X-Request-ID")
        if header_rid != rid:
            raise ValueError(f"{path}: request ID changed ({rid} -> {header_rid})")
        return response.status, payload


def login(username: str, password: str):
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    status, data = request(
        opener, "/api/auth/login", method="POST", body={"username": username, "password": password}
    )
    if status != 200 or data.get("user", {}).get("username") != username:
        raise ValueError(f"{username}: login returned HTTP {status}: {data}")
    return opener


def expect(opener, path: str, status: int, *, method: str = "GET", body: dict | None = None):
    actual, data = request(opener, path, method=method, body=body)
    if actual != status:
        raise ValueError(f"{path}: expected HTTP {status}, got {actual}: {data}")
    return data


def main() -> int:
    failures: list[str] = []
    checks = 0

    def check(label: str, action) -> None:
        nonlocal checks
        checks += 1
        try:
            action()
            print(f"OK {label}")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            failures.append(f"{label}: {type(exc).__name__}: {exc}")

    health = {
        "web": "http://web:3000/health",
        "api": API + "/ready",
        "router": "http://router:8000/health",
        "engines": "http://engines:8000/health",
        "retrieval": "http://retrieval:8000/ready",
        "generation": "http://generation:8000/health",
        "football-data": "http://football-data:8000/ready",
    }
    for name, url in health.items():
        def health_check(url=url):
            with urllib.request.urlopen(url, timeout=15) as response:
                data = json.load(response)
                if response.status != 200 or data.get("status") != "ok":
                    raise ValueError(f"HTTP {response.status}: {data}")

        check(name, health_check)

    anonymous = urllib.request.build_opener()
    check("admin requires login", lambda: expect(anonymous, "/api/admin/stats", 401))

    demo_password = os.getenv("SEED_DEMO_PASSWORD")
    admin_password = os.getenv("SEED_ADMIN_PASSWORD")
    if not demo_password or not admin_password:
        print("FAIL Set SEED_DEMO_PASSWORD and SEED_ADMIN_PASSWORD for smoke.", file=sys.stderr)
        return 2

    demo = None
    admin = None

    def demo_access():
        nonlocal demo
        demo = login("demo1", demo_password)
        expect(demo, "/api/admin/stats", 403)

    def admin_access():
        nonlocal admin
        admin = login("admin", admin_password)
        stats = expect(admin, "/api/admin/stats", 200)
        if "latency_ms" not in stats or "by_route" not in stats:
            raise ValueError("admin stats has unexpected shape")

    check("demo cannot access admin", demo_access)
    check("admin dashboard", admin_access)

    if demo is not None:
        # Queries are taken from 03's routing cases. A smoke pass checks that
        # each route can be reached through 02; it does not assert answer facts.
        routes = (
            ("football_rag", "ใครได้บัลลงดอร์ปี 2008"),
            ("general_ai", "อธิบายกฎล้ำหน้าแบบง่าย ๆ"),
            ("local_ai", "ทำนายผล ลิเวอร์พูล กับ แมนซิตี้"),
            ("clarify", "ยูไนเต็ดนัดล่าสุดชนะไหม"),
            ("decline", "ขอทีเด็ดบอลคืนนี้"),
        )
        for route, question in routes:
            def route_check(route=route, question=question):
                answer = expect(demo, "/api/chat", 200, method="POST", body={"message": question})
                if answer.get("route") != route or not answer.get("answer"):
                    raise ValueError(f"expected {route} with an answer, got {answer}")
                if not answer.get("request_id") or not answer.get("message_id"):
                    raise ValueError("chat response lacks request_id/message_id")

            check(f"chat route {route}", route_check)

    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    print(f"{checks - len(failures)}/{checks} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
