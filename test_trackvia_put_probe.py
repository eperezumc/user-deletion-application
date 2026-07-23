"""Probe TrackVia record update formats (sandbox testing)."""
import json
import sys

import env_loader  # noqa: F401
import requests
from trackvia_api import TrackViaApiError, find_record_by_email, _require_config
from trackvia_config import get_trackvia_settings


def _raw_put(record_id, body, *, path_suffix=None):
    settings = _require_config()
    query = {"user_key": settings["api_key"]}
    suffix = path_suffix or f"/views/{settings['view_id']}/records/{record_id}"
    url = f"{settings['openapi_base_url']}/openapi{suffix}"
    headers = {
        "Authorization": f"Bearer {settings['access_token']}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if settings.get("account_id"):
        headers["account-id"] = settings["account_id"]
    return requests.put(url, params=query, json=body, headers=headers, timeout=30)

# Just commenting some things that need to be done. I am just fillabusterin for now.
def main():
    email = sys.argv[1] if len(sys.argv) > 1 else "eherdman@umci.com"
    settings = get_trackvia_settings()
    record = find_record_by_email(email)
    if not record:
        print(json.dumps({"ok": False, "error": "record not found"}, indent=2))
        return 1
    record_id = record.get("id")
    current = record.get(settings["status_field"]) or record.get("TrackVia Usage")
    get_record = None
    try:
        from trackvia_api import _api_request
        get_record = _api_request(
            "GET",
            f"/views/{settings['view_id']}/records/{record_id}",
        )
    except Exception as exc:
        get_record = {"error": str(exc)}

    print(json.dumps({
        "email": email,
        "record_id": record_id,
        "current_status": current,
        "current_usage_array": record.get("Usage"),
        "status_field": settings["status_field"],
        "disabled_value": settings["status_disabled"],
        "get_record": get_record,
    }, indent=2, default=str))

    attempts = [
        {"Reviewer Code": "api-test"},
        {"TrackVia Usage": "Deactivate Now"},
        {"TrackVia Usage for Testing": "Deactivate Now"},
    ]

    results = []
    for body in attempts:
        resp = _raw_put(record_id, body)
        results.append({
            "endpoint": "view",
            "body_keys": list(body.keys()),
            "status_code": resp.status_code,
            "response": resp.text[:800],
        })
    table_body = {"TrackVia Usage": "Deactivate Now"}
    resp = _raw_put(record_id, table_body, path_suffix=f"/tables/22/records/{record_id}")
    results.append({
        "endpoint": "table/22",
        "body_keys": list(table_body.keys()),
        "status_code": resp.status_code,
        "response": resp.text[:800],
    })
    print(json.dumps({"attempts": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
