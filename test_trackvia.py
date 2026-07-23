"""Manual test helper for direct TrackVia API access."""

import argparse
import json
import sys

import env_loader  # noqa: F401
from trackvia_integration import (
    TrackViaApiError,
    TrackViaConfigError,
    TrackViaUserNotFoundError,
    check_trackvia_health,
    disable_trackvia_user_by_email,
    enable_trackvia_user_by_email,
    lookup_trackvia_user,
    trackvia_backend,
    trackvia_configured,
)
from trackvia_api import _api_request, list_record_field_names, list_views
from trackvia_config import get_trackvia_settings



# This will be used to main function.
def main():
    parser = argparse.ArgumentParser(description="Test TrackVia direct API from this machine.")
    parser.add_argument(
        "action",
        choices=["health", "views", "fields", "probe", "lookup", "disable", "activate"],
        help="Action to run",
    )
    parser.add_argument("email", nargs="?", default="", help="Email (required except health)")
    args = parser.parse_args()

    if not trackvia_configured():
        print(
            "TrackVia is not configured. Set TRACKVIA_API_KEY, TRACKVIA_ACCESS_TOKEN, "
            "and TRACKVIA_VIEW_ID in .env.",
            file=sys.stderr,
        )
        return 1

    print(f"backend: {trackvia_backend()}", file=sys.stderr)

    try:
        if args.action == "health":
            result = check_trackvia_health()
        elif args.action == "probe":
            settings = get_trackvia_settings()
            view_id = settings["view_id"]
            probes = []
            for label, method, path, params in (
                ("find", "GET", f"/views/{view_id}/find", {"q": "test@example.com"}),
                ("records", "GET", f"/views/{view_id}/records", {"start": 0, "max": 1}),
            ):
                try:
                    _api_request(method, path, params=params, timeout=20)
                    probes.append({"endpoint": label, "ok": True})
                except TrackViaApiError as exc:
                    probes.append({"endpoint": label, "ok": False, "error": str(exc)})
            result = {"ok": all(p["ok"] for p in probes), "probes": probes}
        elif args.action == "fields":
            if not args.email:
                print("email is required for fields.", file=sys.stderr)
                return 1
            result = list_record_field_names(args.email)
            if result is None:
                result = {"ok": False, "present": False, "email": args.email}
            else:
                result = {"ok": True, "present": True, **result}
        elif args.action == "views":
            settings = get_trackvia_settings()
            views = list_views()
            result = {
                "ok": True,
                "count": len(views),
                "configured_view_id": settings["view_id"],
                "views": [
                    {
                        "id": v.get("id"),
                        "name": v.get("name") or v.get("viewName"),
                    }
                    for v in views
                    if isinstance(v, dict)
                ],
            }
        else:
            if not args.email:
                print("email is required for this action.", file=sys.stderr)
                return 1
            if args.action == "lookup":
                result = lookup_trackvia_user(args.email)
                if result is None:
                    result = {"ok": True, "present": False, "email": args.email}
            elif args.action == "disable":
                result = disable_trackvia_user_by_email(args.email)
            else:
                result = enable_trackvia_user_by_email(args.email)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("ok", True) else 1
    except TrackViaUserNotFoundError as exc:
        print(json.dumps({"ok": False, "present": False, "error": str(exc)}, indent=2))
        return 2
    except (TrackViaConfigError, TrackViaApiError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
