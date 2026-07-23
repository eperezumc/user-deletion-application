"""Revizto API helpers — OAuth token exchange, refresh, and license lookups."""

import base64
import json
import os
import re
import secrets
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import env_loader  # noqa: F401
import requests

from env_loader import PROJECT_ROOT, env_value, reload_env, set_env_key, set_env_keys
from revizto_token_store import hydrate_revizto_env, save_tokens as save_local_revizto_tokens

BASE_URL = os.getenv("REVIZTO_BASE_URL", "https://api.virginia.revizto.com").rstrip("/")
WORKSPACE_URL = os.getenv("REVIZTO_WORKSPACE_URL", "https://ws.revizto.com").rstrip("/")
TOKEN_URL = f"{BASE_URL}/v5/oauth2"
ENV_PATH = PROJECT_ROOT / ".env"
REFRESH_LOCK_PATH = PROJECT_ROOT / ".revizto_refresh.lock"
TOKEN_REFRESH_BUFFER = timedelta(minutes=15)
_refresh_lock = threading.Lock()
_last_failed_bootstrap_code = ""
ACCESS_CODE_PATTERN = re.compile(r"def50200[a-zA-Z0-9%]{80,}")


@contextmanager
def _refresh_file_lock():
    """Serialize OAuth refresh across app.py and CLI processes (single-use refresh tokens)."""
    REFRESH_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = open(REFRESH_LOCK_PATH, "a+")
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        handle.close()

AUTH_ERROR_HINTS = {
    -10: (
        "The access code is invalid, expired, or already used. "
        "Codes last 15 minutes and are single-use. "
        "Get a new one from Revizto Workspace -> My Account -> Active Sessions -> API."
    ),
    -20: (
        "Token invalid or already used (Revizto also returns -20 for a stale access code). "
        "If refresh works, run: python revisto_api.py --refresh. "
        "Otherwise get a new access code and run: python revisto_api.py --exchange"
    ),
    -204: "Your license may not include API access, or the token is not allowed.",
    -205: "Token region mismatch. Use an access code from the same region as REVIZTO_BASE_URL.",
    -206: "The access token expired. Refresh or exchange a new access code.",
}


class ReviztoAuthError(ValueError):
    pass


class ReviztoUserNotFoundError(LookupError):
    pass


class ReviztoApiError(ValueError):
    pass


def _refresh_token_value():
    """Long-lived refresh credential (Revizto calls it refresh token; .env key is REVIZTO_REFRESH_CODE)."""
    return env_value("REVIZTO_REFRESH_CODE") or env_value("REVIZTO_REFRESH_TOKEN")


def _token_response_refresh(data):
    """Revizto may return refresh_token or refresh_code depending on endpoint/version."""
    return data.get("refresh_token") or data.get("refresh_code") or ""


def _revizto_manual_setup_warning():
    """Warn when the access-code field contains a refresh token copy."""
    code = env_value("REVIZTO_ACCESS_CODE")
    if not code:
        return None
    refresh = _refresh_token_value()
    if refresh and code == refresh:
        return (
            "REVIZTO_ACCESS_CODE has your refresh code, not the access code. "
            "In Revizto use Active Sessions -> API and copy the access code only. "
            "Do not paste REVIZTO_REFRESH_CODE into REVIZTO_ACCESS_CODE."
        )
    if refresh and code.startswith("def50200") and code[:32] == refresh[:32]:
        return (
            "REVIZTO_ACCESS_CODE looks like a refresh code. "
            "Copy the access code from Revizto Active Sessions -> API instead."
        )
    return None


