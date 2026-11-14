#!/usr/bin/env python3
"""Hold authorized old-session responses across a tenant change in Chromium."""
from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    out = ROOT / "docs/evidence/ui"
    out.mkdir(parents=True, exist_ok=True)
    (out / "race-retest.json").unlink(missing_ok=True)
    started = datetime.now(timezone.utc)
    observations = []
    with tempfile.TemporaryDirectory(prefix="p091-session-race-") as temporary:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        env = {**os.environ, "LAB_MODE": "offline", "DATABASE_URL": "sqlite:///" + str(Path(temporary) / "lab.sqlite3")}
        command = [str(ROOT / ".venv/bin/python"), "-m", "uvicorn", "p091.main:create_app", "--factory", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"]
        server = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            ready = False
            for _ in range(100):
                try:
                    with urlopen(base + "/health/ready", timeout=0.3) as response:
                        ready = response.status == 200
                    if ready:
                        break
                except (URLError, OSError):
                    time.sleep(0.1)
            assert ready, "Isolated API did not become ready"
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path="/usr/bin/chromium", headless=True, args=["--no-sandbox"])
                # Include success and error paths. Each held response is authorized
                # for Northwind, then delivered after Contoso's sign-in completes.
                for case in ("chat", "chat-error", "chat-401", "search", "documents", "preview", "citation", "history-list", "history-detail", "dashboard"):
                    page = browser.new_page()
                    page.goto(base)
                    page.locator("#user-select").select_option("nw-employee")
                    page.locator("#login-button").click()
                    expect(page.locator("#status")).to_contain_text("Session ready")
                    page.locator("#question").fill("HR handbook")
                    page.locator("#ask-button").click()
                    expect(page.locator("#answer-text")).to_contain_text("NW_HR_CANARY")
                    expect(page.locator("#ask-button")).to_be_enabled()
                    held: dict[str, Any] = {}

                    def hold(route):
                        if held:
                            route.continue_()
                            return
                        held["response"] = route.fetch()
                        held["route"] = route

                    patterns = {
                        "chat": "**/chat", "chat-error": "**/chat", "chat-401": "**/chat", "search": "**/search", "documents": "**/documents",
                        "preview": "**/documents/*", "citation": "**/citations/**", "history-list": "**/history",
                        "history-detail": "**/history/*", "dashboard": "**/dashboard",
                    }
                    pattern = patterns[case]
                    page.route(pattern, hold)
                    if case in ("chat", "chat-error", "chat-401"):
                        page.locator("#ask-button").click()
                    elif case == "search":
                        page.locator("#search").fill("HR handbook")
                        page.locator("#search-button").click()
                    elif case == "preview":
                        page.locator("#documents button").filter(has_text="HR Handbook").click()
                    elif case == "citation":
                        page.locator("#citations button").first.click()
                    elif case == "history-detail":
                        page.locator("#history button").first.click()
                    else:
                        page.locator("#refresh-button").click()
                    for _ in range(100):
                        page.wait_for_timeout(10)
                        if held:
                            break
                    assert held, f"{case}: request not intercepted"
                    page.locator("#logout-button").click()
                    expect(page.locator("#login-form")).to_be_visible()
                    page.locator("#user-select").select_option("co-employee")
                    page.locator("#login-button").click()
                    expect(page.locator("#status")).to_contain_text("Session ready")
                    expect(page.locator("#identity")).to_contain_text("contoso")
                    if case in ("chat-error", "chat-401"):
                        held["route"].fulfill(status=401 if case == "chat-401" else 503, content_type="application/json", body=json.dumps({"detail": "OLD_SESSION_ERROR_MARKER"}))
                    else:
                        held["route"].fulfill(response=held["response"])
                    page.unroute(pattern, hold)
                    page.wait_for_timeout(150)
                    assert "NW_HR_CANARY" not in page.locator("body").inner_text(), case
                    assert "Northwind" not in page.locator("#documents").inner_text(), case
                    assert "northwind" not in page.locator("#metrics").inner_text(), case
                    assert "OLD_SESSION_ERROR_MARKER" not in page.locator("#status").inner_text(), case
                    expect(page.locator("#answer")).to_be_hidden()
                    expect(page.locator("#preview")).to_be_hidden()
                    expect(page.locator("#ask-button")).to_be_enabled()
                    expect(page.locator("#status")).to_contain_text("Session ready")
                    # New-session utility still works after the old response/error.
                    page.locator("#question").fill("Welcome")
                    page.locator("#ask-button").click()
                    expect(page.locator("#answer-text")).to_contain_text("CO_WELCOME_CANARY")
                    observations.append({"test_id": "UI-RACE-" + case.upper(), "status": "PASS", "old_response_rendered": False, "new_tenant_utility": True})
                    page.close()
                browser_version = browser.version
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=5)
    manifest = {
        "engagement": "P-091", "finding": "F-002", "evidence_id": "P091-UI-RACE-" + started.strftime("%Y%m%dT%H%M%SZ"),
        "started_utc": started.isoformat(), "finished_utc": datetime.now(timezone.utc).isoformat(),
        "command": "python apps/web/check_session_race.py", "mode": "offline synthetic API + actual Chromium intercepted responses",
        "browser_version": browser_version, "app_js_sha256": hashlib.sha256((ROOT / "apps/web/app.js").read_bytes()).hexdigest(),
        "denominator": len(observations), "PASS": len(observations), "FAIL": 0, "checks": observations,
        "scope": "Old authenticated responses and an error held across logout/new tenant login; no server authorization bypass asserted.",
    }
    (out / "race-retest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"PASS": len(observations), "denominator": len(observations), "evidence": str(out / "race-retest.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
