'''
Flask application — disable/activate users in Autodesk ACC, GTP Stratus, Revizto, TrackVia, OpenSpace, and Symetri.
'''

import os

import env_loader  # noqa: F401
from env_loader import reload_env
import requests
from flask import Flask, jsonify, render_template, request

from acc_api import set_user_account_status
from acc_client import AUTODESK_BASE_URL, AUTODESK_IMPERSONATION_USER_ID, get_autodesk_access_token
from acc_config import get_environment, list_environments
from acc_sync import get_sync_status, get_user_by_email, search_users, sync_environment
from stratus_config import get_stratus_environment, list_stratus_environments
from stratus_api import (
    StratusConfigError,
    StratusUserNotFoundError,
    check_stratus_session_health,
    disable_stratus_user,
    enable_stratus_user,
    get_all_company_users_by_email,
    get_company_user_by_email,
)
from revisto_api import (
    ReviztoApiError,
    ReviztoAuthError,
    ReviztoUserNotFoundError,
    activate_revizto_user_by_email,
    bootstrap_revizto_oauth,
    deactivate_revizto_user_by_email,
    maintain_revizto_tokens,
    revizto_auth_help,
    revizto_configured,
    revizto_member_actions_ready,
)
from session_admin import (
    REVIZTO_ACCESS_CODE_URL,
    save_revizto_session_cookie,
    save_stratus_session_cookie,
    save_symetri_bearer_token,
    session_admin_enabled,
    verify_session_admin_key,
)
from session_reconnect import (
    get_job,
    interactive_reconnect_available,
    start_reconnect,
)
from platform_lookup import lookup_email, sync_platform_memberships
from platform_registry import PLATFORM_LABELS, get_sync_status as get_platform_sync_status
from user_directory import apply_action_to_directory, rebuild_directory
from trackvia_integration import (
    TrackViaApiError,
    TrackViaConfigError,
    TrackViaUserNotFoundError,
    check_trackvia_health,
    disable_trackvia_user_by_email,
    enable_trackvia_user_by_email,
    trackvia_backend,
    trackvia_configured,
)
from trackvia_config import get_trackvia_settings
from openspace_api import (
    OpenSpaceApiError,
    OpenSpaceConfigError,
    OpenSpaceNotSupportedError,
    OpenSpaceUserNotFoundError,
    check_openspace_health,
    disable_openspace_user_by_email,
    enable_openspace_user_by_email,
)
from openspace_config import get_openspace_settings, openspace_configured
from symetri_api import (
    SymetriApiError,
    SymetriConfigError,
    SymetriNotSupportedError,
    SymetriUserNotFoundError,
    check_symetri_health,
    enable_symetri_user_by_email,
    remove_symetri_user_by_email,
)
from symetri_config import get_symetri_settings, symetri_configured
from plangrid_api import (
    PlanGridApiError,
    PlanGridConfigError,
    PlanGridUserNotFoundError,
    check_plangrid_health,
    list_organization_users,
    remove_organization_user_by_email,
    _user_email,
    _user_name,
    _user_uid,
)
from plangrid_config import get_plangrid_settings, plangrid_configured

app = Flask(__name__, static_folder="static", template_folder="templates")


def _is_local_request():
    remote = (request.remote_addr or "").strip()
    return remote in ("127.0.0.1", "::1")


def _with_reconnect_meta(payload):
    data = dict(payload)
    data["needs_reconnect"] = bool(data.get("configured") and not data.get("ok"))
    data["extension_reconnect"] = data["needs_reconnect"]
    data["interactive_reconnect"] = (
        data["needs_reconnect"]
        and interactive_reconnect_available()
        and _is_local_request()
    )
    data["reconnect_available"] = bool(
        data["extension_reconnect"] or data["interactive_reconnect"]
    )
    data["session_admin_configured"] = session_admin_enabled()
    if data["needs_reconnect"] and not data.get("reconnect_hint"):
        if not data["session_admin_configured"]:
            data["reconnect_hint"] = (
                "Session refresh is not set up yet. Add SESSION_ADMIN_KEY to server .env, "
                "restart the app, then run scripts\\connect-stratus-prod.bat or connect-revizto.bat."
            )
        else:
            data["reconnect_hint"] = (
                "Session expired. Click Fix connection and run the script or command "
                "(works on managed PCs — no browser extension needed)."
            )
        if data["interactive_reconnect"]:
            data["reconnect_hint"] += " (On this PC you can also use Reconnect.)"
    return data