def revizto_auth_help(exc=None):
    """Actionable setup hint for UI/CLI when OAuth fails."""
    mismatch = _revizto_manual_setup_warning()
    if mismatch:
        return mismatch
    message = str(exc or "").lower()
    if "entity not found" in message or ("result=-10" in message and "user" in message):
        return (
            "Revizto says that code is not a valid access code ('User token' not found). "
            "In Active Sessions -> API, Revizto often shows TWO values — try the other one, "
            "or put the refresh code in REVIZTO_REFRESH_CODE instead."
        )
    if env_value("REVIZTO_ACCESS_CODE") and ("result=-10" in message or "result=-20" in message):
        return (
            "Revizto rejected REVIZTO_ACCESS_CODE (expired, already used, or wrong value). "
            "Get a fresh code from Active Sessions -> API and update REVIZTO_ACCESS_CODE in .env."
        )
    if "result=-20" in message or "refresh token" in message:
        return (
            "Revizto refresh token expired. "
            "Get a new access code from Active Sessions -> API, put it in REVIZTO_ACCESS_CODE in .env "
            "(the app exchanges it automatically within ~20 seconds)."
        )
    if "http 500" in message or "internal server error" in message:
        return (
            "Revizto rejected a corrupt refresh token in .env. "
            "Get a fresh access code from Active Sessions -> API, set REVIZTO_ACCESS_CODE, "
            "and restart the app."
        )
    return (
        "Revizto OAuth failed. In Revizto go to Active Sessions -> API, copy the "
        "access code into REVIZTO_ACCESS_CODE only. "
        "The app saves REVIZTO_ACCESS_TOKEN and REVIZTO_REFRESH_CODE for you."
    )


def _jwt_expires_at(access_token):
    try:
        payload_b64 = access_token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp, tz=timezone.utc)
    except (IndexError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


def _access_token_expired(access_token=None):
    access_token = access_token or env_value("REVIZTO_ACCESS_TOKEN")
    if not access_token:
        return True

    jwt_exp = _jwt_expires_at(access_token)
    expires_at_dt = None
    expires_at = env_value("REVIZTO_ACCESS_TOKEN_EXPIRES_AT")
    if expires_at:
        try:
            expires_at_dt = datetime.fromisoformat(expires_at)
        except ValueError:
            pass

    # .env expiry can be stale after a manual paste; trust the JWT when it is newer.
    if jwt_exp and expires_at_dt and jwt_exp > expires_at_dt + timedelta(minutes=1):
        return datetime.now(timezone.utc) >= jwt_exp - TOKEN_REFRESH_BUFFER

    if expires_at_dt:
        return datetime.now(timezone.utc) >= expires_at_dt - TOKEN_REFRESH_BUFFER

    if jwt_exp:
        return datetime.now(timezone.utc) >= jwt_exp - TOKEN_REFRESH_BUFFER

    return False


def _save_tokens(access_token, refresh_token, expires_in=None, *, clear_access_code=False):
    os.environ["REVIZTO_ACCESS_TOKEN"] = access_token
    os.environ["REVIZTO_REFRESH_CODE"] = refresh_token
    os.environ.pop("REVIZTO_REFRESH_TOKEN", None)

    seconds = int(expires_in or 3600)
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=seconds - 60)).isoformat()
    os.environ["REVIZTO_ACCESS_TOKEN_EXPIRES_AT"] = expires_at

    updated_at = datetime.now(timezone.utc).isoformat()
    os.environ["REVIZTO_TOKENS_UPDATED_AT"] = updated_at

    save_local_revizto_tokens(
        access_token,
        refresh_token,
        expires_at,
        tokens_updated_at=updated_at,
    )

    updates = {
        "REVIZTO_ACCESS_TOKEN": access_token,
        "REVIZTO_REFRESH_CODE": refresh_token,
        "REVIZTO_REFRESH_TOKEN": "",
        "REVIZTO_ACCESS_TOKEN_EXPIRES_AT": expires_at,
        "REVIZTO_TOKENS_UPDATED_AT": updated_at,
    }
    if clear_access_code:
        os.environ.pop("REVIZTO_ACCESS_CODE", None)
        updates["REVIZTO_ACCESS_CODE"] = ""
    try:
        set_env_keys(updates)
    except OSError as exc:
        print(
            "Revizto: saved tokens to local cache; .env update failed "
            f"({exc}). OAuth will keep working from local cache.",
            flush=True,
        )


def _auth_error(body, http_status=None):
    code = body.get("result")
    message = body.get("message") or "Revizto authentication failed"
    hint = AUTH_ERROR_HINTS.get(code, "")
    detail = f"Revizto auth failed"
    if http_status is not None:
        detail += f" (HTTP {http_status}, result={code})"
    else:
        detail += f" (result={code})"
    detail += f": {message}"
    if hint:
        detail += f" {hint}"
    return ReviztoAuthError(detail)


