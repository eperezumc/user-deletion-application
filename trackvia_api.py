"""TrackVia OpenAPI helpers — lookup and update roster records by email."""

import requests

import env_loader  # noqa: F401
from env_loader import reload_env
from trackvia_config import get_trackvia_settings, trackvia_configured, trackvia_missing_settings


class TrackViaConfigError(ValueError):
    pass


class TrackViaUserNotFoundError(LookupError):
    pass


class TrackViaApiError(ValueError):
    pass


# This will be used to require the config.
def _require_config():
    reload_env()
    if not trackvia_configured():
        missing = ", ".join(trackvia_missing_settings())
        raise TrackViaConfigError(
            f"TrackVia is not configured. Set {missing} in .env."
        )
    return get_trackvia_settings()


# This will be used to normalize the email.
def _normalize_email(email):
    return (email or "").strip().lower()



# This will be used to extract the records.
def _extract_records(payload):
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    for key in ("data", "records", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_records(value)
            if nested:
                return nested

    if payload.get("id") is not None:
        return [payload]
    return []



# This will be used to get the record id.
def _record_id(record):
    for key in ("id", "recordId", "record_id"):
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None




# This will be used to get the field value.
def _field_value(record, field_name):
    if not record or not field_name:
        return None
    if field_name in record:
        return record.get(field_name)
    lowered = field_name.lower()
    for key, value in record.items():
        if str(key).lower() == lowered:
            return value
    return None



# This will be used to extract the email from the user field.
def _extract_email_from_user_field(value):
    text = str(value or "").strip()
    if "<" in text and ">" in text:
        inner = text.split("<", 1)[1].split(">", 1)[0].strip()
        if "@" in inner:
            return _normalize_email(inner)
    if "@" in text:
        return _normalize_email(text)
    return ""



# This will be used to get the record email.
def _record_email(record, settings):
    for field_name in (
        settings["email_field"],
        "Email From Viewpoint",
        "Email",
        "User",
    ):
        value = _field_value(record, field_name)
        if value is None:
            continue
        if field_name.lower() == "user" or (
            isinstance(value, str) and "<" in value and "@" in value
        ):
            email = _extract_email_from_user_field(value)
        else:
            email = _normalize_email(value if isinstance(value, str) else str(value or ""))
        if email and "@" in email:
            return email
    return ""


# This will be used to get the status value.
def _status_value(record, settings):
    value = _field_value(record, settings["status_field"])
    if value is None:
        return ""
    return str(value).strip()


# This will be used to check if the trackvia record is disabled.
def is_trackvia_record_disabled(record, settings=None):
    settings = settings or _require_config()
    status = _status_value(record, settings).lower()
    disabled = settings["status_disabled"].strip().lower()
    if status == disabled:
        return True
    if status == (settings.get("disable_action_value") or "").strip().lower():
        return True
    if "deactivated" in status and "trackvia" in status:
        return True
    return status in {"inactive", "disabled", "no", "false", "0"}



# This will be used to make the API request.
def _api_request(method, path, *, params=None, json_body=None, timeout=30):
    settings = _require_config()
    query = dict(params or {})
    query["user_key"] = settings["api_key"]
    url = f"{settings['openapi_base_url']}/openapi{path}"
    headers = {
        "Authorization": f"Bearer {settings['access_token']}",
        "Accept": "application/json",
    }
    account_id = (settings.get("account_id") or "").strip()
    if account_id:
        headers["account-id"] = account_id
    if json_body is not None:
        headers["Content-Type"] = "application/json"

    response = requests.request(
        method,
        url,
        params=query,
        json=json_body,
        headers=headers,
        timeout=timeout,
    )

    if response.status_code == 401:
        detail = response.text
        try:
            body = response.json()
            if isinstance(body, dict):
                detail = body.get("message") or body.get("error") or detail
        except ValueError:
            pass
        raise TrackViaApiError(
            "TrackVia auth failed. "
            f"{detail} "
            "Check TRACKVIA_API_KEY, TRACKVIA_ACCESS_TOKEN, TRACKVIA_ACCOUNT_ID "
            f"(sandbox header), and API user access to view {settings['view_id']}."
        )
    if response.status_code == 403:
        raise TrackViaApiError(
            "TrackVia denied access to this view. Ensure the API user can read/write view "
            f"{settings['view_id']}."
        )
    if not response.ok:
        detail = response.text
        try:
            body = response.json()
            if isinstance(body, dict):
                detail = body.get("message") or body.get("error") or detail
        except ValueError:
            pass
        if response.status_code == 500:
            raise TrackViaApiError(f"TrackVia update failed (500). Detail: {detail}")
        raise TrackViaApiError(f"TrackVia request failed ({response.status_code}): {detail}")

    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {}



# This will be used to pick the record for the email.
def _pick_record_for_email(records, email, settings):
    normalized = _normalize_email(email)
    exact = []
    for record in records:
        record_email = _record_email(record, settings)
        if record_email == normalized:
            exact.append(record)
    if exact:
        return exact[0]
    if len(records) == 1:
        return records[0]
    return None



# This will be used to list the views.
def list_views(max_records=100):
    settings = _require_config()
    payload = _api_request(
        "GET",
        "/views",
        params={"start": 0, "max": max_records},
    )
    return _extract_records(payload)


# This will be used to find the record by email.
def find_record_by_email(email, settings=None):
    settings = settings or _require_config()
    normalized = _normalize_email(email)
    if not normalized or "@" not in normalized:
        raise ValueError("Please enter a valid email address.")

    view_id = settings["view_id"]
    payload = _api_request(
        "GET",
        f"/views/{view_id}/find",
        params={"q": normalized},
    )
    record = _pick_record_for_email(_extract_records(payload), normalized, settings)
    return record



# This will be used to check if the records endpoint is available.
def records_endpoint_available(settings=None):
    """Some sandbox API users can find rows but cannot list view records."""
    settings = settings or _require_config()
    view_id = settings["view_id"]
    try:
        _api_request(
            "GET",
            f"/views/{view_id}/records",
            params={"start": 0, "max": 1},
            timeout=20,
        )
        return True
    except TrackViaApiError:
        return False


# This will be used to get all the view records.
def get_all_view_records(settings=None, max_pages=100):
    settings = settings or _require_config()
    if not records_endpoint_available(settings):
        return []
    view_id = settings["view_id"]
    records = []
    start = 0
    page_size = 1000

    for _ in range(max_pages):
        payload = _api_request(
            "GET",
            f"/views/{view_id}/records",
            params={"start": start, "max": page_size},
        )
        page = _extract_records(payload)
        if not page:
            break
        records.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    return records


# This will be used to get the record summary.
def _record_summary(record, settings):
    return {
        "record_id": _record_id(record),
        "email": _record_email(record, settings),
        "status": _status_value(record, settings),
        "disabled": is_trackvia_record_disabled(record, settings),
    }



# This will be used to summarize the record.
def summarize_record(record, settings=None):
    settings = settings or get_trackvia_settings()
    return _record_summary(record, settings)



# This will be used to get the record by email.
def get_record_by_email(email, settings=None):
    """Return full record payload including structure when available."""
    settings = settings or _require_config()
    record = find_record_by_email(email, settings=settings)
    if not record:
        return None
    record_id = _record_id(record)
    if not record_id:
        return {"record": record, "structure": []}
    try:
        payload = _api_request(
            "GET",
            f"/views/{settings['view_id']}/records/{record_id}",
        )
        if isinstance(payload, dict):
            return {
                "record": payload.get("data") or record,
                "structure": payload.get("structure") or [],
            }
    except TrackViaApiError:
        pass
    return {"record": record, "structure": []}



# This will be used to list the record field names.
def list_record_field_names(email, settings=None):
    detail = get_record_by_email(email, settings=settings)
    if not detail:
        return None
    record = detail["record"]
    structure = detail.get("structure") or []
    fields = {}
    for key, value in sorted(record.items()):
        if str(key).endswith("(id)"):
            continue
        fields[key] = value
    schema = []
    for field in structure:
        if not isinstance(field, dict):
            continue
        schema.append({
            "name": field.get("name"),
            "type": field.get("type"),
            "canUpdate": field.get("canUpdate"),
            "choices": field.get("choices"),
        })
    return {
        "email": _record_email(record, settings or get_trackvia_settings()),
        "record_id": _record_id(record),
        "fields": fields,
        "schema": schema,
    }



# This will be used to update the record status.
def update_record_status(email, status_value):
    settings = _require_config()
    record = find_record_by_email(email, settings=settings)
    if not record:
        raise TrackViaUserNotFoundError(f"No TrackVia record found for {email}.")

    record_id = _record_id(record)
    if not record_id:
        raise TrackViaApiError("TrackVia record is missing an id field.")

    payload = _api_request(
        "PUT",
        f"/views/{settings['view_id']}/records/{record_id}",
        json_body={"data": [{settings["status_field"]: status_value}]},
    )
    updated = _extract_records(payload)
    if updated:
        record = updated[0]
    elif isinstance(payload, dict) and payload.get("id") is not None:
        record = payload
    else:
        record = dict(record)
        record[settings["status_field"]] = status_value
    return _record_summary(record, settings)


# This will be used to disable the trackvia user by email.
def disable_trackvia_user_by_email(email):
    settings = _require_config()
    return update_record_status(email, settings["disable_action_value"])



# This will be used to enable the trackvia user by email
def enable_trackvia_user_by_email(email):
    settings = _require_config()
    return update_record_status(email, settings["status_active"])



# This will be used to check the trackvia health.
def check_trackvia_health():
    settings = get_trackvia_settings()
    label = settings["label"]
    if not trackvia_configured():
        missing = ", ".join(trackvia_missing_settings())
        return {
            "ok": False,
            "configured": False,
            "label": label,
            "message": f"{label} is not configured on this server. Set {missing} in .env.",
        }

    try:
        try:
            _api_request(
                "GET",
                f"/views/{settings['view_id']}/find",
                params={"q": "healthcheck@example.com"},
                timeout=20,
            )
        except TrackViaApiError:
            _api_request("GET", "/views", params={"start": 0, "max": 1}, timeout=20)
        bulk_sync = records_endpoint_available(settings)
        return {
            "ok": True,
            "configured": True,
            "label": label,
            "message": f"{label} API connected (view {settings['view_id']}).",
            "view_id": settings["view_id"],
            "account_id": settings.get("account_id") or None,
            "openapi_base_url": settings.get("openapi_base_url"),
            "bulk_sync": bulk_sync,
        }
    except TrackViaApiError as exc:
        return {
            "ok": False,
            "configured": True,
            "label": label,
            "message": str(exc),
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "configured": True,
            "label": label,
            "message": f"TrackVia request failed: {exc}",
        }
