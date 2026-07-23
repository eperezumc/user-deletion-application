"""Look up user membership across platforms (live or cached registry)."""

import requests

from acc_config import get_environment
from acc_sync import get_user_by_email
from platform_registry import (
    PLATFORM_KEYS,
    PLATFORM_LABELS,
    normalize_email,
    record_sync_finish,
    record_sync_start,
    upsert_membership,
)
from user_directory import get_directory_stats, get_directory_user, update_platform_in_directory
from revisto_api import (
    ReviztoApiError,
    ReviztoAuthError,
    find_license_member_by_email,
    get_default_license,
    get_license_team_members,
    revizto_configured,
    revizto_member_actions_ready,
)
from stratus_api import (
    StratusConfigError,
    StratusUserNotFoundError,
    check_stratus_session_health,
    get_all_company_user_roles,
    get_all_company_users_by_email,
    is_stratus_user_disabled,
    stratus_status_label,
)
from stratus_config import get_stratus_environment
from trackvia_integration import (
    TrackViaApiError,
    TrackViaConfigError,
    TrackViaUserNotFoundError,
    index_trackvia_users_by_email,
    lookup_trackvia_user,
    trackvia_configured,
    trackvia_supports_bulk_sync,
)
from trackvia_config import trackvia_missing_settings
from openspace_api import (
    OpenSpaceApiError,
    OpenSpaceConfigError,
    check_openspace_health,
    find_org_member_by_email,
    list_org_members,
)
from openspace_config import openspace_configured, openspace_missing_settings
from symetri_api import (
    SymetriApiError,
    SymetriConfigError,
    check_symetri_health,
    find_account_user_by_email,
    list_symetri_users_for_sync,
)
from symetri_config import symetri_configured, symetri_missing_settings

# This will be used to create a base platform entry.
def _base_platform_entry(platform, configured=True, message=None, check_state="absent"):
    entry = {
        "platform": platform,
        "label": PLATFORM_LABELS[platform],
        "configured": configured,
        "present": False,
        "check_state": check_state,
    }
    if message:
        entry["message"] = message
    return entry


# This will be used to normalize the membership status.
def _normalize_membership_status(status=None, deactivated=None):
    """Map platform-specific status values to active or disabled."""
    if deactivated:
        return "disabled"
    value = (status or "").strip().lower()
    if value in {"inactive", "disabled", "deactivated", "2"}:
        return "disabled"
    return "active"


# This will be used to mark the entry as present.
def _mark_present(entry, status=None, deactivated=None, **fields):
    entry["present"] = True
    entry["check_state"] = "present"
    entry["membership_status"] = _normalize_membership_status(status, deactivated)
    entry["status"] = status
    for key, value in fields.items():
        entry[key] = value
    return entry


# This will be used to check the ACC platform.
def _check_acc(email, env):
    entry = _base_platform_entry("acc", configured=bool(env["account_id"]))
    if not env["account_id"]:
        entry["check_state"] = "not_configured"
        entry["message"] = (
            f"{env['label']} account ID is not configured. "
            f"Set {env['account_id_env_var']} in .env."
        )
        return entry

    if not env["db_path"].exists():
        entry["check_state"] = "unavailable"
        entry["message"] = f"No local ACC data for {env['label']}. Run Sync from Autodesk first."
        return entry

    user = get_user_by_email(env["db_path"], email)
    if not user:
        entry["check_state"] = "absent"
        entry["message"] = f"Not found in {env['label']} user cache."
        return entry

    return _mark_present(
        entry,
        status=user.get("status") or "active",
        external_id=user["user_id"],
        details={
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
        },
    )


