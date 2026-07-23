"""TrackVia integration facade — direct Open API."""

from concurrent.futures import ThreadPoolExecutor, as_completed

from trackvia_api import (
    TrackViaApiError,
    TrackViaConfigError,
    TrackViaUserNotFoundError,
    check_trackvia_health as check_direct_trackvia_health,
    disable_trackvia_user_by_email as disable_trackvia_direct,
    enable_trackvia_user_by_email as enable_trackvia_direct,
    find_record_by_email,
    get_all_view_records,
    records_endpoint_available,
    summarize_record,
    trackvia_configured as direct_trackvia_configured,
)
from trackvia_config import get_trackvia_settings, trackvia_missing_settings


# This will be used to get the trackvia backend
def trackvia_backend():
    if direct_trackvia_configured():
        return "api"
    return None

# This will be used to check if the trackvia is configured
def trackvia_configured():
    return direct_trackvia_configured()


# This will be used to check if the trackvia supports bulk sync
def trackvia_supports_bulk_sync():
    if not trackvia_configured():
        return False
    try:
        return records_endpoint_available()
    except TrackViaConfigError:
        return False

# This will be used to lookup the trackvia user by email
def lookup_trackvia_user(email):
    if not trackvia_configured():
        missing = ", ".join(trackvia_missing_settings())
        raise TrackViaConfigError(
            f"TrackVia is not configured. Set {missing} in .env."
        )

    record = find_record_by_email(email)
    if not record:
        return None
    summary = summarize_record(record)
    summary["source"] = "api"
    summary["present"] = True
    summary["membership_status"] = "disabled" if summary["disabled"] else "active"
    return summary

# This will be used to disable the trackvia user by email
def disable_trackvia_user_by_email(email):
    return disable_trackvia_direct(email)

# This will be used to enable the trackvia user by email
def enable_trackvia_user_by_email(email):
    return enable_trackvia_direct(email)

# This will be used to check the trackvia health
def check_trackvia_health():
    if not trackvia_configured():
        label = get_trackvia_settings()["label"]
        missing = ", ".join(trackvia_missing_settings())
        return {
            "ok": False,
            "configured": False,
            "label": label,
            "backend": None,
            "message": f"{label} is not configured on this server. Set {missing} in .env.",
        }

    health = check_direct_trackvia_health()
    health["backend"] = "api"
    return health

# This will be used to list the trackvia users for sync
def list_trackvia_users_for_sync():
    if not trackvia_supports_bulk_sync():
        return []
    return get_all_view_records()

# This will be used to index the trackvia users by email
def index_trackvia_users_by_email(emails):
    """
    Build email -> TrackVia summary for roster sync.
    Uses bulk list when available; otherwise per-email find (slower).
    """
    if not trackvia_configured():
        return {}

    if trackvia_supports_bulk_sync():
        by_email = {}
        for record in list_trackvia_users_for_sync():
            summary = summarize_record(record)
            email = (summary.get("email") or "").strip().lower()
            if email:
                by_email[email] = summary
        return by_email

    from trackvia_api import find_record_by_email

    normalized_emails = []
    for email in emails:
        normalized = (email or "").strip().lower()
        if normalized and "@" in normalized:
            normalized_emails.append(normalized)

    by_email = {}

    def _lookup_one(address):
        record = find_record_by_email(address)
        if not record:
            return None
        summary = summarize_record(record)
        key = (summary.get("email") or address).strip().lower()
        return key, summary

    workers = min(8, max(1, len(normalized_emails)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_lookup_one, address) for address in normalized_emails]
        for future in as_completed(futures):
            try:
                result = future.result()
            except TrackViaApiError:
                continue
            if not result:
                continue
            key, summary = result
            by_email[key] = summary
    return by_email
