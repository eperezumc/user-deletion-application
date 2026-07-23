"""Symetri My Symetri API — lookup company users and remove from account."""

import base64
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

import env_loader  # noqa: F401
from env_loader import reload_env
from symetri_config import (
    DEFAULT_DELETE_PATH,
    DEFAULT_USERS_LIST_PATH,
    get_symetri_settings,
    symetri_configured,
    symetri_missing_settings,
)


class SymetriConfigError(ValueError):
    pass


class SymetriUserNotFoundError(LookupError):
    pass


class SymetriApiError(ValueError):
    pass


class SymetriNotSupportedError(NotImplementedError):
    pass


TOKEN_REFRESH_BUFFER = timedelta(minutes=10)
SYMETRI_TOKEN_HELP = (
    "Sign in at my.symetri.com as a license admin, then use Reconnect in this app "
    "or copy the Authorization bearer token into SYMETRI_BEARER_TOKEN in .env."
)

# This will be used to get the JWT payload.
def _jwt_payload(token):
    token = (token or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    padding = "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(parts[1] + padding))
    except (ValueError, json.JSONDecodeError):
        return {}

# This will be used to get the JWT expires at
def _jwt_expires_at(token):
    exp = _jwt_payload(token).get("exp")
    if not exp:
        return None
    try:
        return datetime.fromtimestamp(int(exp), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def bearer_token_expired(token, *, buffer=TOKEN_REFRESH_BUFFER):
    expires_at = _jwt_expires_at(token)
    if not expires_at:
        return False
    return datetime.now(timezone.utc) >= expires_at - buffer

# This will be used to check if the bearer token is usable
def bearer_token_usable(token):
    token = (token or "").strip()
    if not token or "." not in token:
        return False
    return not bearer_token_expired(token)

# This will be used to check the Symetri token status
def symetri_token_status(token):
    expires_at = _jwt_expires_at(token)
    if not expires_at:
        return {"expires_at": None, "expired": False}
    now = datetime.now(timezone.utc)
    return {
        "expires_at": expires_at.isoformat(),
        "expired": now >= expires_at,
        "expires_soon": bearer_token_expired(token),
    }


def _normalize_bearer_token(token):
    text = (token or "").strip()
    if text.lower().startswith("bearer "):
        text = text[7:].strip()
    return text

# This will be used to require the Symetri onfiguration.
def _require_config():
    reload_env()
    if not symetri_configured():
        missing = ", ".join(symetri_missing_settings())
        raise SymetriConfigError(
            f"Symetri is not configured. Set {missing} in .env."
        )
    return get_symetri_settings()


# This will be used to normalize the email.
def _normalize_email(email):
    return (email or "").strip().lower()


# This will be used to get the headers.
def _headers(settings, json=False):
    token = _normalize_bearer_token(settings["bearer_token"])
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "Origin": settings["web_origin"],
        "Referer": f"{settings['web_origin']}/",
        "api-supported-versions": "1",
    }
    if json:
        headers["Content-Type"] = "application/json"
    return headers


# This will be used to extract the records.
def _extract_records(payload):
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    for key in ("users", "members", "content", "data", "items", "results", "accountUsers"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_records(value)
            if nested:
                return nested
    return []


# This will be used to get the user id.
def _user_id(record):
    for key in ("userId", "id", "auth0Id", "auth0UserId", "sub"):
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


# This will be used to get the record name.
def _record_name(record):
    for key in ("fullName", "name", "displayName"):
        value = record.get(key)
        if value and str(value).strip():
            return str(value).strip()
    first = (record.get("firstName") or "").strip()
    last = (record.get("lastName") or "").strip()
    combined = f"{first} {last}".strip()
    return combined or None


# This will be used to handle the API error.
def _api_error(response, prefix="Symetri request failed"):
    detail = response.text
    try:
        body = response.json()
        if isinstance(body, dict):
            detail = body.get("message") or body.get("error") or body.get("title") or detail
    except ValueError:
        pass
    if response.status_code in (401, 403):
        raise SymetriApiError(
            f"{prefix} (HTTP {response.status_code}): authentication failed. {SYMETRI_TOKEN_HELP}"
        )
    raise SymetriApiError(f"{prefix} (HTTP {response.status_code}): {detail}")


# This will be used to make the API request.
def _api_request(settings, method, path, *, params=None, json_body=None, timeout=60):
    url = f"{settings['api_base_url']}{path}"
    response = requests.request(
        method,
        url,
        headers=_headers(settings, json=json_body is not None),
        params=params,
        json=json_body,
        timeout=timeout,
    )
    if not response.ok and response.status_code != 204:
        _api_error(response)
    if response.status_code == 204 or not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {}


# This will be used to get the users list path.
def _users_list_path(settings):
    template = settings.get("users_list_path") or DEFAULT_USERS_LIST_PATH
    return template.format(account_id=settings["account_id"])


# This will be used to get the delete user path.
def _delete_user_path(settings, user_id):
    template = settings.get("delete_path") or DEFAULT_DELETE_PATH
    return template.format(
        account_id=settings["account_id"],
        user_id=quote(user_id, safe=""),
    )


# This will be used to list the account users.
def _list_account_users(settings):
    path = _users_list_path(settings)
    payload = _api_request(settings, "GET", path, timeout=30)
    records = _extract_records(payload)
    if records:
        return records
    if isinstance(payload, list):
        return payload
    return []


# This will be used to list the Symetri users for sync.
def list_symetri_users_for_sync(settings=None):
    """Return summarized Symetri account users for directory sync."""
    settings = settings or _require_config()
    members = []
    for record in _list_account_users(settings):
        email = _record_email(record)
        user_id = _user_id(record)
        if not email or not user_id:
            continue
        members.append({
            "email": email,
            "user_id": user_id,
            "name": _record_name(record),
            "account_id": settings["account_id"],
        })
    return members


# This will be used to find the account user by email.
def find_account_user_by_email(email, settings=None):
    settings = settings or _require_config()
    normalized = _normalize_email(email)
    if not normalized or "@" not in normalized:
        raise ValueError("Please enter a valid email address.")

    for record in _list_account_users(settings):
        if _record_email(record) != normalized:
            continue
        user_id = _user_id(record)
        if not user_id:
            continue
        return {
            "user_id": user_id,
            "email": normalized,
            "name": _record_name(record),
            "account_id": settings["account_id"],
            "raw": record,
        }
    return None


def delete_account_user(user_id, settings=None):
    settings = settings or _require_config()
    user_id = (user_id or "").strip()
    if not user_id:
        raise SymetriApiError("No Symetri user id provided for delete.")

    path = _delete_user_path(settings, user_id)
    return _api_request(settings, "DELETE", path, timeout=60)


def remove_symetri_user_by_email(email):
    member = find_account_user_by_email(email)
    if not member:
        raise SymetriUserNotFoundError(f"No Symetri account user found for {email}.")
    if not member.get("user_id"):
        raise SymetriApiError(f"Symetri user for {email} is missing a user id.")

    response = delete_account_user(member["user_id"])
    return {
        "action": "delete",
        "email": member["email"],
        "user_id": member["user_id"],
        "account_id": member["account_id"],
        "name": member.get("name"),
        "response": response,
    }


def enable_symetri_user_by_email(email):
    raise SymetriNotSupportedError(
        "Symetri re-invite is not automated. Add the user back in My Symetri."
    )


def check_symetri_health():
    settings = get_symetri_settings()
    label = settings["label"]
    if not symetri_configured():
        missing = ", ".join(symetri_missing_settings())
        return {
            "ok": False,
            "configured": False,
            "label": label,
            "message": f"{label} is not configured on this server. Set {missing} in .env.",
        }

    token_status = symetri_token_status(settings["bearer_token"])
    if token_status.get("expired"):
        return {
            "ok": False,
            "configured": True,
            "label": label,
            "token_expired": True,
            "token_expires_at": token_status.get("expires_at"),
            "message": f"{label} bearer token expired. {SYMETRI_TOKEN_HELP}",
            "reconnect_hint": (
                "Symetri bearer token expired (about every 48 hours). "
                "Click Reconnect — a separate browser window opens; sign in there (not this tab)."
            ),
        }

    try:
        users = _list_account_users(settings)
        message = f"{label} connected (account {settings['account_id']}, {len(users)} users)."
        payload = {
            "ok": True,
            "configured": True,
            "label": label,
            "message": message,
            "account_id": settings["account_id"],
            "user_count": len(users),
            "api_base_url": settings["api_base_url"],
        }
        if token_status.get("expires_at"):
            payload["token_expires_at"] = token_status["expires_at"]
        return payload
    except SymetriApiError as exc:
        message = str(exc)
        token_expired = "authentication failed" in message.lower()
        return {
            "ok": False,
            "configured": True,
            "label": label,
            "token_expired": token_expired,
            "message": message,
            "reconnect_hint": (
                "Symetri session is invalid. Click Reconnect to sign in at my.symetri.com, "
                "or update SYMETRI_BEARER_TOKEN in .env from DevTools."
            ) if token_expired else None,
        }