# This will be used to check the Stratus platform.
def _check_stratus(email, environment):
    try:
        stratus_env = get_stratus_environment(environment)
    except ValueError as exc:
        entry = _base_platform_entry(
            "stratus", configured=False, message=str(exc), check_state="not_configured"
        )
        return entry

    health = check_stratus_session_health(stratus_env["key"])
    entry = _base_platform_entry("stratus", configured=health.get("configured", False))
    if not health.get("configured"):
        entry["check_state"] = "not_configured"
        entry["message"] = health.get("message", "Stratus is not configured.")
        return entry
    if not health.get("ok"):
        entry["check_state"] = "unavailable"
        entry["message"] = health.get("message", "Stratus session unavailable.")
        return entry

    try:
        users = get_all_company_users_by_email(email, environment=stratus_env["key"])
    except StratusUserNotFoundError:
        entry["check_state"] = "absent"
        entry["message"] = f"Not found in {stratus_env['label']}."
        return entry
    except (StratusConfigError, requests.HTTPError) as exc:
        entry["check_state"] = "unavailable"
        entry["message"] = str(exc)
        return entry

    disabled = any(is_stratus_user_disabled(user, stratus_env) for user in users)
    status_label = "Disabled" if disabled else stratus_status_label(users[0], stratus_env)
    return _mark_present(
        entry,
        status=status_label,
        deactivated=disabled,
        external_id=users[0].get("id"),
        details={
            "count": len(users),
            "user_name": users[0].get("userName"),
            "group": users[0].get("group"),
        },
    )

# This will be used to check the Revizto platform.
def _check_revizto(email):
    entry = _base_platform_entry("revizto", configured=revizto_configured())
    if not revizto_configured():
        entry["check_state"] = "not_configured"
        entry["message"] = "Revizto is not configured on this server."
        return entry
    if not revizto_member_actions_ready():
        entry["check_state"] = "unavailable"
        entry["message"] = "Revizto session cookie is missing or expired."
        return entry

    try:
        license_record = get_default_license()
        member = find_license_member_by_email(license_record["uuid"], email)
    except (ReviztoAuthError, ReviztoApiError, requests.HTTPError) as exc:
        entry["check_state"] = "unavailable"
        entry["message"] = str(exc)
        return entry

    if not member:
        entry["check_state"] = "absent"
        entry["message"] = "Not found in Revizto license team."
        return entry

    return _mark_present(
        entry,
        status="active",
        deactivated=bool(member.get("deactivated")),
        external_id=member.get("member_uuid"),
        details={
            "name": member.get("name"),
            "role": member.get("role"),
            "license_name": member.get("license_name"),
        },
    )


# This will be used to check the TrackVia platform.
def _check_trackvia(email):
    entry = _base_platform_entry("trackvia", configured=trackvia_configured())
    if not trackvia_configured():
        entry["check_state"] = "not_configured"
        missing = ", ".join(trackvia_missing_settings())
        entry["message"] = f"TrackVia is not configured. Set {missing} in .env."
        return entry

    try:
        result = lookup_trackvia_user(email)
    except (TrackViaConfigError, TrackViaApiError, requests.HTTPError) as exc:
        entry["check_state"] = "unavailable"
        entry["message"] = str(exc)
        return entry
    except Exception as exc:
        entry["check_state"] = "unavailable"
        entry["message"] = str(exc)
        return entry

    if not result:
        entry["check_state"] = "absent"
        entry["message"] = "Not found in TrackVia roster view."
        return entry

    return _mark_present(
        entry,
        status=result.get("status"),
        deactivated=result.get("disabled"),
        external_id=result.get("record_id"),
        details={"status": result.get("status"), "backend": "api"},
    )

# This will be used to apply the live TrackVia date to the directory.
def _apply_live_trackvia(email, platforms, environment_key, synced_at=None):
    """
    TrackVia cannot bulk-list records on this API account, so per-email find during
    full sync is slow and often stale. Refresh TrackVia from the API on each lookup.
    """
    if not trackvia_configured():
        return platforms

    entry = _check_trackvia(email)
    if synced_at:
        entry["synced_at"] = synced_at
    platforms["trackvia"] = entry

    if entry.get("check_state") in {"unavailable", "not_configured"}:
        return platforms

    present = entry.get("check_state") == "present"
    update_platform_in_directory(
        email,
        environment_key,
        "trackvia",
        present=present,
        status=entry.get("status"),
        external_id=entry.get("external_id"),
        deactivated=entry.get("membership_status") == "disabled",
    )
    upsert_membership(
        email,
        "trackvia",
        environment_key,
        present=present,
        status=entry.get("status"),
        external_id=entry.get("external_id"),
        details={"status": entry.get("status")} if entry.get("status") else None,
        synced_at=synced_at,
    )
    return platforms