def _normalize_token_response(data, http_status=None):
    if not isinstance(data, dict):
        raise ReviztoAuthError("Unexpected Revizto auth response")

    if data.get("result") not in (None, 0):
        raise _auth_error(data, http_status=http_status)

    if data.get("access_token"):
        if not _token_response_refresh(data):
            raise ReviztoAuthError("Revizto response missing refresh_token")
        return data

    inner = data.get("data")
    if isinstance(inner, dict) and inner.get("access_token"):
        if not _token_response_refresh(inner):
            raise ReviztoAuthError("Revizto response missing refresh_token")
        return inner

    raise ReviztoAuthError("Revizto response missing access_token")


def _http_auth_error(response):
    snippet = (response.text or "").replace("\n", " ").strip()[:200]
    return ReviztoAuthError(
        f"Revizto auth HTTP {response.status_code}"
        f"{f': {snippet}' if snippet else ''}"
    )


def _parse_token_response(response):
    try:
        body = response.json()
    except ValueError as exc:
        if response.status_code >= 400:
            raise _http_auth_error(response) from exc
        raise ReviztoAuthError("Revizto returned a non-JSON auth response") from exc

    if response.status_code >= 400:
        if isinstance(body, dict) and body.get("result") is not None:
            raise _auth_error(body, http_status=response.status_code)
        raise _http_auth_error(response)

    return _normalize_token_response(body, http_status=response.status_code)


def extract_access_code_from_payload(payload):
    """Find a Revizto API access code in JSON or text payloads."""
    if payload is None:
        return None
    if isinstance(payload, str):
        match = ACCESS_CODE_PATTERN.search(payload)
        return match.group(0) if match else None
    if isinstance(payload, dict):
        for key in ("code", "access_code", "accessCode", "user_token", "token"):
            value = payload.get(key)
            if isinstance(value, str) and ACCESS_CODE_PATTERN.fullmatch(value.strip()):
                return value.strip()
            found = extract_access_code_from_payload(value)
            if found:
                return found
        for value in payload.values():
            found = extract_access_code_from_payload(value)
            if found:
                return found
        return None
    if isinstance(payload, list):
        for item in payload:
            found = extract_access_code_from_payload(item)
            if found:
                return found
    return None


def _workspace_session_headers(cookie):
    return {
        "Cookie": cookie,
        "Accept": "application/json, text/plain, */*",
    }


def request_revizto_access_code(session_cookie=None):
    """
    Request a fresh Revizto API access code using a signed-in workspace session cookie.
    Revizto shows the same code under My Account -> Active Sessions -> API.
    """
    cookie = (session_cookie or _session_cookie()).strip()
    if not revizto_session_cookie_usable(cookie):
        raise ReviztoAuthError(
            "Revizto workspace session is incomplete. "
            "Sign in at ws.revizto.com in the Playwright browser window opened by Reconnect."
        )

    device_id = _cookie_value(cookie, "w_device_id") or _device_id()
    headers = _workspace_session_headers(cookie)
    form = {"Version": "v5", "device_id": device_id}
    params = {"Version": "v5", "device_id": device_id}
    attempts = [
        ("GET", f"{WORKSPACE_URL}/v5/user/access_code", params),
        ("POST", f"{WORKSPACE_URL}/v5/user/access_code", form),
        ("GET", f"{WORKSPACE_URL}/api/v5/user/access_code", params),
        ("POST", f"{WORKSPACE_URL}/api/v5/user/access_code", form),
        ("POST", f"{BASE_URL}/v5/user/access_code", form),
        ("GET", f"{BASE_URL}/v5/user/access_code", params),
        ("POST", f"{BASE_URL}/v5/oauth2/access_code", form),
        ("GET", f"{BASE_URL}/v5/oauth2/access_code", params),
        ("POST", TOKEN_URL, {**form, "grant_type": "create_access_code"}),
        ("GET", TOKEN_URL, {**params, "create": "1"}),
    ]

    last_error = None
    for method, url, payload in attempts:
        try:
            if method == "POST":
                response = requests.post(url, headers=headers, data=payload, timeout=30)
            else:
                response = requests.get(url, headers=headers, params=payload, timeout=30)
            if response.status_code >= 400:
                continue
            try:
                body = response.json()
            except ValueError:
                body = response.text
            code = extract_access_code_from_payload(body)
            if code:
                return code
        except requests.RequestException as exc:
            last_error = exc
            continue

    detail = f" Last error: {last_error}" if last_error else ""
    raise ReviztoAuthError(
        "Could not request a Revizto API access code from the workspace session."
        f"{detail} Open My Account -> Active Sessions -> API in the Playwright window."
    )


