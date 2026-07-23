"""Manual test helper for Symetri account user removal."""

import argparse
import json
import sys

import env_loader  # noqa: F401
from symetri_api import (
    SymetriApiError,
    SymetriConfigError,
    SymetriUserNotFoundError,
    check_symetri_health,
    find_account_user_by_email,
    remove_symetri_user_by_email,
)
from symetri_config import symetri_configured


def main():
    parser = argparse.ArgumentParser(description="Test Symetri My Symetri API from this machine.")
    parser.add_argument(
        "action",
        choices=["health", "lookup", "delete"],
        help="Action to run",
    )
    parser.add_argument("email", nargs="?", default="", help="Email (required except health)")
    args = parser.parse_args()

    if not symetri_configured():
        print(
            "Symetri is not configured. Set SYMETRI_ACCOUNT_ID and SYMETRI_BEARER_TOKEN in .env.",
            file=sys.stderr,
        )
        return 1

    try:
        if args.action == "health":
            result = check_symetri_health()
        elif args.action == "lookup":
            if not args.email:
                print("email is required for lookup.", file=sys.stderr)
                return 1
            member = find_account_user_by_email(args.email)
            result = {"ok": bool(member), "present": bool(member), "member": member}
        else:
            if not args.email:
                print("email is required for delete.", file=sys.stderr)
                return 1
            result = remove_symetri_user_by_email(args.email)
    except SymetriUserNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (SymetriConfigError, SymetriApiError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