# This will be used to check the OpenSpace platform.
def _check_openspace(email):
    entry = _base_platform_entry("openspace", configured=openspace_configured())
    if not openspace_configured():
        missing = ", ".join(openspace_missing_settings())
        entry["message"] = f"OpenSpace is not configured. Set {missing} in .env."
        entry["check_state"] = "not_configured"
        return entry

    try:
        member = find_org_member_by_email(email)
    except (OpenSpaceConfigError, OpenSpaceApiError, requests.HTTPError) as exc:
        entry["check_state"] = "unavailable"
        entry["message"] = str(exc)
        return entry
    except Exception as exc:
        entry["check_state"] = "unavailable"
        entry["message"] = str(exc)
        return entry

    if not member:
        entry["check_state"] = "absent"
        entry["message"] = "Not found in OpenSpace organization."
        return entry

    return _mark_present(
        entry,
        status=member.get("role"),
        external_id=member.get("account_id"),
        details={"role": member.get("role"), "name": member.get("name")},
    )


# This will be used to check the Symetri platform.
def _check_symetri(email):
    entry = _base_platform_entry("symetri", configured=symetri_configured())
    if not symetri_configured():
        missing = ", ".join(symetri_missing_settings())
        entry["message"] = f"Symetri is not configured. Set {missing} in .env."
        entry["check_state"] = "not_configured"
        return entry

    try:
        member = find_account_user_by_email(email)
    except (SymetriConfigError, SymetriApiError, requests.HTTPError) as exc:
        entry["check_state"] = "unavailable"
        entry["message"] = str(exc)
        return entry
    except Exception as exc:
        entry["check_state"] = "unavailable"
        entry["message"] = str(exc)
        return entry

    if not member:
        entry["check_state"] = "absent"
        entry["message"] = "Not found in Symetri account users."
        return entry

    return _mark_present(
        entry,
        external_id=member.get("user_id"),
        details={"name": member.get("name"), "account_id": member.get("account_id")},
    )


# This will be used to lookup the email from the live data sources.
def lookup_email_live(email, environment=None):
    """Check one email against each platform using live data sources."""
    email = normalize_email(email)
    env = get_environment(environment)
    environment_key = env["key"]

    platforms = {
        "acc": _check_acc(email, env),
        "stratus": _check_stratus(email, environment_key),
        "revizto": _check_revizto(email),
        "trackvia": _check_trackvia(email),
        "openspace": _check_openspace(email),
        "symetri": _check_symetri(email),
    }

    present_on = [key for key in PLATFORM_KEYS if platforms[key].get("present")]
    return {
        "email": email,
        "environment": environment_key,
        "source": "live",
        "platforms": platforms,
        "present_on": present_on,
        "present_count": len(present_on),
    }


# This will be used to lookup the email from the local user directory.
def lookup_email_from_directory(email, environment=None):
    """Return membership from the local user directory when a row exists."""
    email = normalize_email(email)
    env = get_environment(environment)
    user = get_directory_user(email, environment=env["key"])
    if not user:
        return None

    platforms = {}
    for key in PLATFORM_KEYS:
        cached = (user.get("platforms") or {}).get(key) or {}
        present = bool(cached.get("present"))
        membership = cached.get("membership") or ("absent" if not present else "active")
        entry = {
            "platform": key,
            "label": cached.get("label") or PLATFORM_LABELS[key],
            "configured": True,
            "present": present,
            "check_state": "present" if present else "absent",
            "membership_status": membership,
            "status": cached.get("status"),
            "external_id": cached.get("external_id"),
            "synced_at": user.get("synced_at"),
        }
        if not present:
            entry["message"] = "Not found in synced directory. Run Sync all platforms."
        elif membership == "disabled":
            entry["message"] = "Cached status: disabled."
        platforms[key] = entry

    _apply_live_trackvia(email, platforms, env["key"], synced_at=user.get("synced_at"))

    present_on = [key for key in PLATFORM_KEYS if platforms[key].get("present")]
    stats = get_directory_stats(env["key"])
    return {
        "email": user["email"],
        "environment": env["key"],
        "source": "directory",
        "display_name": user.get("display_name"),
        "platforms": platforms,
        "present_on": present_on,
        "present_count": len(present_on),
        "synced_at": user.get("synced_at"),
        "directory_user_count": stats.get("user_count", 0),
    }


