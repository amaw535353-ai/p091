#!/usr/bin/env python3
"""Optional real-Chromium smoke test; requires Playwright and a local Chromium."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-python", default=str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable)
    parser.add_argument("--chromium", default="/usr/bin/chromium")
    args = parser.parse_args()
    out = ROOT / "docs/evidence/ui"
    out.mkdir(parents=True, exist_ok=True)
    for filename in ("manifest.json", "offline.png", "mobile.png", "api.log"):
        (out / filename).unlink(missing_ok=True)
    checks = []
    errors = []
    started = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory(prefix="p091-browser-") as temporary:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        env = {**os.environ, "LAB_MODE": "offline", "DATABASE_URL": "sqlite:///" + str(Path(temporary) / "lab.sqlite3")}
        command = [args.api_python, "-m", "uvicorn", "p091.main:create_app", "--factory", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"]
        with (out / "api.log").open("w") as api_log:
            server = subprocess.Popen(command, cwd=ROOT, env=env, stdout=api_log, stderr=subprocess.STDOUT)
            try:
                ready = False
                for _ in range(100):
                    if server.poll() is not None:
                        break
                    try:
                        with urlopen(base + "/health/ready", timeout=0.3) as response:
                            ready = response.status == 200
                        if ready:
                            break
                    except (URLError, OSError):
                        time.sleep(0.1)
                if not ready:
                    raise RuntimeError("Isolated browser API did not become ready")

                def api(path, body=None, token=None, method="POST"):
                    request = Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method)
                    request.add_header("Content-Type", "application/json")
                    if token:
                        request.add_header("Authorization", "Bearer " + token)
                    with urlopen(request, timeout=5) as response:
                        return json.load(response)

                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(executable_path=args.chromium, headless=True, args=["--no-sandbox"])
                    page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(base)
                    expect(page.locator("#mode-badge")).to_have_text("OFFLINE · SYNTHETIC DATA")
                    checks.append("UI-001 offline synthetic mode is visibly labeled")
                    page.locator("#user-select").select_option("nw-employee")
                    page.locator("#login-button").click()
                    expect(page.locator("#identity")).to_be_visible()
                    expect(page.locator("#status")).to_contain_text("Session ready")
                    expect(page.locator("#documents")).to_contain_text("Northwind HR Handbook")
                    expect(page.locator("#documents")).not_to_contain_text("Finance Forecast")
                    expect(page.locator("#documents")).not_to_contain_text("Contoso")
                    checks.append("UI-002 employee sees permitted sources without Finance or other-tenant titles")
                    page.locator("#question").fill("HR handbook")
                    page.locator("#ask-button").click()
                    expect(page.locator("#answer-text")).to_contain_text("NW_HR_CANARY")
                    expect(page.locator("#answer-text")).not_to_contain_text("NW_FINANCE_CANARY")
                    expect(page.locator("#citations button")).to_have_count(1)
                    page.locator("#citations button").click()
                    expect(page.locator("#preview-body")).to_contain_text("NW_HR_CANARY")
                    checks.append("UI-003 permitted answer has an independently opened source citation")
                    page.screenshot(path=str(out / "offline.png"), full_page=True)

                    admin = api("/lab/login", {"user_id": "nw-admin"})["access_token"]
                    documents = api("/documents", token=admin, method="GET")["documents"]
                    handbook = next(document for document in documents if document["title"] == "Northwind HR Handbook")
                    malicious = '<img src=x onerror="window.p091XssProbe=1">'
                    api("/admin/documents/" + handbook["id"], {"body": "NW_HR_CANARY. SAFE_XSS_FIXTURE " + malicious, "title": "Northwind HR Handbook " + malicious}, admin, "PATCH")
                    api("/admin/documents/" + handbook["id"] + "/reindex", token=admin)
                    page.locator("#refresh-button").click()
                    expect(page.locator("#documents")).to_contain_text("SAFE_XSS_FIXTURE")
                    expect(page.locator("#documents img")).to_have_count(0)
                    page.locator("#documents button").filter(has_text="HR Handbook").click()
                    expect(page.locator("#preview-body")).to_contain_text(malicious)
                    expect(page.locator("#preview img")).to_have_count(0)
                    assert page.evaluate("typeof window.p091XssProbe") == "undefined"
                    checks.append("UI-004 untrusted title/body markup remains literal text and executes no handler")

                    page.locator("#logout-button").click()
                    expect(page.locator("#login-form")).to_be_visible()
                    expect(page.locator("#documents")).not_to_contain_text("NW_HR_CANARY")
                    expect(page.locator("#answer-text")).to_have_text("")
                    expect(page.locator("#preview-body")).to_have_text("")
                    checks.append("UI-005 logout removes bearer state and rendered source/answer/preview text")
                    page.locator("#user-select").select_option("co-employee")
                    page.locator("#login-button").click()
                    expect(page.locator("#status")).to_contain_text("Session ready")
                    expect(page.locator("#documents")).to_contain_text("Contoso HR Handbook")
                    expect(page.locator("#documents")).not_to_contain_text("Northwind")
                    page.locator("#question").fill("Welcome")
                    page.locator("#ask-button").click()
                    expect(page.locator("#answer-text")).to_contain_text("CO_WELCOME_CANARY")
                    expect(page.locator("#answer-text")).not_to_contain_text("NW_WELCOME_CANARY")
                    checks.append("UI-006 changing to second tenant loads that tenant's permitted answer")
                    storage = page.evaluate("({local:Object.keys(localStorage),session:Object.keys(sessionStorage)})")
                    assert storage == {"local": [], "session": []}
                    checks.append("UI-007 offline bearer credentials are absent from localStorage/sessionStorage")
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    page.screenshot(path=str(out / "mobile.png"), full_page=True)
                    checks.append("UI-008 mobile layout has no horizontal overflow at 390 pixels")
                    assert not errors, errors
                    checks.append("UI-009 Chromium emitted no uncaught page errors")
                    browser_version = browser.version
                    browser.close()
                manifest = {
                    "engagement": "P-091", "evidence_id": "P091-UI-" + started.strftime("%Y%m%dT%H%M%SZ"),
                    "started_utc": started.isoformat(), "finished_utc": datetime.now(timezone.utc).isoformat(),
                    "command": [sys.executable, "apps/web/check_browser.py", "--api-python", args.api_python, "--chromium", args.chromium],
                    "browser": "Chromium", "browser_version": browser_version, "mode": "offline synthetic",
                    "checks": [{"test_id": value.split()[0], "description": value, "status": "PASS"} for value in checks],
                    "denominator": len(checks), "PASS": len(checks), "FAIL": 0, "uncaught_page_errors": errors,
                    "screenshots_sha256": {filename: hashlib.sha256((out / filename).read_bytes()).hexdigest() for filename in ("offline.png", "mobile.png")},
                    "scope": "Offline browser workflows only. Keycloak PKCE and live service UI paths are not exercised here.",
                }
                (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
                print(json.dumps({"PASS": len(checks), "denominator": len(checks), "manifest": str(out / "manifest.json")}, indent=2))
                return 0
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == "__main__":
    raise SystemExit(main())