def resolve_user_for_action(payload):
    """Return (env, email, user_id) or (None, error_dict, http_status)."""
    email = (payload.get("email") or "").strip()
    user_id = (payload.get("user_id") or "").strip()

    try:
        env = get_environment(payload.get("environment"))
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    if not email:
        return None, {"error": "Email is required."}, 400
    if "@" not in email:
        return None, {"error": "Please enter a valid email address."}, 400

    if not env["account_id"]:
        return None, {
            "error": (
                f"{env['label']} account ID is not configured. "
                f"Set {env['account_id_env_var']} in a .env file in the project folder."
            )
        }, 500

    if not user_id:
        if not env["db_path"].exists():
            return None, {
                "error": (
                    f"No user found for that email in {env['label']}. "
                    "Try Sync from Autodesk or verify the email."
                )
            }, 404
        user = get_user_by_email(env["db_path"], email)
        if not user:
            return None, {
                "error": (
                    f"No user found for that email in {env['label']}. "
                    "Try Sync from Autodesk or verify the email."
                )
            }, 404
        user_id = user["user_id"]

    return (env, email, user_id), None, None


def _stratus_user_summary(user):
    return {
        "email": user.get("email"),
        "pk": user.get("id"),
        "user_id": user.get("userId"),
        "user_name": user.get("userName"),
        "group": user.get("group"),
        "status": user.get("userStatusTypeEnumValue"),
        "status_name": user.get("userStatusTypeEnumName"),
        "default_project_role_id": user.get("defaultProjectRoleId"),
        "default_project_role_name": user.get("defaultProjectRoleName"),
        "is_quick_pass": user.get("isQuickPass"),
    }


