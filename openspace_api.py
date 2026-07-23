"""OpenSpace org admin API — lookup members and remove from organization."""

import requests

import env_loader  # noqa: F401
from env_loader import reload_env
from openspace_config import get_openspace_settings, openspace_configured, openspace_missing_settings

DELETE_USERS_PATH = "/api/v3/users/delete"
DEFAULT_MEMBERS_LIST_PATH = "/api/v3/users"
DEFAULT_MEMBERS_SEARCH_PATH = "/api/v3/users/search"


class OpenSpaceConfigError(ValueError):
    pass


class OpenSpaceUserNotFoundError(LookupError):
    pass


class OpenSpaceApiError(ValueError):
    pass


class OpenSpaceNotSupportedError(NotImplementedError):
    pass


def _require_config():
    reload_env()
    if not openspace_configured():
        missing = ", ".join(openspace_missing_settings())
        raise OpenSpaceConfigError(
            f"OpenSpace is not configured. Set {missing} in .env."
        )
    return get_openspace_settings()

# This will be used to normalize the email.
def _normalize_email(email):
    return (email or "").strip().lower()


# This will be used to get the cookie value.
def _cookie_value(cookie, key):
    for part in (cookie or "").split(";"):
        piece = part.strip()
        if piece.startswith(f"{key}="):
            return piece.split("=", 1)[1].strip()
    return ""

# This will be used to get the session headers.
def _session_headers(settings, json=False):
    cookie = settings["session_cookie"]
    headers = {
        "Cookie": cookie,
        "Accept": "application/json",
    }
    if json:
        headers["Content-Type"] = "application/json"
    xsrf = _cookie_value(cookie, "XSRF-TOKEN")
    if xsrf:
        headers["X-XSRF-TOKEN"] = xsrf
        headers["X-CSRF-TOKEN"] = xsrf
    return headers