def reconnect_revizto_from_session(session_cookie, access_code=None):
    """
    Save workspace cookie, obtain a fresh API access code, exchange for OAuth tokens.
    """
    cookie = (session_cookie or "").strip()
    if not cookie:
        raise ReviztoAuthError("Revizto session cookie is empty.")

    os.environ["REVIZTO_SESSION_COOKIE"] = cookie
    set_env_key("REVIZTO_SESSION_COOKIE", cookie)

    code = (access_code or "").strip() or request_revizto_access_code(cookie)
    exchange_access_code(code)

    licenses = get_current_user_licenses()
    license_name = licenses[0].get("name") if licenses else "license"
    return {
        "platform": "revizto",
        "env_var": "REVIZTO_SESSION_COOKIE",
        "message": f"Revizto connected ({license_name}).",
    }


def _optional_oauth_fields():
    fields = {}
    client_id = (os.getenv("REVIZTO_CLIENT_ID") or "").strip()
    redirect_uri = (os.getenv("REVIZTO_REDIRECT_URI") or "").strip()
    if client_id:
        fields["client_id"] = client_id
    if redirect_uri:
        fields["redirect_uri"] = redirect_uri
    return fields


def exchange_access_code(code=None):
    """
    One-time exchange: access code (15 min lifetime) -> access + refresh tokens.
    Get a new code from Revizto Workspace -> My Account -> Active Sessions -> API.
    """
    reload_env()
    code = (code or env_value("REVIZTO_ACCESS_CODE") or "").strip()
    if not code:
        raise ReviztoAuthError("REVIZTO_ACCESS_CODE is missing.")

    mismatch = _revizto_manual_setup_warning()
    if mismatch:
        raise ReviztoAuthError(mismatch)

    payload = {"grant_type": "authorization_code", "code": code, **_optional_oauth_fields()}
    response = requests.post(TOKEN_URL, data=payload, timeout=30)
    if response.status_code >= 400:
        response = requests.get(TOKEN_URL, params={"code": code}, timeout=30)

    data = _parse_token_response(response)
    refresh_token = _token_response_refresh(data)
    _save_tokens(
        data["access_token"],
        refresh_token,
        data.get("expires_in"),
        clear_access_code=True,
    )
    return data["access_token"], refresh_token


def _clear_pending_access_code():
    os.environ.pop("REVIZTO_ACCESS_CODE", None)
    set_env_key("REVIZTO_ACCESS_CODE", "")


def _bootstrap_pending_code(code):
    """
    Turn a pasted Revizto code into saved API tokens.
    Tries access-code exchange first, then refresh grant (users often paste the wrong one).
    """
    global _last_failed_bootstrap_code

    mismatch = _revizto_manual_setup_warning()
    if mismatch:
        raise ReviztoAuthError(mismatch)

    try:
        result = exchange_access_code(code)
        _last_failed_bootstrap_code = ""
        return result
    except ReviztoAuthError as exchange_error:
        message = str(exchange_error).lower()
        if "result=-10" not in message and "entity not found" not in message:
            _last_failed_bootstrap_code = code
            raise

        try:
            access_token, refresh_token = refresh_revizto_tokens(code)
            _clear_pending_access_code()
            _last_failed_bootstrap_code = ""
            print(
                "Revizto: pasted value worked as a refresh code -> saved tokens to .env",
                flush=True,
            )
            return access_token, refresh_token
        except ReviztoAuthError as refresh_error:
            _last_failed_bootstrap_code = code
            raise ReviztoAuthError(
                f"{exchange_error} Also tried as refresh code: {refresh_error}"
            ) from refresh_error


def _reconcile_refresh_tokens():
    """Legacy: drop duplicate REVIZTO_REFRESH_TOKEN when it disagrees with REFRESH_CODE."""
    code = env_value("REVIZTO_REFRESH_CODE")
    token = env_value("REVIZTO_REFRESH_TOKEN")
    if code and token and code != token:
        set_env_key("REVIZTO_REFRESH_TOKEN", "")
        os.environ.pop("REVIZTO_REFRESH_TOKEN", None)


def _refresh_token_candidates(explicit=None):
    if explicit:
        return [explicit.strip()]

    _reconcile_refresh_tokens()
    code = env_value("REVIZTO_REFRESH_CODE")
    if code:
        return [code]
    token = env_value("REVIZTO_REFRESH_TOKEN")
    return [token] if token else []