def _run_user_action(payload, acc_status, acc_verb, stratus_action, revizto_action):
    """Shared logic for disable and activate endpoints."""
    email = (payload.get("email") or "").strip()
    if not email:
        return {"body": {"error": "Email is required."}, "status": 400}
    if "@" not in email:
        return {"body": {"error": "Please enter a valid email address."}, "status": 400}

    message_parts = []
    partial = False
    acc_result = None
    stratus_result = None
    revizto_result = None
    trackvia_result = None
    openspace_result = None
    symetri_result = None
    acc_error = None
    stratus_error = None
    revizto_error = None
    trackvia_error = None
    openspace_error = None
    symetri_error = None
    environment_key = None

    resolved, error_body, _ = resolve_user_for_action(payload)
    if resolved is not None:
        env, email, user_id = resolved
        environment_key = env["key"]
        try:
            acc_result = set_user_account_status(
                email, user_id, env["account_id"], acc_status
            )
            message_parts.append(f"Autodesk ACC ({env['label']}): {acc_verb}.")
        except requests.HTTPError as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            acc_error = f"Autodesk ACC request failed: {detail}"
            message_parts.append(acc_error)
            partial = True
        except Exception as exc:
            acc_error = str(exc)
            message_parts.append(f"Autodesk ACC: {acc_error}")
            partial = True
    else:
        acc_error = error_body.get("error", f"Autodesk ACC {acc_verb} skipped.")
        message_parts.append(f"Autodesk ACC: {acc_error}")
        partial = True

    stratus_env_key = (
        payload.get("environment") or environment_key or "dev"
    ).strip().lower()

    try:
        stratus_env = get_stratus_environment(stratus_env_key)
    except ValueError as exc:
        message_parts.append(f"Stratus: skipped ({exc})")
        partial = True
        stratus_env = None

    stratus_health = (
        check_stratus_session_health(stratus_env_key)
        if stratus_env is not None
        else {"ok": False, "configured": False}
    )

    if stratus_health.get("ok"):
        try:
            stratus_result = stratus_action(
                email, all_matches=True, environment=stratus_env_key
            )
            count = len(stratus_result)
            stratus_label = stratus_health.get("label", "Stratus")
            if count:
                message_parts.append(
                    f"{stratus_label}: {acc_verb}d {count} company-user row(s) for {email}."
                )
            else:
                message_parts.append(f"{stratus_label}: no rows found for {email}.")
                partial = True
        except StratusUserNotFoundError:
            message_parts.append(
                f"{stratus_health.get('label', 'Stratus')}: no rows found for {email}."
            )
            partial = True
        except requests.HTTPError as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            stratus_error = (
                f"{stratus_health.get('label', 'Stratus')} request failed: {detail}"
            )
            message_parts.append(stratus_error)
            partial = True
        except Exception as exc:
            stratus_error = str(exc)
            message_parts.append(f"Stratus: {stratus_error}")
            partial = True
    elif stratus_health.get("configured"):
        stratus_error = stratus_health.get("message", "Stratus session unavailable.")
        message_parts.append(
            f"{stratus_health.get('label', 'Stratus')}: skipped ({stratus_error})"
        )
        partial = True
    elif stratus_env is not None:
        message_parts.append(
            f"{stratus_env['label']}: skipped (not configured on this server)."
        )
        partial = True
    else:
        message_parts.append("Stratus: skipped (invalid environment).")
        partial = True

    if revizto_member_actions_ready():
        try:
            revizto_result = revizto_action(email)
            member_name = (revizto_result.get("member") or {}).get("name") or email
            message_parts.append(f"Revizto: {acc_verb}d {member_name} ({email}).")
        except ReviztoUserNotFoundError:
            message_parts.append(f"Revizto: no license member found for {email}.")
            partial = True
        except (ReviztoAuthError, ReviztoApiError, requests.HTTPError) as exc:
            if isinstance(exc, requests.HTTPError):
                detail = exc.response.text if exc.response is not None else str(exc)
                revizto_error = f"Revizto request failed: {detail}"
            else:
                revizto_error = str(exc)
            message_parts.append(revizto_error)
            partial = True
        except Exception as exc:
            revizto_error = str(exc)
            message_parts.append(f"Revizto: {revizto_error}")
            partial = True
    elif revizto_configured():
        message_parts.append(
            "Revizto: skipped (session cookie missing — set REVIZTO_SESSION_COOKIE in .env)."
        )
        partial = True
    else:
        message_parts.append("Revizto: skipped (not configured on this server).")
        partial = True

    if trackvia_configured():
        try:
            trackvia_result = (
                disable_trackvia_user_by_email(email)
                if acc_verb == "disable"
                else enable_trackvia_user_by_email(email)
            )
            message_parts.append(
                f"TrackVia: {acc_verb}d {email} (status: {trackvia_result.get('status')})."
            )
        except TrackViaUserNotFoundError:
            message_parts.append(f"TrackVia: no roster row found for {email}.")
            partial = True
        except (TrackViaConfigError, TrackViaApiError, requests.HTTPError) as exc:
            if isinstance(exc, requests.HTTPError):
                detail = exc.response.text if exc.response is not None else str(exc)
                trackvia_error = f"TrackVia request failed: {detail}"
            else:
                trackvia_error = str(exc)
            message_parts.append(trackvia_error)
            partial = True
        except Exception as exc:
            trackvia_error = str(exc)
            message_parts.append(f"TrackVia: {trackvia_error}")
            partial = True
    else:
        message_parts.append("TrackVia: skipped (not configured on this server).")
        partial = True

    if openspace_configured():
        try:
            if acc_verb == "disable":
                openspace_result = disable_openspace_user_by_email(email)
                message_parts.append(
                    f"OpenSpace: removed {email} from organization "
                    f"(account {openspace_result.get('account_id')})."
                )
            else:
                enable_openspace_user_by_email(email)
        except OpenSpaceUserNotFoundError:
            message_parts.append(f"OpenSpace: no org member found for {email}.")
            partial = True
        except OpenSpaceNotSupportedError as exc:
            message_parts.append(f"OpenSpace: skipped ({exc})")
            partial = True
        except (OpenSpaceConfigError, OpenSpaceApiError, requests.HTTPError) as exc:
            if isinstance(exc, requests.HTTPError):
                detail = exc.response.text if exc.response is not None else str(exc)
                openspace_error = f"OpenSpace request failed: {detail}"
            else:
                openspace_error = str(exc)
            message_parts.append(openspace_error)
            partial = True
        except Exception as exc:
            openspace_error = str(exc)
            message_parts.append(f"OpenSpace: {openspace_error}")
            partial = True
    else:
        message_parts.append("OpenSpace: skipped (not configured on this server).")
        partial = True

    if symetri_configured():
        try:
            if acc_verb == "disable":
                symetri_result = remove_symetri_user_by_email(email)
                message_parts.append(
                    f"Symetri: removed {email} from account "
                    f"{symetri_result.get('account_id')} (user {symetri_result.get('user_id')})."
                )
            else:
                enable_symetri_user_by_email(email)
        except SymetriUserNotFoundError:
            message_parts.append(f"Symetri: no account user found for {email}.")
            partial = True
        except SymetriNotSupportedError as exc:
            message_parts.append(f"Symetri: skipped ({exc})")
            partial = True
        except (SymetriConfigError, SymetriApiError, requests.HTTPError) as exc:
            if isinstance(exc, requests.HTTPError):
                detail = exc.response.text if exc.response is not None else str(exc)
                symetri_error = f"Symetri request failed: {detail}"
            else:
                symetri_error = str(exc)
            message_parts.append(symetri_error)
            partial = True
        except Exception as exc:
            symetri_error = str(exc)
            message_parts.append(f"Symetri: {symetri_error}")
            partial = True
    else:
        message_parts.append("Symetri: skipped (not configured on this server).")
        partial = True

    if (
        acc_result is None
        and not stratus_result
        and not revizto_result
        and not trackvia_result
        and not openspace_result
        and not symetri_result
    ):
        return {
            "body": {
                "error": (
                    f"{acc_verb.capitalize()} failed in Autodesk ACC, Stratus, Revizto, "
                    "TrackVia, OpenSpace, and Symetri."
                ),
                "message": " ".join(message_parts),
                "partial": True,
                "acc_error": acc_error,
                "stratus_error": stratus_error,
                "revizto_error": revizto_error,
                "trackvia_error": trackvia_error,
                "openspace_error": openspace_error,
                "symetri_error": symetri_error,
            },
            "status": 502,
        }

    return {
        "body": {
            "message": " ".join(message_parts),
            "partial": partial,
            "environment": environment_key,
            "acc": acc_result,
            "stratus": {
                "count": len(stratus_result) if stratus_result else 0,
                "results": stratus_result,
            },
            "revizto": revizto_result,
            "trackvia": trackvia_result,
            "openspace": openspace_result,
            "symetri": symetri_result,
            "acc_error": acc_error,
            "stratus_error": stratus_error,
            "revizto_error": revizto_error,
            "trackvia_error": trackvia_error,
            "openspace_error": openspace_error,
            "symetri_error": symetri_error,
        },
        "status": 200,
    }


