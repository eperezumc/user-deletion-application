"""Background interactive session reconnect jobs for the web UI."""

import json
import subprocess
import threading
import time
from pathlib import Path

from session_connect import LOGIN_TIMEOUT_SECONDS, connect_platform_session, playwright_available

_lock = threading.Lock()
_jobs = {}
PROJECT_ROOT = Path(__file__).resolve().parent

# This is the function that gets the python executable from the venv.
def _venv_python():
    candidate = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    return candidate if candidate.exists() else None

# This is the function that checks if the playwright is available in the venv.
def _venv_playwright_available():
    venv = _venv_python()
    if not venv:
        return False
    try:
        proc = subprocess.run(
            [
                str(venv),
                "-c",
                "from session_connect import playwright_available; "
                "raise SystemExit(0 if playwright_available() else 1)",
            ],
            capture_output=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


# This is the function that checks if the playwright is usable.
def _playwright_usable():
    return playwright_available() or _venv_playwright_available()


# This will be used to check if the interactice reconnect is available.
def interactive_reconnect_available():
    return _playwright_usable()

# This is the function that gets the job key.
def _job_key(platform, environment=None):
    if platform == "stratus":
        return f"stratus:{(environment or 'prod').strip().lower()}"
    return platform

# This is the function that gets the start message.
def _start_message(platform):
    if platform == "symetri":
        return (
            "A separate browser window is opening — sign in to my.symetri.com in THAT window "
            "(not this tab). This page updates when the token is saved."
        )
    if platform == "revizto":
        return (
            "Check your taskbar — a NEW browser window is opening (not this tab). "
            "Sign in there if needed, then open "
            "https://ws.revizto.com/login?request=accessCode for the API access code."
        )
    return "Opening browser — sign in when prompted."


def _job_is_stale(job, max_age_seconds=LOGIN_TIMEOUT_SECONDS + 30):
    if job.get("status") != "running":
        return False
    started_at = job.get("started_at")
    if not started_at:
        return False
    return (time.time() - started_at) > max_age_seconds

# When a job is requested, this function will return the job details.
def get_job(job_id):
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None

# This is the function that connects to the session.
def _connect_session(platform, environment):
    if playwright_available():
        return connect_platform_session(platform, environment=environment, validate=True)

    venv = _venv_python()
    if not venv or not _venv_playwright_available():
        raise RuntimeError(
            "Interactive reconnect is not available on this server. "
            "Install Playwright in .venv or run scripts\\connect-symetri.bat."
        )

    script = """
import json
import sys
from session_connect import connect_platform_session

result = connect_platform_session(sys.argv[1], environment=sys.argv[2], validate=True)
print(json.dumps(result))
"""
    proc = subprocess.run(
        [str(venv), "-c", script, platform, environment],
        capture_output=True,
        text=True,
        timeout=LOGIN_TIMEOUT_SECONDS + 120,
        cwd=str(PROJECT_ROOT),
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(detail or "Reconnect failed.")
    lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("Reconnect finished without a result.")
    return json.loads(lines[-1])


# This is the function that starts the reconnect.
def start_reconnect(platform, environment="prod"):
    if not interactive_reconnect_available():
        raise RuntimeError(
            "Interactive reconnect is not available on this server. "
            "Install Playwright or run connect_sessions.py from the command line."
        )

    platform = platform.strip().lower()
    environment = (environment or "prod").strip().lower()
    job_id = _job_key(platform, environment)

    with _lock:
        existing = _jobs.get(job_id)
        if existing and existing["status"] == "running" and not _job_is_stale(existing):
            return job_id, dict(existing)
        if existing and existing["status"] == "running":
            existing["status"] = "error"
            existing["message"] = "Previous reconnect timed out. Starting a new attempt."
            existing["finished_at"] = time.time()

        job = {
            "id": job_id,
            "platform": platform,
            "environment": environment,
            "status": "running",
            "message": _start_message(platform),
            "error": None,
            "result": None,
            "started_at": time.time(),
            "finished_at": None,
        }
        _jobs[job_id] = job

    thread = threading.Thread(
        target=_run_job,
        args=(job_id, platform, environment),
        daemon=True,
    )
    thread.start()
    return job_id, dict(job)


def _run_job(job_id, platform, environment):
    try:
        result = _connect_session(platform, environment)
        with _lock:
            job = _jobs[job_id]
            job["status"] = "success"
            job["message"] = result.get("message") or "Session connected."
            job["result"] = result
            job["finished_at"] = time.time()
    except Exception as exc:
        detail = str(exc).strip() or "Reconnect failed."
        print(f"Reconnect {platform} failed: {detail}", flush=True)
        with _lock:
            job = _jobs[job_id]
            job["status"] = "error"
            job["message"] = detail
            job["error"] = detail
            job["finished_at"] = time.time()