# This will be used to lookup the email from the local user directory.
def lookup_email(email, environment=None, live=False):
    """Look up membership from the local user directory (filled by Sync all platforms).

    ``live`` is accepted for backward compatibility but ignored; lookup is always
    directory-only.
    """
    del live
    email = normalize_email(email)
    cached = lookup_email_from_directory(email, environment=environment)
    if cached:
        return cached

    env = get_environment(environment)
    platforms = {}
    for key in PLATFORM_KEYS:
        entry = _base_platform_entry(key, configured=True)
        entry["check_state"] = "absent"
        entry["message"] = "Not in synced directory."
        platforms[key] = entry

    _apply_live_trackvia(email, platforms, env["key"])

    present_on = [key for key in PLATFORM_KEYS if platforms[key].get("present")]
    return {
        "email": email,
        "environment": env["key"],
        "source": "directory",
        "directory_miss": True,
        "message": "Email not found in synced directory. Run Sync all platforms to refresh.",
        "platforms": platforms,
        "present_on": present_on,
        "present_count": len(present_on),
    }

# This will be used to sync the platform memberships.
def sync_platform_memberships(environment=None):
    """Rebuild the local registry from ACC cache, Stratus, and Revizto."""
    env = get_environment(environment)
    environment_key = env["key"]
    run_id = record_sync_start(environment_key)
    synced_at = None

    try:
        emails = set()

        if env["db_path"].exists():
            import sqlite3

            with sqlite3.connect(env["db_path"]) as conn:
                rows = conn.execute(
                    "SELECT email FROM users WHERE email IS NOT NULL AND email != ''"
                ).fetchall()
            for (email,) in rows:
                emails.add(normalize_email(email))

        stratus_env = get_stratus_environment(environment_key)
        stratus_health = check_stratus_session_health(stratus_env["key"])
        stratus_users = []
        if stratus_health.get("ok"):
            stratus_users = get_all_company_user_roles(environment=stratus_env["key"])
            for user in stratus_users:
                email = (user.get("email") or "").strip()
                if email:
                    emails.add(normalize_email(email))

        revizto_members = []
        if revizto_member_actions_ready():
            license_record = get_default_license()
            revizto_members = get_license_team_members(
                license_record["uuid"], with_deactivated=True
            )
            for member in revizto_members:
                user = member.get("user") or {}
                email = (user.get("email") or "").strip()
                if email:
                    emails.add(normalize_email(email))

        stratus_by_email = {}
        for user in stratus_users:
            email = normalize_email(user.get("email") or "")
            if email:
                stratus_by_email.setdefault(email, []).append(user)

        revizto_by_email = {}
        for member in revizto_members:
            user = member.get("user") or {}
            email = normalize_email(user.get("email") or "")
            if email:
                revizto_by_email[email] = member

        trackvia_by_email = {}

        openspace_by_email = {}
        if openspace_configured():
            try:
                openspace_health = check_openspace_health()
            except Exception:
                openspace_health = {"ok": False}
            if openspace_health.get("ok"):
                for member in list_org_members():
                    member_email = normalize_email(member.get("email") or "")
                    if member_email:
                        emails.add(member_email)
                        openspace_by_email[member_email] = member

        symetri_by_email = {}
        if symetri_configured():
            try:
                symetri_health = check_symetri_health()
            except Exception:
                symetri_health = {"ok": False}
            if symetri_health.get("ok"):
                for member in list_symetri_users_for_sync():
                    member_email = normalize_email(member.get("email") or "")
                    if member_email:
                        emails.add(member_email)
                        symetri_by_email[member_email] = member

        if trackvia_configured():
            trackvia_by_email = index_trackvia_users_by_email(emails)
            for trackvia_email in trackvia_by_email:
                emails.add(trackvia_email)

        from datetime import datetime, timezone

        synced_at = datetime.now(timezone.utc).isoformat()

        for email in sorted(emails):
            acc_user = (
                get_user_by_email(env["db_path"], email)
                if env["db_path"].exists()
                else None
            )
            upsert_membership(
                email,
                "acc",
                environment_key,
                present=bool(acc_user),
                status=acc_user.get("status") if acc_user else None,
                external_id=acc_user["user_id"] if acc_user else None,
                details={
                    "first_name": acc_user.get("first_name"),
                    "last_name": acc_user.get("last_name"),
                }
                if acc_user
                else None,
                synced_at=synced_at,
            )

            stratus_matches = stratus_by_email.get(email, [])
            stratus_user = stratus_matches[0] if stratus_matches else None
            stratus_disabled = any(
                is_stratus_user_disabled(user, stratus_env) for user in stratus_matches
            )
            upsert_membership(
                email,
                "stratus",
                environment_key,
                present=bool(stratus_user),
                status=(
                    "Disabled"
                    if stratus_disabled
                    else stratus_status_label(stratus_user, stratus_env)
                    if stratus_user
                    else None
                ),
                external_id=stratus_user.get("id") if stratus_user else None,
                details={
                    "count": len(stratus_matches),
                    "user_name": stratus_user.get("userName"),
                }
                if stratus_user
                else None,
                synced_at=synced_at,
            )

            revizto_member = revizto_by_email.get(email)
            revizto_user = (revizto_member or {}).get("user") or {}
            revizto_name = (
                revizto_user.get("fullname")
                or f"{revizto_user.get('firstname', '')} {revizto_user.get('lastname', '')}".strip()
            )
            upsert_membership(
                email,
                "revizto",
                environment_key,
                present=bool(revizto_member),
                status=(
                    "deactivated"
                    if revizto_member and revizto_member.get("deactivated")
                    else "active"
                    if revizto_member
                    else None
                ),
                external_id=revizto_member.get("uuid") if revizto_member else None,
                details={"name": revizto_name} if revizto_name else None,
                synced_at=synced_at,
            )

            trackvia_summary = trackvia_by_email.get(email)
            upsert_membership(
                email,
                "trackvia",
                environment_key,
                present=bool(trackvia_summary),
                status=trackvia_summary.get("status") if trackvia_summary else None,
                external_id=trackvia_summary.get("record_id") if trackvia_summary else None,
                details={"status": trackvia_summary.get("status")} if trackvia_summary else None,
                synced_at=synced_at,
            )

            openspace_member = openspace_by_email.get(email)
            upsert_membership(
                email,
                "openspace",
                environment_key,
                present=bool(openspace_member),
                status="active" if openspace_member else None,
                external_id=openspace_member.get("account_id") if openspace_member else None,
                details={
                    "role": openspace_member.get("role"),
                    "name": openspace_member.get("name"),
                }
                if openspace_member
                else None,
                synced_at=synced_at,
            )

            symetri_member = symetri_by_email.get(email)
            upsert_membership(
                email,
                "symetri",
                environment_key,
                present=bool(symetri_member),
                status="active" if symetri_member else None,
                external_id=symetri_member.get("user_id") if symetri_member else None,
                details={"name": symetri_member.get("name")} if symetri_member else None,
                synced_at=synced_at,
            )

        from user_directory import rebuild_directory

        directory_result = rebuild_directory(environment_key)
        record_sync_finish(run_id, environment_key, len(emails))
        return {
            "environment": environment_key,
            "status": "success",
            "user_count": len(emails),
            "synced_at": synced_at,
            "directory_user_count": directory_result["user_count"],
            "trackvia_sync_mode": "bulk" if trackvia_supports_bulk_sync() else "find",
            "trackvia_user_count": len(trackvia_by_email),
        }
    except Exception as exc:
        record_sync_finish(run_id, environment_key, 0, error=str(exc))
        raise
