"""
Safe smoke test — does NOT disable anyone.

Checks that this machine can load .env and talk to each configured platform.
Run after setup (with the vault .env in place):

  .\\.venv\\Scripts\\python test_smoke.py

Exit code 0 = everything configured+ok (or intentionally not configured).
Exit code 1 = at least one configured platform failed (usually expired session).
"""

from __future__ import annotations

import sys

import env_loader  # noqa: F401 — loads .env
from env_loader import reload_env

reload_env()


def _row(name: str, result: dict) -> str:
    configured = bool(result.get("configured"))
    ok = bool(result.get("ok"))
    if not configured:
        status = "SKIP (not configured)"
    elif ok:
        status = "OK"
    else:
        status = "FAIL"
    message = (result.get("message") or result.get("detail") or "").strip()
    if len(message) > 100:
        message = message[:97] + "..."
    return f"  {name:<18} {status:<22} {message}"


def main() -> int:
    print("User Disabling Platform — smoke test")
    print("(Read-only. Does not disable or modify any accounts.)\n")

    results: list[tuple[str, dict]] = []

    # --- Autodesk token ---
    try:
        from acc_client import get_autodesk_access_token
        import os

        client_id = (os.getenv("AUTODESK_CLIENT_ID") or "").strip()
        client_secret = (os.getenv("AUTODESK_CLIENT_SECRET") or "").strip()
        if not client_id or not client_secret:
            results.append(("Autodesk ACC", {
                "configured": False,
                "ok": False,
                "message": "AUTODESK_CLIENT_ID / SECRET not set",
            }))
        else:
            token = get_autodesk_access_token()
            results.append(("Autodesk ACC", {
                "configured": True,
                "ok": bool(token),
                "message": "Access token obtained" if token else "Empty token",
            }))
    except Exception as exc:
        results.append(("Autodesk ACC", {
            "configured": True,
            "ok": False,
            "message": str(exc),
        }))

    # --- Platform health helpers ---
    checkers = []

    try:
        from stratus_api import check_stratus_session_health
        checkers.append(("Stratus (prod)", lambda: check_stratus_session_health("prod")))
        checkers.append(("Stratus (dev)", lambda: check_stratus_session_health("dev")))
    except Exception as exc:
        results.append(("Stratus", {"configured": True, "ok": False, "message": str(exc)}))

    try:
        from revisto_api import (
            ReviztoAuthError,
            get_current_user_licenses,
            get_revizto_access_token,
            revizto_auth_help,
            revizto_configured,
            revizto_member_actions_ready,
        )

        def _revizto():
            if not revizto_configured():
                return {
                    "configured": False,
                    "ok": False,
                    "message": "Revizto tokens not set",
                }
            if not revizto_member_actions_ready():
                return {
                    "configured": True,
                    "ok": False,
                    "message": "Session cookie missing — run scripts\\connect-revizto.bat",
                }
            try:
                get_revizto_access_token(allow_refresh=False)
                licenses = get_current_user_licenses()
                license_name = licenses[0].get("name") if licenses else "license"
                return {
                    "configured": True,
                    "ok": True,
                    "message": f"Connected ({license_name})",
                }
            except ReviztoAuthError as exc:
                return {
                    "configured": True,
                    "ok": False,
                    "message": revizto_auth_help(exc),
                }

        checkers.append(("Revizto", _revizto))
    except Exception as exc:
        results.append(("Revizto", {"configured": True, "ok": False, "message": str(exc)}))

    try:
        from trackvia_integration import check_trackvia_health
        checkers.append(("TrackVia", check_trackvia_health))
    except Exception as exc:
        results.append(("TrackVia", {"configured": True, "ok": False, "message": str(exc)}))

    try:
        from openspace_api import check_openspace_health
        checkers.append(("OpenSpace", check_openspace_health))
    except Exception as exc:
        results.append(("OpenSpace", {"configured": True, "ok": False, "message": str(exc)}))

    try:
        from symetri_api import check_symetri_health
        checkers.append(("Symetri", check_symetri_health))
    except Exception as exc:
        results.append(("Symetri", {"configured": True, "ok": False, "message": str(exc)}))

    try:
        from plangrid_api import check_plangrid_health
        checkers.append(("PlanGrid", check_plangrid_health))
    except Exception as exc:
        results.append(("PlanGrid", {"configured": True, "ok": False, "message": str(exc)}))

    for name, fn in checkers:
        try:
            results.append((name, fn() or {}))
        except Exception as exc:
            results.append((name, {
                "configured": True,
                "ok": False,
                "message": str(exc),
            }))

    print("Platform status:")
    failures = 0
    for name, result in results:
        print(_row(name, result if isinstance(result, dict) else {}))
        if result.get("configured") and not result.get("ok"):
            failures += 1

    print()
    if failures:
        print(f"RESULT: {failures} configured platform(s) failed.")
        print("Fix: refresh sessions with scripts\\connect-*.bat, or update .env from the vault.")
        return 1

    print("RESULT: All configured platforms look OK on this machine.")
    print("Next: run scripts\\run-app.bat and open http://127.0.0.1:5000")
    return 0


if __name__ == "__main__":
    sys.exit(main())
