"""
One-off test script for Stratus company-admin disable calls.

Usage:
  1. Log into https://www.gtpstratus.com as a company admin in Chrome.
  2. DevTools → Network → any request → Headers → copy the full Cookie value.
  3. Add to .env:
       STRATUS_SESSION_COOKIE=<paste cookie string>
       STRATUS_TEST_PK=<company-user row pk from DevTools payload>
  4. Run:
       .venv\\Scripts\\python test_stratus_disable.py --dry-run
       .venv\\Scripts\\python test_stratus_disable.py

Use a TEST user pk, not your own account, unless you are ready to revert in the UI.
"""

from __future__ import annotations

import argparse
import os
import sys

import env_loader 
import requests

STRATUS_UPDATE_URL = (
    "https://www.gtpstratus.com/companyadmin/update-company-user-role-value"
)

# This is a list of tuples that contains the disable steps for the Stratus API.
DISABLE_STEPS: list[tuple[str, str]] = [ # This is the disable steps for the Stratus API.
    ("group", "(Former Employee)"),
    ("defaultProjectRoleId", ""),
    ("userStatusTypeEnumValue", "2"),
]


# This is a function that builds the session for the Stratus API.
def build_session(cookie_header: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://www.gtpstratus.com",
            "Referer": "https://www.gtpstratus.com/companyadmin",
            "Cookie": cookie_header,
        }
    )
    return session


# This is a function that updates the field for the Stratus API.
def update_field(
    session: requests.Session,
    pk: str,
    name: str,
    value: str,
    *,
    dry_run: bool,
) -> None:
    payload = {"pk": pk, "name": name, "value": value}
    label = f"{name}={value!r}"
    if dry_run:
        print(f"[dry-run] PUT {STRATUS_UPDATE_URL}  {label}")
        return

    response = session.put(STRATUS_UPDATE_URL, data=payload, timeout=30)
    print(f"{label} -> HTTP {response.status_code}")
    if not response.ok:
        print(response.text or "(empty body)")
        response.raise_for_status()


def main() -> int:
    # The parser is used to parse the command line arguments.
    # It is used to parse the command line arguments and return a namespace object.
    # The namespace object contains the arguments and their values.
    # The arguments are:
    # --email: Look up company-user row id (pk) by email.
    # --pk: Company-user row id. Skips email lookup when provided.
    # --cookie: Full Cookie header from a logged-in admin session.
    # --dry-run: Print requests without sending them.
    parser = argparse.ArgumentParser(description="Test Stratus disable PUT calls.")
    parser.add_argument(
        "--pk",
        default=os.getenv("STRATUS_TEST_PK", ""),
        help="Company-user row pk (from DevTools payload).",
    )
    parser.add_argument(
        "--cookie",
        default=os.getenv("STRATUS_SESSION_COOKIE", ""),
        help="Full Cookie header from a logged-in admin session.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print requests without sending them.",
    )
    parser.add_argument(
        "--step",
        choices=["group", "role", "status", "all"],
        default="all",
        help="Run one step or all three (default: all).",
    )
    args = parser.parse_args()

    if not args.pk:
        print("Missing pk. Pass --pk or set STRATUS_TEST_PK in .env", file=sys.stderr)
        return 1
    if not args.cookie and not args.dry_run:
        print(
            "Missing cookie. Pass --cookie or set STRATUS_SESSION_COOKIE in .env",
            file=sys.stderr,
        )
        return 1

    # This is a dictionary that maps the step to the disable steps.
    step_map = { # This is the step map for the Stratus API.
        "group": [DISABLE_STEPS[0]],
        "role": [DISABLE_STEPS[1]],
        "status": [DISABLE_STEPS[2]],
        "all": DISABLE_STEPS,
    }
    steps = step_map[args.step]

    session = build_session(args.cookie) if args.cookie else requests.Session()

    print(f"Target pk: {args.pk}")
    for name, value in steps:
        update_field(session, args.pk, name, value, dry_run=args.dry_run)

    if not args.dry_run:
        print("Done. Refresh Admin → Company → Users in Stratus to confirm.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