def refresh_revizto_tokens(refresh_token=None):
    """
    Get a new access token using the refresh token.
    Revizto returns a new refresh token too — the old one stops working.
    """
    candidates = _refresh_token_candidates(refresh_token)
    if not candidates:
        raise ReviztoAuthError(
            "REVIZTO_REFRESH_TOKEN is missing. "
            "Put a fresh REVIZTO_ACCESS_CODE in .env and run: python revisto_api.py --exchange"
        )

    last_error = None
    for candidate in candidates:
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": candidate,
            **_optional_oauth_fields(),
        }
        try:
            response = requests.post(TOKEN_URL, data=payload, timeout=30)
            data = _parse_token_response(response)
        except (ReviztoAuthError, requests.RequestException) as exc:
            last_error = exc if isinstance(exc, ReviztoAuthError) else ReviztoAuthError(str(exc))
            if len(candidates) > 1:
                continue
            raise last_error from exc

        _save_tokens(data["access_token"], _token_response_refresh(data), data.get("expires_in"))
        return data["access_token"], _token_response_refresh(data)

    raise last_error


def _clear_stale_access_code():
    _clear_pending_access_code()


def _renew_tokens_locked():
    """Exchange a pending bootstrap code or refresh using the saved refresh code."""
    code = env_value("REVIZTO_ACCESS_CODE")
    if code:
        access_token, _refresh_token = _bootstrap_pending_code(code)
        if env_value("REVIZTO_ACCESS_CODE"):
            print(
                "Revizto: exchanged access code -> saved access + refresh tokens to .env",
                flush=True,
            )
        return access_token

    access_token, _refresh_token = refresh_revizto_tokens()
    print("Revizto: refreshed access token in .env", flush=True)
    return access_token


def get_revizto_access_token(*, allow_refresh=True):
    """
    Return a valid access token.
    Pending REVIZTO_ACCESS_CODE is exchanged only when there is no valid JWT yet.
    When allow_refresh is False (health checks), never calls the refresh endpoint.
    """
    reload_env()
    hydrate_revizto_env()

    access_token = env_value("REVIZTO_ACCESS_TOKEN")
    if access_token and not _access_token_expired(access_token):
        if env_value("REVIZTO_ACCESS_CODE"):
            _clear_stale_access_code()
        return access_token

    pending_code = env_value("REVIZTO_ACCESS_CODE")
    if pending_code:
        if not allow_refresh and pending_code == _last_failed_bootstrap_code:
            raise ReviztoAuthError(
                "Revizto access token expired and the pending REVIZTO_ACCESS_CODE was "
                "already rejected. Paste a fresh code in .env."
            )
        with _refresh_lock:
            with _refresh_file_lock():
                reload_env()
                access_token = env_value("REVIZTO_ACCESS_TOKEN")
                if access_token and not _access_token_expired(access_token):
                    _clear_stale_access_code()
                    return access_token
                if env_value("REVIZTO_ACCESS_CODE"):
                    return _renew_tokens_locked()

    if not allow_refresh:
        raise ReviztoAuthError(
            "Revizto access token expired. Waiting for background refresh or a new "
            "REVIZTO_ACCESS_CODE in .env."
        )

    with _refresh_lock:
        with _refresh_file_lock():
            reload_env()
            access_token = env_value("REVIZTO_ACCESS_TOKEN")
            if access_token and not _access_token_expired(access_token):
                return access_token
            return _renew_tokens_locked()


def bootstrap_revizto_oauth(access_code=None):
    """Persist an access code (optional) and exchange it for API tokens."""
    if access_code:
        access_code = access_code.strip()
        if not access_code:
            raise ReviztoAuthError("access_code is empty.")
        set_env_key("REVIZTO_ACCESS_CODE", access_code)
        os.environ["REVIZTO_ACCESS_CODE"] = access_code
    reload_env()
    token = get_revizto_access_token()
    return token, env_value("REVIZTO_REFRESH_CODE") or ""