def _record_directory_action(payload, action, result):
    if result.get("status") != 200:
        return
    body = result.get("body") or {}
    environment_key = body.get("environment") or (payload.get("environment") or "dev").strip().lower()
    email = (payload.get("email") or "").strip()
    if not email:
        return
    try:
        apply_action_to_directory(email, environment_key, action, body)
    except Exception:
        pass


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/connect/symetri")
def connect_symetri():
    """Open browser sign-in flow and capture bearer token on the server."""
    if not _is_local_request():
        return (
            "Symetri reconnect must be started from the computer running this app "
            "(open http://127.0.0.1:5000/connect/symetri)."
        ), 403
    return render_template("connect_symetri.html")


@app.get("/connect/revizto")
def connect_revizto():
    """Redirect to Revizto Workspace Active Sessions -> API (access code page)."""
    if not _is_local_request():
        return (
            "Revizto reconnect must be started from the computer running this app "
            "(open http://127.0.0.1:5000/connect/revizto)."
        ), 403
    from flask import redirect

    return redirect(REVIZTO_ACCESS_CODE_URL)


@app.get("/api/config")
def api_config():
    return jsonify({
        "environments": [
            {
                "key": env["key"],
                "label": env["label"],
                "account_configured": bool(env["account_id"]),
                "account_id_env_var": env["account_id_env_var"],
                "db_path": env["db_path"].name,
            }
            for env in list_environments()
        ],
        "default_environment": os.getenv("ACC_ENVIRONMENT", "dev"),
        "stratus_environments": [
            {
                "key": env["key"],
                "label": env["label"],
                "base_url": env["base_url"],
                "configured": env["configured"],
                "session_cookie_env_var": env["session_cookie_env_var"],
                "former_employee_group_env_var": env["former_employee_group_env_var"],
                "disable_default_project_role_id": env["disable_default_project_role_id"],
                "disable_default_project_role_id_env_var": (
                    env["disable_default_project_role_id_env_var"]
                ),
            }
            for env in list_stratus_environments()
        ],
        "revizto_configured": revizto_configured(),
        "revizto_member_actions_ready": revizto_member_actions_ready(),
        "revizto_base_url": os.getenv("REVIZTO_BASE_URL", "https://api.virginia.revizto.com"),
        "revizto_access_code_url": REVIZTO_ACCESS_CODE_URL,
        "trackvia_configured": trackvia_configured(),
        "trackvia_backend": trackvia_backend(),
        "trackvia_base_url": get_trackvia_settings()["base_url"],
        "trackvia_openapi_base_url": get_trackvia_settings().get("openapi_base_url"),
        "trackvia_account_id": get_trackvia_settings().get("account_id") or None,
        "openspace_configured": openspace_configured(),
        "openspace_org_id": get_openspace_settings().get("org_id") or None,
        "openspace_base_url": get_openspace_settings().get("base_url"),
        "symetri_configured": symetri_configured(),
        "symetri_account_id": get_symetri_settings().get("account_id") or None,
        "symetri_api_base_url": get_symetri_settings().get("api_base_url"),
        "plangrid_configured": plangrid_configured(),
        "plangrid_base_url": get_plangrid_settings().get("app_base_url"),
        "plangrid_org_id": get_plangrid_settings().get("org_id") or None,
        "platforms": [
            {"key": key, "label": PLATFORM_LABELS[key]}
            for key in PLATFORM_LABELS
        ],
    })


