"""Manual test helper for OpenSpace org member removal."""

import argparse
import json
import sys

import env_loader  # noqa: F401
from openspace_api import (
    OpenSpaceApiError,
    OpenSpaceConfigError,
    OpenSpaceUserNotFoundError,
    check_openspace_health,
    disable_openspace_user_by_email,
    find_org_member_by_email,
    openspace_configured,
)


# This wil be used to test the openspace org admin API from this machine.
def main():
    parser = argparse.ArgumentParser(description="Test OpenSpace org admin API from this machine.")
    parser.add_argument(
        "action",
        choices=["health", "lookup", "disable"],
        help="Action to run",
    )
    parser.add_argument("email", nargs="?", default="", help="Email (required except health)")
    args = parser.parse_args()

    if not openspace_configured():
        print(
            "OpenSpace is not configured. Set OPENSPACE_ORG_ID and OPENSPACE_SESSION_COOKIE in .env.",
            file=sys.stderr,
        )
        return 1

    try:
        if args.action == "health":
            result = check_openspace_health()
        elif args.action == "lookup":
            if not args.email:
                print("email is required for lookup.", file=sys.stderr)
                return 1
            member = find_org_member_by_email(args.email)
            result = {"ok": bool(member), "present": bool(member), "member": member}
        else:
            if not args.email:
                print("email is required for disable.", file=sys.stderr)
                return 1
            result = disable_openspace_user_by_email(args.email)
    except OpenSpaceUserNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OpenSpaceConfigError, OpenSpaceApiError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