def maintain_revizto_tokens():
    """Refresh OAuth tokens before they expire. Only the background keeper should call this."""
    global _last_failed_bootstrap_code

    if not revizto_configured():
        return None
    reload_env()
    hydrate_revizto_env()

    access_token = env_value("REVIZTO_ACCESS_TOKEN")
    if access_token and not _access_token_expired(access_token):
        if env_value("REVIZTO_ACCESS_CODE"):
            _clear_stale_access_code()
        return access_token

    pending = env_value("REVIZTO_ACCESS_CODE")
    if pending and pending == _last_failed_bootstrap_code:
        return None
    if pending:
        return get_revizto_access_token(allow_refresh=True)

    with _refresh_lock:
        with _refresh_file_lock():
            reload_env()
            access_token = env_value("REVIZTO_ACCESS_TOKEN")
            if access_token and not _access_token_expired(access_token):
                return access_token
            return _renew_tokens_locked()


def _bearer_headers():
    return {"Authorization": f"Bearer {get_revizto_access_token()}"}


def _session_cookie():
    return env_value("REVIZTO_SESSION_COOKIE")


def _cookie_value(cookie, key):
    for part in cookie.split(";"):
        piece = part.strip()
        if piece.startswith(f"{key}="):
            return piece.split("=", 1)[1].strip()
    return ""


def _cookie_has_name_prefix(cookie, prefix):
    for part in cookie.split(";"):
        name = part.strip().split("=", 1)[0]
        if name.startswith(prefix):
            return True
    return False


def revizto_session_cookie_usable(cookie_header):
    """
    True when the cookie header looks like a completed Revizto workspace sign-in.

    Revizto sets anonymous cookies (device id, region, etc.) before login. We require
    markers that only appear after authentication, not just w_key or ssoKey alone.
    """
    cookie = (cookie_header or "").strip()
    if not cookie:
        return False
    if not _cookie_value(cookie, "w_key"):
        return False
    if not _cookie_value(cookie, "ssoKey"):
        return False
    if _cookie_value(cookie, "lastAuth") != "login":
        return False
    if not _cookie_has_name_prefix(cookie, "currentAccountUuid_"):
        return False
    return True


def _revizto_headers(json=False, require_cookie=False):
    headers = _bearer_headers()
    cookie = _session_cookie()
    if cookie:
        headers["Cookie"] = cookie
    elif require_cookie:
        raise ReviztoApiError(
            "REVIZTO_SESSION_COOKIE is not configured. "
            "Log into ws.revizto.com, copy the Cookie header from DevTools, and add it to .env."
        )
    if json:
        headers["Content-Type"] = "application/json"
    return headers


def _auth_headers():
    return _revizto_headers(json=True)


def _device_id():
    device_id = (os.getenv("REVIZTO_DEVICE_ID") or "").strip()
    if device_id:
        return device_id

    cookie = _session_cookie()
    if cookie:
        device_id = _cookie_value(cookie, "w_device_id")
        if device_id:
            return device_id

    device_id = secrets.token_urlsafe(12)[:16]
    os.environ["REVIZTO_DEVICE_ID"] = device_id
    set_env_key("REVIZTO_DEVICE_ID", device_id)
    return device_id


def _new_operation_id():
    return secrets.token_hex(20)


def _license_id(license_record):
    license_id = license_record.get("id")
    if license_id is None:
        raise ReviztoApiError("Revizto license is missing numeric id.")
    return license_id



def get_default_license():
    license_id_override = (os.getenv("REVIZTO_LICENSE_ID") or "").strip()
    licenses = get_current_user_licenses()
    if not licenses:
        raise ReviztoApiError("No Revizto licenses found for this account.")

    if license_id_override:
        for license_record in licenses:
            if str(license_record.get("id")) == license_id_override:
                return license_record
        raise ReviztoApiError(
            f"REVIZTO_LICENSE_ID={license_id_override} was not found for this account."
        )

    return licenses[0]


def revizto_configured():
    hydrate_revizto_env()
    return bool(
        env_value("REVIZTO_ACCESS_TOKEN")
        or _refresh_token_value()
        or env_value("REVIZTO_ACCESS_CODE")
    )


def revizto_member_actions_ready():
    """Activate/deactivate need OAuth token plus workspace session cookie."""
    return revizto_configured() and bool(_session_cookie())


def _member_action_form(member_uuids, operation_id=None):
    form = {
        "Version": "v5",
        "device_id": _device_id(),
        "operationId": operation_id or _new_operation_id(),
    }
    for index, member_uuid in enumerate(member_uuids):
        form[f"uuids[{index}]"] = member_uuid
    return form