@app.get("/api/sync/status")
def sync_status():
    try:
        env = get_environment(request.args.get("environment"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(get_sync_status(env["db_path"], env["key"]))


@app.post("/api/sync")
def sync_account_data():
    payload = request.get_json(silent=True) or {}
    try:
        env = get_environment(payload.get("environment"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not env["account_id"]:
        return jsonify({
            "error": (
                f"{env['label']} account ID is not configured. "
                f"Set {env['account_id_env_var']} in a .env file in the project folder."
            )
        }), 400

    try:
        result = sync_environment(
            env,
            base_url=AUTODESK_BASE_URL,
            get_access_token=get_autodesk_access_token,
            impersonation_user_id=AUTODESK_IMPERSONATION_USER_ID,
        )
    except requests.HTTPError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        return jsonify({"error": f"Autodesk sync failed: {detail}"}), 502
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify(result)


@app.get("/api/platforms/lookup")
@app.post("/api/platforms/lookup")
def platform_lookup_api():
    reload_env()
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        email = (payload.get("email") or "").strip()
        environment = payload.get("environment")
    else:
        email = (request.args.get("email") or "").strip()
        environment = request.args.get("environment")
    if not email:
        return jsonify({"error": "Email is required."}), 400
    if "@" not in email:
        return jsonify({"error": "Please enter a valid email address."}), 400

    try:
        result = lookup_email(
            email,
            environment=environment,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/api/platforms/sync/status")
def platform_sync_status_api():
    try:
        env = get_environment(request.args.get("environment"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(get_platform_sync_status(env["key"]))


@app.post("/api/platforms/sync")
def platform_sync_api():
    payload = request.get_json(silent=True) or {}
    try:
        env = get_environment(payload.get("environment"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        result = sync_platform_memberships(env["key"])
    except requests.HTTPError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        return jsonify({"error": f"Platform sync failed: {detail}"}), 502
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify(result)


@app.post("/api/directory/rebuild")
def directory_rebuild_api():
    payload = request.get_json(silent=True) or {}
    try:
        env = get_environment(payload.get("environment"))
        result = rebuild_directory(env["key"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(result)


@app.get("/api/users/search")
def search_users_api():
    query = (request.args.get("q") or "").strip()
    if len(query) < 2:
        return jsonify({"results": []})

    try:
        env = get_environment(request.args.get("environment"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not env["db_path"].exists():
        return jsonify({
            "error": f"No local data for {env['label']}. Run sync first.",
            "results": [],
            "hint": f"No local data for {env['label']}. Run sync first.",
        }), 404

    results = search_users(env["db_path"], query)
    status = get_sync_status(env["db_path"], env["key"])
    hint = None
    if not status.get("synced"):
        hint = f"No users cached for {env['label']}. Click Sync from Autodesk first."
    elif not results:
        hint = "No matching users found."

    return jsonify({"results": results, "environment": env["key"], "hint": hint})


@app.post("/api/disable")
def disable_account():
    payload = request.get_json(silent=True) or {}
    result = _run_user_action(
        payload, "inactive", "disable", disable_stratus_user, deactivate_revizto_user_by_email
    )
    _record_directory_action(payload, "disable", result)
    return jsonify(result["body"]), result["status"]


@app.post("/api/activate")
def activate_account():
    payload = request.get_json(silent=True) or {}
    result = _run_user_action(
        payload, "active", "activate", enable_stratus_user, activate_revizto_user_by_email
    )
    _record_directory_action(payload, "activate", result)
    return jsonify(result["body"]), result["status"]


@app.get("/api/revizto/health")
def revizto_health():
    reload_env()
    label = "Revizto"
    if not revizto_configured():
        return jsonify({
            "ok": False,
            "configured": False,
            "label": label,
            "message": (
                f"{label} is not configured on this server. "
                "Set Revizto tokens in the server .env file."
            ),
        })

    if not revizto_member_actions_ready():
        return jsonify(_with_reconnect_meta({
            "ok": False,
            "configured": True,
            "label": label,
            "message": (
                f"{label} session cookie is missing or expired. "
                "Sign in again to restore activate/deactivate."
            ),
        }))

    try:
        from revisto_api import get_current_user_licenses, get_revizto_access_token

        get_revizto_access_token(allow_refresh=False)
        licenses = get_current_user_licenses()
        license_name = licenses[0].get("name") if licenses else "license"
        return jsonify(_with_reconnect_meta({
            "ok": True,
            "configured": True,
            "label": label,
            "message": f"{label} connected ({license_name}).",
        }))
    except ReviztoAuthError as exc:
        return jsonify(_with_reconnect_meta({
            "ok": False,
            "configured": True,
            "label": label,
            "message": revizto_auth_help(exc),
            "detail": str(exc),
        })), 200
    except Exception as exc:
        return jsonify(_with_reconnect_meta({
            "ok": False,
            "configured": True,
            "label": label,
            "message": revizto_auth_help(exc),
            "detail": str(exc),
        })), 500


@app.get("/api/trackvia/health")
def trackvia_health():
    reload_env()
    return jsonify(check_trackvia_health())


@app.get("/api/symetri/health")
def symetri_health():
    reload_env()
    try:
        return jsonify(_with_reconnect_meta(check_symetri_health()))
    except Exception as exc:
        return jsonify(_with_reconnect_meta({
            "ok": False,
            "configured": symetri_configured(),
            "label": "Symetri",
            "message": "Symetri session expired or invalid. Sign in again at my.symetri.com.",
            "detail": str(exc),
        })), 500


@app.get("/api/openspace/health")
def openspace_health():
    reload_env()
    try:
        return jsonify(_with_reconnect_meta(check_openspace_health()))
    except Exception as exc:
        return jsonify(_with_reconnect_meta({
            "ok": False,
            "configured": openspace_configured(),
            "label": "OpenSpace",
            "message": "OpenSpace session expired or invalid. Sign in again to reconnect.",
            "detail": str(exc),
        })), 500


@app.get("/api/plangrid/health")
def plangrid_health():
    reload_env()
    try:
        return jsonify(check_plangrid_health())
    except Exception as exc:
        return jsonify({
            "ok": False,
            "configured": plangrid_configured(),
            "label": "PlanGrid",
            "message": str(exc),
            "detail": str(exc),
        }), 500


@app.get("/api/plangrid/users")
def plangrid_users():
    """List org users via Admin Console GET /proxy/aapi2/organizations/.../users."""
    reload_env()
    try:
        limit = int(request.args.get("limit") or 100)
    except ValueError:
        limit = 100
    limit = max(1, min(limit, 500))

    try:
        users = list_organization_users(
            include_license=True,
            include_profile=True,
            include_projects=False,
            limit=limit,
        )
        compact = []
        for user in users:
            license_info = user.get("license") if isinstance(user, dict) else None
            compact.append({
                "uid": _user_uid(user),
                "email": _user_email(user),
                "name": _user_name(user),
                "status": user.get("status") if isinstance(user, dict) else None,
                "license": license_info,
            })
        return jsonify({
            "ok": True,
            "count": len(compact),
            "users": compact,
        })
    except PlanGridConfigError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except PlanGridUserNotFoundError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404
    except PlanGridApiError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502


@app.post("/api/plangrid/remove")
def plangrid_remove():
    """Remove a user from the PlanGrid org (DELETE aapi1/organization/.../users)."""
    reload_env()
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or request.args.get("email") or "").strip()
    dry_run = bool(payload.get("dry_run") or request.args.get("dry_run"))
    unlink = payload.get("unlink_org_project")
    if unlink is None:
        unlink = True

    if not email:
        return jsonify({"ok": False, "error": "Email is required."}), 400
    if "@" not in email:
        return jsonify({"ok": False, "error": "Please enter a valid email address."}), 400

    try:
        result = remove_organization_user_by_email(
            email,
            unlink_org_project=bool(unlink),
            dry_run=dry_run,
        )
        return jsonify({"ok": True, **result})
    except PlanGridConfigError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except PlanGridUserNotFoundError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404
    except PlanGridApiError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502


@app.get("/api/stratus/health")
def stratus_health():
    reload_env()
    environment = request.args.get("environment")
    try:
        return jsonify(_with_reconnect_meta(check_stratus_session_health(environment)))
    except Exception as exc:
        try:
            env = get_stratus_environment(environment)
            configured = env["configured"]
        except ValueError:
            configured = False
        return jsonify(_with_reconnect_meta({
            "ok": False,
            "configured": configured,
            "message": "Stratus session expired or invalid. Sign in again to reconnect.",
            "detail": str(exc),
        })), 500


@app.get("/api/stratus/lookup")
def stratus_lookup():
    email = (request.args.get("email") or "").strip()
    environment = request.args.get("environment")
    all_matches = request.args.get("all_matches", "").lower() in {"1", "true", "yes"}
    if not email:
        return jsonify({"error": "Email is required."}), 400
    if "@" not in email:
        return jsonify({"error": "Please enter a valid email address."}), 400

    try:
        if all_matches:
            users = get_all_company_users_by_email(email, environment=environment)
            return jsonify({
                "email": email,
                "environment": get_stratus_environment(environment)["key"],
                "count": len(users),
                "results": [_stratus_user_summary(user) for user in users],
            })
        user = get_company_user_by_email(email, environment=environment)
    except StratusConfigError as exc:
        return jsonify({"error": str(exc)}), 500
    except StratusUserNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except requests.HTTPError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        return jsonify({"error": f"Stratus request failed: {detail}"}), 502
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify(_stratus_user_summary(user))


def _require_session_admin():
    if not session_admin_enabled():
        return jsonify({
            "error": (
                "Session connect is not enabled on this server. "
                "Set SESSION_ADMIN_KEY in the server .env file."
            ),
        }), 503
    provided = (request.headers.get("X-Session-Admin-Key") or "").strip()
    if not verify_session_admin_key(provided):
        return jsonify({"error": "Invalid or missing X-Session-Admin-Key."}), 401
    return None


@app.get("/api/admin/sessions/status")
def session_admin_status():
    return jsonify({
        "enabled": session_admin_enabled(),
        "connect_command": "python connect_sessions.py --platform <stratus|revizto|symetri>",
        "extension_path": "browser_extension",
    })


@app.post("/api/admin/sessions/stratus")
def upload_stratus_session():
    denied = _require_session_admin()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    cookie = (payload.get("cookie") or "").strip()
    environment = (payload.get("environment") or "prod").strip().lower()
    validate = payload.get("validate", True)

    try:
        result = save_stratus_session_cookie(
            cookie,
            environment=environment,
            validate=bool(validate),
        )
        return jsonify({"ok": True, **result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/admin/sessions/symetri")
def upload_symetri_session():
    denied = _require_session_admin()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    token = (payload.get("bearer_token") or payload.get("token") or "").strip()
    validate = payload.get("validate", True)

    try:
        result = save_symetri_bearer_token(token, validate=bool(validate))
        return jsonify({"ok": True, **result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/admin/sessions/revizto")
def upload_revizto_session():
    denied = _require_session_admin()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    cookie = (payload.get("cookie") or "").strip()
    validate = payload.get("validate", True)

    try:
        result = save_revizto_session_cookie(cookie, validate=bool(validate))
        return jsonify({"ok": True, **result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/admin/revizto/oauth")
def revizto_oauth_exchange():
    """
    Exchange a Revizto access code for access + refresh tokens.
    Body: {"access_code": "..."} or empty to use REVIZTO_ACCESS_CODE from .env.
    """
    denied = _require_session_admin()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    access_code = (payload.get("access_code") or "").strip()

    try:
        access_token, _refresh_token = bootstrap_revizto_oauth(access_code or None)
        return jsonify({
            "ok": True,
            "message": "Revizto OAuth tokens saved.",
            "access_token_prefix": access_token[:12],
        })
    except ReviztoAuthError as exc:
        return jsonify({
            "ok": False,
            "error": revizto_auth_help(exc),
            "detail": str(exc),
        }), 400


@app.get("/api/session/connect-command")
def connect_command():
    platform = (request.args.get("platform") or "").strip().lower()
    environment = (request.args.get("environment") or "prod").strip().lower()
    if platform not in ("stratus", "revizto", "symetri"):
        return jsonify({"error": "platform must be stratus, revizto, or symetri."}), 400

    server = request.host_url.rstrip("/")
    base = f".venv\\Scripts\\python connect_sessions.py --platform {platform}"
    if platform == "stratus":
        base += f" --environment {environment}"
    script = (
        f"scripts/connect-stratus-{environment}.bat"
        if platform == "stratus"
        else "scripts/connect-symetri.bat"
        if platform == "symetri"
        else "scripts/connect-revizto.bat"
    )
    return jsonify({
        "server_url": server,
        "script_path": script,
        "local_command": base,
        "remote_command": f"{base} --server {server}",
        "admin_key_configured": session_admin_enabled(),
    })


@app.get("/api/session/extension/info")
def extension_info():
    payload = {
        "ok": session_admin_enabled(),
        "server_url": request.host_url.rstrip("/"),
        "admin_key_configured": session_admin_enabled(),
        "extension_path": "browser_extension",
        "options_url": f"{request.host_url.rstrip('/')}/api/session/extension/info",
    }
    provided = (request.headers.get("X-Session-Admin-Key") or "").strip()
    if provided:
        if not verify_session_admin_key(provided):
            return jsonify({
                **payload,
                "ok": False,
                "error": "Invalid SESSION_ADMIN_KEY.",
            }), 401
        payload["message"] = "Extension connection OK."
        payload["ok"] = True
        return jsonify(payload)

    if session_admin_enabled():
        payload["message"] = "Server is ready for the Session Sync extension."
    else:
        payload["message"] = (
            "Add SESSION_ADMIN_KEY to the server .env file before using the extension."
        )
    return jsonify(payload)


@app.post("/api/session/symetri/token")
def save_symetri_token_local():
    """Save a fresh Symetri bearer token from the local UI (localhost only)."""
    if not _is_local_request():
        return jsonify({
            "error": "Symetri token update is only allowed from the machine running this app.",
        }), 403

    payload = request.get_json(silent=True) or {}
    token = (payload.get("bearer_token") or payload.get("token") or "").strip()
    try:
        result = save_symetri_bearer_token(token, validate=True)
        return jsonify({"ok": True, **result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/session/revizto/access-code")
def save_revizto_access_code_local():
    """Exchange a Revizto API access code from the local UI (localhost only)."""
    if not _is_local_request():
        return jsonify({
            "error": "Revizto access code update is only allowed from the machine running this app.",
        }), 403

    payload = request.get_json(silent=True) or {}
    access_code = (payload.get("access_code") or payload.get("code") or "").strip()
    if not access_code:
        return jsonify({"ok": False, "error": "access_code is required."}), 400

    try:
        bootstrap_revizto_oauth(access_code)
        from revisto_api import get_current_user_licenses

        licenses = get_current_user_licenses()
        license_name = licenses[0].get("name") if licenses else "license"
        return jsonify({
            "ok": True,
            "platform": "revizto",
            "message": f"Revizto connected ({license_name}).",
        })
    except ReviztoAuthError as exc:
        return jsonify({"ok": False, "error": revizto_auth_help(exc)}), 400


@app.get("/api/session/reconnect/capabilities")
def reconnect_capabilities():
    return jsonify({"interactive": interactive_reconnect_available()})


@app.post("/api/session/reconnect")
def reconnect_session():
    payload = request.get_json(silent=True) or {}
    platform = (payload.get("platform") or "").strip().lower()
    environment = (payload.get("environment") or "prod").strip().lower()
    if platform not in ("stratus", "revizto", "symetri"):
        return jsonify({"error": "platform must be stratus, revizto, or symetri."}), 400
    try:
        job_id, job = start_reconnect(platform, environment)
        return jsonify({"ok": True, "job_id": job_id, **job})
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503


@app.get("/api/session/reconnect/status")
def reconnect_session_status():
    job_id = (request.args.get("job_id") or "").strip()
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Unknown reconnect job."}), 404
    return jsonify(job)


if __name__ == "__main__":
    import os
    import threading
    import time

    def _revizto_token_keeper():
        from env_loader import env_value

        time.sleep(5)
        interval = 5 * 60
        while True:
            try:
                maintain_revizto_tokens()
                interval = 5 * 60
            except ReviztoAuthError as exc:
                print(f"Revizto token keeper: {revizto_auth_help(exc)}", flush=True)
                interval = 30 if env_value("REVIZTO_ACCESS_CODE") else 5 * 60
            except (PermissionError, OSError) as exc:
                print(
                    f"Revizto token keeper: could not update .env ({exc}). "
                    "Tokens are saved to local cache if refresh succeeded.",
                    flush=True,
                )
                interval = 5 * 60
            except Exception as exc:
                print(f"Revizto token keeper error: {exc}", flush=True)
                interval = 5 * 60
            time.sleep(interval)

    def _revizto_access_code_watcher():
        from env_loader import env_value

        last_code = env_value("REVIZTO_ACCESS_CODE")
        time.sleep(15)
        while True:
            reload_env()
            code = env_value("REVIZTO_ACCESS_CODE")
            if code and code != last_code:
                last_code = code
                try:
                    maintain_revizto_tokens()
                    print("Revizto: exchanged new access code from .env", flush=True)
                    last_code = ""
                except ReviztoAuthError as exc:
                    print(f"Revizto access code exchange: {revizto_auth_help(exc)}", flush=True)
                except PermissionError as exc:
                    print(
                        "Revizto access code exchange: could not write tokens to .env "
                        f"(network drive lock?): {exc}",
                        flush=True,
                    )
                except OSError as exc:
                    print(f"Revizto access code exchange error: {exc}", flush=True)
            time.sleep(20)

    # Flask debug reloader spawns a parent watcher + child server; only run keeper in the child.
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Thread(
            target=_revizto_token_keeper, daemon=True, name="revizto-token-keeper"
        ).start()
        threading.Thread(
            target=_revizto_access_code_watcher, daemon=True, name="revizto-access-code-watcher"
        ).start()
        try:
            maintain_revizto_tokens()
        except ReviztoAuthError as exc:
            print(f"Revizto startup: {revizto_auth_help(exc)}", flush=True)
        except Exception as exc:
            print(f"Revizto startup error: {exc}", flush=True)

    app.run(debug=True, host="127.0.0.1", port=5000)