# This will be used to extract the records.
def _extract_records(payload):
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    for key in ("users", "members", "content", "data", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_records(value)
            if nested:
                return nested
    return []

# This will be used to get the account id.
def _account_id(record):
    for key in ("accountId", "id", "userId", "account_id"):
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None

# This will be used to get the record email.
def _record_email(record):
    for key in ("email", "userEmail", "mail", "username"):
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip().lower()
        if "@" in text:
            return text
    return ""

# This will be used to handle the API error.
def _api_error(response, prefix="OpenSpace request failed"):
    detail = response.text
    try:
        body = response.json()
        if isinstance(body, dict):
            detail = body.get("message") or body.get("error") or detail
    except ValueError:
        pass
    if response.status_code in (401, 403):
        raise OpenSpaceApiError(
            f"{prefix} (HTTP {response.status_code}): {detail}. "
            "Sign in at openspace.ai as an Org Admin and refresh OPENSPACE_SESSION_COOKIE."
        )
    raise OpenSpaceApiError(f"{prefix} (HTTP {response.status_code}): {detail}")


# This will be used to make the session request.
def _session_request(settings, method, path, *, params=None, json_body=None, timeout=60):
    url = f"{settings['base_url']}{path}"
    response = requests.request(
        method,
        url,
        headers=_session_headers(settings, json=json_body is not None),
        params=params,
        json=json_body,
        timeout=timeout,
    )
    if not response.ok:
        _api_error(response)
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {}

# This will be used to get the membership via the external API.
def _membership_via_external_api(email, settings):
    api_key = settings.get("api_key")
    if not api_key:
        return None

    url = f"{settings['external_api_base_url']}/api/external/v1/reports/memberships"
    response = requests.get(
        url,
        headers={"api-key": api_key, "Accept": "application/json"},
        params={"orgs": settings["org_id"], "size": 1000, "sort": "email,ASC"},
        timeout=60,
    )
    if not response.ok:
        _api_error(response, prefix="OpenSpace Usage API lookup failed")

    target = _normalize_email(email)
    matches = []
    for record in _extract_records(response.json()):
        record_email = (record.get("userEmail") or "").strip().lower()
        if record_email == target:
            matches.append(record)

    if not matches:
        return None

    record = matches[0]
    account_id = record.get("userId") or record.get("accountId")
    return {
        "account_id": str(account_id).strip() if account_id else None,
        "email": record_email,
        "name": record.get("userFullName"),
        "role": record.get("role"),
        "source": "usage_api",
        "raw": record,
    }

# This will be used to get the members via the session list.
def _members_via_session_list(email, settings):
    org_id = settings["org_id"]
    list_path = settings.get("members_list_path") or DEFAULT_MEMBERS_LIST_PATH
    search_path = settings.get("members_search_path") or DEFAULT_MEMBERS_SEARCH_PATH
    attempts = [
        ("GET", list_path, {"orgId": org_id}),
        ("GET", list_path, {"organizationId": org_id}),
        ("POST", search_path, {"orgId": org_id, "query": email}),
        ("POST", search_path, {"orgId": org_id, "search": email}),
        ("POST", search_path, {"orgId": org_id, "searchText": email}),
        ("POST", list_path, {"orgId": org_id}),
        ("GET", f"/api/v3/organizations/{org_id}/users", None),
        ("GET", f"/api/v3/orgs/{org_id}/users", None),
    ]

    last_error = None
    target = _normalize_email(email)
    for method, path, body in attempts:
        try:
            if method == "GET":
                payload = _session_request(
                    settings,
                    "GET",
                    path,
                    params=body,
                    timeout=30,
                )
            else:
                payload = _session_request(settings, "POST", path, json_body=body, timeout=30)
        except OpenSpaceApiError as exc:
            last_error = exc
            continue

        records = _extract_records(payload)
        if method == "GET" and path in (list_path, DEFAULT_MEMBERS_LIST_PATH) and records is not None:
            for record in records:
                if _record_email(record) == target:
                    account_id = _account_id(record)
                    if not account_id:
                        continue
                    return {
                        "account_id": account_id,
                        "email": target,
                        "name": record.get("fullName") or record.get("name") or record.get("userFullName"),
                        "role": record.get("role"),
                        "source": "session_api",
                        "raw": record,
                    }
            return None

        for record in records:
            if _record_email(record) == target:
                account_id = _account_id(record)
                if not account_id:
                    continue
                return {
                    "account_id": account_id,
                    "email": target,
                    "name": record.get("fullName") or record.get("name") or record.get("userFullName"),
                    "role": record.get("role"),
                    "source": "session_api",
                    "raw": record,
                }
    if last_error:
        raise last_error
    return None


# This will be used to list the org members.
def list_org_members(settings=None):
    """Return all org members for directory sync."""
    settings = settings or _require_config()
    org_id = settings["org_id"]
    list_path = settings.get("members_list_path") or DEFAULT_MEMBERS_LIST_PATH
    attempts = [
        ("GET", list_path, {"orgId": org_id}),
        ("GET", list_path, {"organizationId": org_id}),
        ("GET", f"/api/v3/organizations/{org_id}/users", None),
        ("GET", f"/api/v3/orgs/{org_id}/users", None),
    ]
    last_error = None
    for method, path, params in attempts:
        try:
            payload = _session_request(
                settings,
                method,
                path,
                params=params,
                timeout=60,
            )
        except OpenSpaceApiError as exc:
            last_error = exc
            continue
        records = _extract_records(payload)
        if not records:
            continue
        members = []
        for record in records:
            email = _record_email(record)
            account_id = _account_id(record)
            if not email or not account_id:
                continue
            members.append({
                "email": email,
                "account_id": account_id,
                "name": record.get("fullName") or record.get("name") or record.get("userFullName"),
                "role": record.get("role"),
            })
        if members:
            return members
    if last_error:
        raise last_error
    return []

# This will be used to find the org member by email.
def find_org_member_by_email(email, settings=None):
    settings = settings or _require_config()
    normalized = _normalize_email(email)
    if not normalized or "@" not in normalized:
        raise ValueError("Please enter a valid email address.")

    member = _membership_via_external_api(normalized, settings)
    if member is None:
        member = _members_via_session_list(normalized, settings)
    return member

# This will be used to delete the org members.
def delete_org_members(account_ids, settings=None):
    settings = settings or _require_config()
    ids = [str(value).strip() for value in account_ids if str(value).strip()]
    if not ids:
        raise OpenSpaceApiError("No OpenSpace account IDs provided for delete.")

    path = settings.get("delete_path") or DELETE_USERS_PATH
    payload = {"accountIds": ids, "orgId": settings["org_id"]}
    return _session_request(settings, "POST", path, json_body=payload)

# This will be used to disable the openspace user by email.
def disable_openspace_user_by_email(email):
    member = find_org_member_by_email(email)
    if not member:
        raise OpenSpaceUserNotFoundError(f"No OpenSpace org member found for {email}.")
    if not member.get("account_id"):
        raise OpenSpaceApiError(f"OpenSpace member for {email} is missing an account id.")

    response = delete_org_members([member["account_id"]])
    return {
        "action": "delete",
        "email": member["email"],
        "account_id": member["account_id"],
        "org_id": _require_config()["org_id"],
        "name": member.get("name"),
        "role": member.get("role"),
        "source": member.get("source"),
        "response": response,
    }

# This will be used to enable the openspace user by email.
def enable_openspace_user_by_email(email):
    raise OpenSpaceNotSupportedError(
        "OpenSpace re-invite is not automated. Add the user back in OpenSpace Team Management."
    )


# This will be used to check the openspace health.
def check_openspace_health():
    settings = get_openspace_settings()
    label = settings["label"]
    if not openspace_configured():
        missing = ", ".join(openspace_missing_settings())
        return {
            "ok": False,
            "configured": False,
            "label": label,
            "message": f"{label} is not configured on this server. Set {missing} in .env.",
        }

    try:
        org_id = settings["org_id"]
        list_path = settings.get("members_list_path") or DEFAULT_MEMBERS_LIST_PATH
        probe_errors = []
        message = None
        for method, path, kwargs in (
            ("GET", f"/api/v3/organizations/{org_id}", {}),
            ("GET", DEFAULT_MEMBERS_LIST_PATH, {"params": {"orgId": org_id}}),
            ("GET", list_path, {"params": {"orgId": org_id}}),
        ):
            try:
                _session_request(settings, method, path, timeout=20, **kwargs)
                message = f"{label} connected (org {org_id})."
                break
            except OpenSpaceApiError as exc:
                probe_errors.append(str(exc))

        if not message:
            if settings.get("api_key"):
                url = f"{settings['external_api_base_url']}/api/external/v1/reports/memberships"
                response = requests.get(
                    url,
                    headers={"api-key": settings["api_key"], "Accept": "application/json"},
                    params={"orgs": org_id, "size": 1},
                    timeout=20,
                )
                if not response.ok:
                    _api_error(response, prefix="OpenSpace health check failed")
                message = f"{label} connected via Usage API (org {org_id})."
            else:
                raise OpenSpaceApiError(
                    probe_errors[-1] if probe_errors else "OpenSpace health check failed."
                )

        return {
            "ok": True,
            "configured": True,
            "label": label,
            "message": message,
            "org_id": org_id,
            "base_url": settings["base_url"],
        }
    except OpenSpaceApiError as exc:
        return {
            "ok": False,
            "configured": True,
            "label": label,
            "message": str(exc),
        }