def _parse_api_response(response):
    response.raise_for_status()
    try:
        body = response.json()
    except ValueError as exc:
        raise ReviztoApiError(
            f"Revizto returned non-JSON (HTTP {response.status_code})."
        ) from exc

    if isinstance(body, dict) and body.get("result") not in (None, 0):
        raise ReviztoApiError(
            body.get("message") or f"Revizto API error (result={body.get('result')})"
        )
    return body


def _api_post_form(path, form_data):
    response = requests.post(
        f"{BASE_URL}{path}",
        headers=_revizto_headers(require_cookie=True),
        data=form_data,
        timeout=60,
    )
    return _parse_api_response(response)


def _api_post(path):
    response = requests.post(f"{BASE_URL}{path}", headers=_auth_headers(), timeout=60)
    return _parse_api_response(response)


def _api_get(path, params=None):
    response = requests.get(
        f"{BASE_URL}{path}",
        headers=_auth_headers(),
        params=params or {},
        timeout=60,
    )
    return _parse_api_response(response)


def _member_summary(member):
    user = member.get("user") or {}
    license_info = member.get("license") or {}
    return {
        "member_uuid": member.get("uuid"),
        "user_uuid": user.get("uuid"),
        "email": user.get("email"),
        "name": user.get("fullname") or f"{user.get('firstname', '')} {user.get('lastname', '')}".strip(),
        "role": member.get("role"),
        "status": member.get("status"),
        "deactivated": member.get("deactivated"),
        "license_uuid": license_info.get("uuid"),
        "license_name": license_info.get("name"),
    }


def get_current_user_licenses():
    body = _api_get("/v5/user/licenses")
    return body["data"]["entities"]


def get_current_user_license_uuid():
    return get_default_license()["uuid"]


def activate_license_members(member_uuids, license_record=None, operation_id=None):
    license_record = license_record or get_default_license()
    form = _member_action_form(member_uuids, operation_id=operation_id)
    body = _api_post_form(
        f"/v5/license/{_license_id(license_record)}/activate",
        form,
    )
    return {
        "action": "activate",
        "license_id": _license_id(license_record),
        "license_uuid": license_record.get("uuid"),
        "member_uuids": list(member_uuids),
        "operation_id": form["operationId"],
        "response": body,
    }


def deactivate_license_members(member_uuids, license_record=None, operation_id=None):
    license_record = license_record or get_default_license()
    form = _member_action_form(member_uuids, operation_id=operation_id)
    body = _api_post_form(
        f"/v5/license/{_license_id(license_record)}/deactivate",
        form,
    )
    return {
        "action": "deactivate",
        "license_id": _license_id(license_record),
        "license_uuid": license_record.get("uuid"),
        "member_uuids": list(member_uuids),
        "operation_id": form["operationId"],
        "response": body,
    }


def activate_revizto_user_by_email(email, license_record=None):
    license_record = license_record or get_default_license()
    member = find_license_member_by_email(license_record["uuid"], email)
    if not member:
        raise ReviztoUserNotFoundError(f"No Revizto license member found for {email}.")
    result = activate_license_members([member["member_uuid"]], license_record=license_record)
    result["email"] = email
    result["member"] = member
    return result


def deactivate_revizto_user_by_email(email, license_record=None):
    license_record = license_record or get_default_license()
    member = find_license_member_by_email(license_record["uuid"], email)
    if not member:
        raise ReviztoUserNotFoundError(f"No Revizto license member found for {email}.")
    result = deactivate_license_members([member["member_uuid"]], license_record=license_record)
    result["email"] = email
    result["member"] = member
    return result


def get_license_team_members(license_uuid, with_deactivated=False):
    params = {"withDeactivated": "1"} if with_deactivated else None
    body = _api_get(f"/v5/license/{license_uuid}/team", params=params)
    return body["data"]["entities"]


def find_license_member_by_email(license_uuid, email, with_deactivated=True):
    target = email.strip().lower()
    for member in get_license_team_members(license_uuid, with_deactivated=with_deactivated):
        user = member.get("user") or {}
        if (user.get("email") or "").strip().lower() == target:
            return _member_summary(member)
    return None


