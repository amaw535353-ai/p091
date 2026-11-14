#!/usr/bin/env python3
"""Run pinned Promptfoo against a temporary synthetic loopback API only."""

from __future__ import annotations

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
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "evaluations/promptfoo"


def main() -> int:
    out = ROOT / "docs/evidence/promptfoo"
    out.mkdir(parents=True, exist_ok=True)
    # Never interpret a previous result file after a failed current execution.
    for filename in ("results.json", "manifest.json", "promptfoo.log", "api.log"):
        (out / filename).unlink(missing_ok=True)
    env = dict(os.environ)
    env.update({
        "PROMPTFOO_DISABLE_TELEMETRY": "1", "PROMPTFOO_DISABLE_UPDATE_CHECK": "1",
        "PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION": "1", "PROMPTFOO_DISABLE_SHARE": "1",
        "PROMPTFOO_CONFIG_DIR": str(ROOT / "work/promptfoo"),
        "PROMPTFOO_DISABLE_PROGRESS_BAR": "1", "LAB_MODE": "offline",
        "DATABASE_URL": "sqlite:///:memory:",
    })
    if not (EVAL / "node_modules/.bin/promptfoo").exists():
        install = subprocess.run(["npm", "--cache", str(ROOT / "work/npm-cache"), "ci", "--no-audit", "--no-fund"], cwd=EVAL, env=env, check=False)
        if install.returncode:
            print("Pinned Promptfoo dependency installation failed; no evaluation results claimed.")
            return install.returncode
    with tempfile.TemporaryDirectory(prefix="p091-eval-") as temporary:
        env["PROMPTFOO_CONFIG_DIR"] = str(Path(temporary) / "promptfoo")
        env["DATABASE_URL"] = "sqlite:///" + str(Path(temporary) / "lab.sqlite3")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env["P091_BASE_URL"] = f"http://127.0.0.1:{port}"
        server_command = [sys.executable, "-m", "uvicorn", "p091.main:create_app", "--factory", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"]
        with (out / "api.log").open("w") as log:
            server = subprocess.Popen(server_command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                ready = False
                for _ in range(100):
                    if server.poll() is not None:
                        break
                    try:
                        with urlopen(env["P091_BASE_URL"] + "/health/ready", timeout=0.3) as response:
                            ready = response.status == 200
                        if ready:
                            break
                    except (URLError, OSError):
                        time.sleep(0.1)
                if not ready:
                    print(f"Isolated API did not become ready; inspect {out / 'api.log'}. No evaluations claimed.")
                    return 1
                command = [str(EVAL / "node_modules/.bin/promptfoo"), "eval", "--config", "promptfooconfig.yaml", "--no-cache", "--no-table", "--output", str(out / "results.json")]
                started = datetime.now(timezone.utc)
                result = subprocess.run(command, cwd=EVAL, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
                (out / "promptfoo.log").write_text(result.stdout)
                print(result.stdout, end="")
                summary = None
                if (out / "results.json").exists():
                    data = json.loads((out / "results.json").read_text())
                    summary = data.get("results", {}).get("stats")
                manifest = {
                    "engagement": "P-091", "evidence_id": "P091-PROMPTFOO-" + started.strftime("%Y%m%dT%H%M%SZ"),
                    "started_utc": started.isoformat(), "finished_utc": datetime.now(timezone.utc).isoformat(),
                    "command": command, "exit_code": result.returncode,
                    "provider": "local deterministic extractive API", "model": None, "sample_count_per_case": 1,
                    "promptfoo_version": "0.125.1", "stats_observed": summary,
                    "external_model_requests": 0, "telemetry_disabled": True,
                    "configuration_sha256": hashlib.sha256((EVAL / "promptfooconfig.yaml").read_bytes()).hexdigest(),
                    "provider_sha256": hashlib.sha256((EVAL / "local-provider.cjs").read_bytes()).hexdigest(),
                    "results_sha256": hashlib.sha256((out / "results.json").read_bytes()).hexdigest() if (out / "results.json").exists() else None,
                    "limitation": "Deterministic authorization regression; no stochastic-model jailbreak resistance measured.",
                }
                (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
                return result.returncode
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == "__main__":
    raise SystemExit(main())
