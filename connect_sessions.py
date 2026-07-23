"""
Interactive login — open a browser, sign in, then push session cookies to the app.

First-time setup:
  pip install playwright

Uses Microsoft Edge or Google Chrome if installed (no extra browser download).

Examples:
  python connect_sessions.py --platform stratus --environment prod
  python connect_sessions.py --platform revizto
  python connect_sessions.py --platform stratus --server http://192.168.1.50:5000
"""

import argparse
import json
import os
import urllib.error
import urllib.request

import env_loader  
from session_connect import capture_session_cookie
from session_admin import STRATUS_LOGIN_URLS, REVIZTO_LOGIN_URL, SYMETRI_LOGIN_URL


def push_to_server(server_url, admin_key, path, payload):
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{server_url.rstrip('/')}{path}",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Session-Admin-Key": admin_key,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Server rejected cookie ({exc.code}): {detail}") from exc


def main():
    parser = argparse.ArgumentParser(description="Capture platform session cookies after login.")
    parser.add_argument(
        "--platform",
        required=True,
        choices=("stratus", "revizto", "symetri"),
        help="Which platform to sign into",
    )
    parser.add_argument(
        "--environment",
        default="prod",
        choices=("dev", "prod"),
        help="Stratus environment (ignored for Revizto)",
    )
    parser.add_argument(
        "--server",
        default="",
        help="App base URL. If set, POST cookie to the server instead of writing local .env",
    )
    parser.add_argument(
        "--admin-key",
        default="",
        help="SESSION_ADMIN_KEY (defaults to SESSION_ADMIN_KEY from .env)",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Save without testing the cookie against the platform API",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Wait for Enter instead of auto-detecting sign-in",
    )
    args = parser.parse_args()

    if args.platform == "stratus":
        login_url = STRATUS_LOGIN_URLS[args.environment]
    elif args.platform == "symetri":
        login_url = SYMETRI_LOGIN_URL
    else:
        login_url = REVIZTO_LOGIN_URL

    server_url = (args.server or os.getenv("SESSION_CONNECT_SERVER") or "").strip()
    admin_key = (args.admin_key or os.getenv("SESSION_ADMIN_KEY") or "").strip()

    if server_url and not admin_key:
        raise SystemExit(
            "SESSION_ADMIN_KEY is not set in .env.\n"
            "Add a secret value to SESSION_ADMIN_KEY, restart the app, then run this again.\n"
            "Or omit --server to save the cookie to this machine's .env only."
        )

    if args.platform == "symetri":
        from session_connect import capture_symetri_bearer_token

        print(f"Opening browser at {login_url}")
        if args.manual:
            print("Sign in at my.symetri.com, then return here and press Enter.")
        else:
            print("Sign in when the browser opens. Waiting until login completes...")

        token = capture_symetri_bearer_token(manual_confirm=args.manual)
        print(f"Captured bearer token ({len(token)} characters).")

        if server_url:
            path = "/api/admin/sessions/symetri"
            payload = {"bearer_token": token, "validate": not args.no_validate}
            result = push_to_server(server_url, admin_key, path, payload)
            print(result.get("message") or "Bearer token pushed to server.")
            return

        from session_admin import save_symetri_bearer_token

        result = save_symetri_bearer_token(token, validate=not args.no_validate)
        print(result.get("message") or "Bearer token saved to .env.")
        return

    print(f"Opening browser at {login_url}")
    if args.manual:
        print("Sign in, then return here and press Enter.")
    else:
        print("Sign in when the browser opens. Waiting until login completes...")

    cookie = capture_session_cookie(
        args.platform,
        environment=args.environment,
        manual_confirm=args.manual,
    )
    print(f"Captured {len(cookie)} characters of cookie data.")

    if server_url:
        if args.platform == "stratus":
            path = "/api/admin/sessions/stratus"
            payload = {
                "cookie": cookie,
                "environment": args.environment,
                "validate": not args.no_validate,
            }
        else:
            path = "/api/admin/sessions/revizto"
            payload = {"cookie": cookie, "validate": not args.no_validate}
        result = push_to_server(server_url, admin_key, path, payload)
        print(result.get("message") or "Cookie pushed to server.")
        return

    if args.no_validate:
        from session_admin import save_revizto_session_cookie, save_stratus_session_cookie

        if args.platform == "stratus":
            result = save_stratus_session_cookie(
                cookie, environment=args.environment, validate=False
            )
        else:
            result = save_revizto_session_cookie(cookie, validate=False)
    else:
        from session_admin import save_revizto_session_cookie, save_stratus_session_cookie

        if args.platform == "stratus":
            result = save_stratus_session_cookie(
                cookie, environment=args.environment, validate=True
            )
        else:
            result = save_revizto_session_cookie(cookie, validate=True)
    print(result.get("message") or "Cookie saved to .env.")


if __name__ == "__main__":
    main()