def get_specific_license_member(license_uuid, email):
    """Find a license team member by email. Returns their member UUID (for disable/remove APIs)."""
    member = find_license_member_by_email(license_uuid, email)
    return member["member_uuid"] if member else None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Revizto token utilities")
    parser.add_argument(
        "--exchange",
        action="store_true",
        help="Exchange REVIZTO_ACCESS_CODE for tokens (first-time setup)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force refresh using REVIZTO_REFRESH_TOKEN",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show whether cached access/refresh tokens look usable",
    )
    parser.add_argument(
        "--licenses",
        action="store_true",
        help="List licenses visible to the current Revizto account",
    )
    parser.add_argument(
        "--lookup",
        metavar="EMAIL",
        help="Find a license team member by email (uses your first license)",
    )
    parser.add_argument(
        "--activate",
        metavar="EMAIL",
        help="Activate a license member by email",
    )
    parser.add_argument(
        "--deactivate",
        metavar="EMAIL",
        help="Deactivate a license member by email",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --activate/--deactivate, print the request without sending it",
    )
    args = parser.parse_args()

    if args.licenses:
        for lic in get_current_user_licenses():
            print(f"id={lic.get('id')}  uuid={lic.get('uuid')}  {lic.get('name')}")
    elif args.lookup:
        license_uuid = get_current_user_license_uuid()
        member = find_license_member_by_email(license_uuid, args.lookup)
        if not member:
            print(f"No member found for {args.lookup!r} in license {license_uuid}")
        else:
            for key, value in member.items():
                print(f"{key}: {value}")
    elif args.activate or args.deactivate:
        email = args.activate or args.deactivate
        license_record = get_default_license()
        member = find_license_member_by_email(license_record["uuid"], email)
        if not member:
            print(f"No member found for {email!r}")
            raise SystemExit(1)

        action = "activate" if args.activate else "deactivate"
        form = _member_action_form([member["member_uuid"]])
        url = f"{BASE_URL}/v5/license/{_license_id(license_record)}/{action}"
        print(f"url: {url}")
        for key, value in form.items():
            print(f"{key}: {value}")
        print(f"member: {member['name']} <{member['email']}>")
        print(f"cookie configured: {bool(_session_cookie())}")

        if args.dry_run:
            print("dry-run: request not sent")
        elif args.activate:
            result = activate_revizto_user_by_email(email, license_record=license_record)
            print("activate ok")
            print(f"operation_id: {result['operation_id']}")
        else:
            result = deactivate_revizto_user_by_email(email, license_record=license_record)
            print("deactivate ok")
            print(f"operation_id: {result['operation_id']}")
    elif args.status:
        access = (os.getenv("REVIZTO_ACCESS_TOKEN") or "").strip()
        refresh = _refresh_token_value()
        print(f"access token present: {bool(access)}")
        print(f"access token expired: {_access_token_expired(access) if access else 'n/a'}")
        jwt_exp = _jwt_expires_at(access) if access else None
        if jwt_exp:
            print(f"access token expires (UTC): {jwt_exp.isoformat()}")
        refresh_code = env_value("REVIZTO_REFRESH_CODE")
        legacy_refresh = env_value("REVIZTO_REFRESH_TOKEN")
        print(f"refresh code present: {bool(refresh)}")
        if legacy_refresh and legacy_refresh != refresh_code:
            print(
                "warning: legacy REVIZTO_REFRESH_TOKEN is set and differs from "
                "REVIZTO_REFRESH_CODE; only REVIZTO_REFRESH_CODE is used."
            )
        print(f"access code present: {bool((os.getenv('REVIZTO_ACCESS_CODE') or '').strip())}")
        setup_warning = _revizto_manual_setup_warning()
        if setup_warning:
            print(f"warning: {setup_warning}")
        if access and _access_token_expired(access):
            print(
                "hint: access token expired. Restart python app.py (auto-refresh) or run "
                "python revisto_api.py --exchange with a new REVIZTO_ACCESS_CODE. "
                "Do not run --refresh while app.py is running."
            )
        print(f"session cookie present: {bool(_session_cookie())}")
        print(f"member actions ready: {revizto_member_actions_ready()}")
    elif args.exchange:
        access, refresh = exchange_access_code()
        print("Tokens saved to .env (access token expires in ~1 hour).")
        print(f"Refresh token starts with: {refresh[:12]}...")
    elif args.refresh:
        access = get_revizto_access_token()
        refresh = _refresh_token_value() or ""
        print("Tokens refreshed and saved to .env.")
        print(f"New access token starts with: {access[:12]}...")
        if refresh:
            print(f"Refresh token starts with: {refresh[:12]}...")
    else:
        token = get_revizto_access_token()
        print(f"Access token ready (starts with {token[:12]}...).")
