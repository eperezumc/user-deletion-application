"""Wide-format user directory — one row per person with per-platform status columns."""

import json
import sqlite3
from datetime import datetime, timezone

from acc_sync import get_user_by_email
from acc_config import get_environment
from platform_registry import DB_PATH, PLATFORM_KEYS, PLATFORM_LABELS, normalize_email, init_db

DIRECTORY_TABLE = "user_directory"

DIRECTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_directory (
    email TEXT NOT NULL COLLATE NOCASE,
    environment TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    acc_present INTEGER NOT NULL DEFAULT 0,
    acc_status TEXT,
    acc_membership TEXT,
    acc_external_id TEXT,
    stratus_present INTEGER NOT NULL DEFAULT 0,
    stratus_status TEXT,
    stratus_membership TEXT,
    stratus_external_id TEXT,
    revizto_present INTEGER NOT NULL DEFAULT 0,
    revizto_status TEXT,
    revizto_membership TEXT,
    revizto_external_id TEXT,
    trackvia_present INTEGER NOT NULL DEFAULT 0,
    trackvia_status TEXT,
    trackvia_membership TEXT,
    trackvia_external_id TEXT,
    openspace_present INTEGER NOT NULL DEFAULT 0,
    openspace_status TEXT,
    openspace_membership TEXT,
    openspace_external_id TEXT,
    symetri_present INTEGER NOT NULL DEFAULT 0,
    symetri_status TEXT,
    symetri_membership TEXT,
    symetri_external_id TEXT,
    synced_at TEXT,
    last_action_at TEXT,
    last_action TEXT,
    PRIMARY KEY (email, environment)
);

CREATE INDEX IF NOT EXISTS idx_user_directory_env
    ON user_directory(environment);

CREATE INDEX IF NOT EXISTS idx_user_directory_name
    ON user_directory(environment, last_name, first_name);
"""




# This will be used to get the current UTC time.
def _utc_now():
    return datetime.now(timezone.utc).isoformat()

# This will be used to initialize the directory.
def init_directory(db_path=DB_PATH):
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(DIRECTORY_SCHEMA)
        conn.commit()


# This will be used to split the person name.
def _split_person_name(full_name):
    full_name = (full_name or "").strip()
    if not full_name:
        return None, None
    parts = full_name.split(None, 1)
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]


# This will be used to get the membership detail names.
def _membership_details_names(conn, email, environment):
    """Pull display names stored on platform membership rows during sync."""
    first_name = None
    last_name = None
    rows = conn.execute(
        """
        SELECT details
        FROM platform_memberships
        WHERE email = ? AND environment = ? AND details IS NOT NULL AND details != ''
        """,
        (email, environment),
    ).fetchall()
    for (details_json,) in rows:
        try:
            details = json.loads(details_json)
        except json.JSONDecodeError:
            continue
        if not isinstance(details, dict):
            continue
        if details.get("first_name"):
            first_name = first_name or details["first_name"]
        if details.get("last_name"):
            last_name = last_name or details["last_name"]
        for name_key in ("name", "user_name", "display_name"):
            candidate = (details.get(name_key) or "").strip()
            if not candidate:
                continue
            split_first, split_last = _split_person_name(candidate)
            first_name = first_name or split_first
            last_name = last_name or split_last
    return first_name, last_name

# This will be used to normalize the membership status.
def normalize_membership_status(status=None, deactivated=None):
    if deactivated:
        return "disabled"
    value = (status or "").strip().lower()
    if value in {"inactive", "disabled", "deactivated", "2", "deactivated trackvia user"}:
        return "disabled"
    if value in {"", "absent", "not found"}:
        return "absent"
    return "active"


# This will be used to get the platform fields.
def _platform_fields(platform, present, status=None, external_id=None, deactivated=None):
    membership = (
        "absent"
        if not present
        else normalize_membership_status(status, deactivated)
    )
    return {
        f"{platform}_present": 1 if present else 0,
        f"{platform}_status": status,
        f"{platform}_membership": membership,
        f"{platform}_external_id": external_id,
    }


# This will be used to convert the row to a dictionary
def _row_to_dict(row):
    if row is None:
        return None
    data = dict(row)
    platforms = {}
    for platform in PLATFORM_KEYS:
        platforms[platform] = {
            "label": PLATFORM_LABELS[platform],
            "present": bool(data.get(f"{platform}_present")),
            "status": data.get(f"{platform}_status"),
            "membership": data.get(f"{platform}_membership"),
            "external_id": data.get(f"{platform}_external_id"),
        }
    return {
        "email": data["email"],
        "environment": data["environment"],
        "first_name": data.get("first_name"),
        "last_name": data.get("last_name"),
        "display_name": " ".join(
            part for part in (data.get("first_name"), data.get("last_name")) if part
        ).strip()
        or None,
        "platforms": platforms,
        "synced_at": data.get("synced_at"),
        "last_action_at": data.get("last_action_at"),
        "last_action": data.get("last_action"),
    }


# This will be used to get the membership row
def _membership_row(conn, email, environment, platform):
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT present, status, external_id, details
        FROM platform_memberships
        WHERE environment = ? AND email = ? AND platform = ?
        """,
        (environment, email, platform),
    ).fetchone()


# This will be used to get the ACC from the cache.
def _acc_from_cache(acc_db_path, email):
    if not acc_db_path or not acc_db_path.exists():
        return None
    user = get_user_by_email(acc_db_path, email)
    if not user:
        return None
    return {
        "present": True,
        "status": user.get("status") or "active",
        "external_id": user.get("user_id"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
    }


# This will be used to rebuild the dictionary.
def rebuild_directory(environment=None, db_path=DB_PATH):
    """Rebuild the wide user directory from platform_memberships and ACC cache."""
    env = get_environment(environment)
    environment_key = env["key"]
    init_directory(db_path)
    synced_at = _utc_now()

    emails = set()
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT email
            FROM platform_memberships
            WHERE environment = ?
            """,
            (environment_key,),
        ).fetchall()
        emails.update(normalize_email(row[0]) for row in rows if row[0])

    if env["db_path"].exists():
        with sqlite3.connect(env["db_path"]) as conn:
            acc_rows = conn.execute(
                "SELECT email FROM users WHERE email IS NOT NULL AND email != ''"
            ).fetchall()
        emails.update(normalize_email(row[0]) for row in acc_rows if row[0])

    upserted = 0
    with sqlite3.connect(db_path) as conn:
        for email in sorted(emails):
            acc_cache = _acc_from_cache(env["db_path"], email)
            first_name = acc_cache.get("first_name") if acc_cache else None
            last_name = acc_cache.get("last_name") if acc_cache else None
            detail_first, detail_last = _membership_details_names(
                conn, email, environment_key
            )
            first_name = first_name or detail_first
            last_name = last_name or detail_last

            fields = {
                "email": email,
                "environment": environment_key,
                "first_name": first_name,
                "last_name": last_name,
                "synced_at": synced_at,
            }

            for platform in PLATFORM_KEYS:
                membership = _membership_row(conn, email, environment_key, platform)
                if membership:
                    details = None
                    if membership["details"]:
                        try:
                            details = json.loads(membership["details"])
                        except json.JSONDecodeError:
                            details = None
                    if platform == "acc" and details:
                        first_name = first_name or details.get("first_name")
                        last_name = last_name or details.get("last_name")
                    deactivated = None
                    if platform == "revizto" and membership["status"] == "deactivated":
                        deactivated = True
                    fields.update(
                        _platform_fields(
                            platform,
                            bool(membership["present"]),
                            status=membership["status"],
                            external_id=membership["external_id"],
                            deactivated=deactivated,
                        )
                    )
                elif platform == "acc" and acc_cache:
                    fields.update(
                        _platform_fields(
                            "acc",
                            True,
                            status=acc_cache["status"],
                            external_id=acc_cache["external_id"],
                        )
                    )
                    fields["first_name"] = first_name
                    fields["last_name"] = last_name
                else:
                    fields.update(_platform_fields(platform, False))

            columns = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            updates = ", ".join(
                f"{column} = excluded.{column}"
                for column in fields
                if column not in {"email", "environment"}
            )
            conn.execute(
                f"""
                INSERT INTO user_directory ({columns})
                VALUES ({placeholders})
                ON CONFLICT(email, environment) DO UPDATE SET
                    {updates}
                """,
                tuple(fields.values()),
            )
            upserted += 1
        conn.commit()

    return {
        "environment": environment_key,
        "user_count": upserted,
        "synced_at": synced_at,
    }


# This will be used to get the directory user.
def get_directory_user(email, environment=None, db_path=DB_PATH):
    env = get_environment(environment)
    init_directory(db_path)
    normalized = normalize_email(email)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT *
            FROM user_directory
            WHERE environment = ? AND email = ?
            """,
            (env["key"], normalized),
        ).fetchone()
    return _row_to_dict(row)



# This will be used to search the directory.
def search_directory(query="", environment=None, limit=50, offset=0, db_path=DB_PATH):
    env = get_environment(environment)
    init_directory(db_path)
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))

    clauses = ["environment = ?"]
    params = [env["key"]]
    term = (query or "").strip()
    if term:
        like = f"%{term}%"
        clauses.append(
            """
            (
                LOWER(email) LIKE LOWER(?)
                OR LOWER(COALESCE(first_name, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(last_name, '')) LIKE LOWER(?)
                OR LOWER(TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, ''))) LIKE LOWER(?)
            )
            """
        )
        params.extend([like, like, like, like])

    where_sql = " AND ".join(clauses)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        total = conn.execute(
            f"SELECT COUNT(*) FROM user_directory WHERE {where_sql}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT *
            FROM user_directory
            WHERE {where_sql}
            ORDER BY email
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()

    return {
        "environment": env["key"],
        "query": term or None,
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": [_row_to_dict(row) for row in rows],
    }


# This will be used to get the directory stats.
def get_directory_stats(environment=None, db_path=DB_PATH):
    env = get_environment(environment)
    init_directory(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT COUNT(*) AS user_count, MAX(synced_at) AS last_synced_at
            FROM user_directory
            WHERE environment = ?
            """,
            (env["key"],),
        ).fetchone()
    return {
        "environment": env["key"],
        "user_count": row["user_count"] if row else 0,
        "last_synced_at": row["last_synced_at"] if row else None,
    }



# This will be used to ensure the row exists.
def _ensure_row(conn, email, environment):
    conn.execute(
        """
        INSERT INTO user_directory (email, environment)
        VALUES (?, ?)
        ON CONFLICT(email, environment) DO NOTHING
        """,
        (email, environment),
    )


# This will be used to update the platform in the directory.
def update_platform_in_directory(
    email,
    environment,
    platform,
    *,
    present,
    status=None,
    external_id=None,
    deactivated=None,
    db_path=DB_PATH,
):
    init_directory(db_path)
    normalized = normalize_email(email)
    fields = _platform_fields(
        platform, present, status=status, external_id=external_id, deactivated=deactivated
    )
    assignments = ", ".join(f"{key} = ?" for key in fields)
    with sqlite3.connect(db_path) as conn:
        _ensure_row(conn, normalized, environment)
        conn.execute(
            f"""
            UPDATE user_directory
            SET {assignments}
            WHERE email = ? AND environment = ?
            """,
            (*fields.values(), normalized, environment),
        )
        conn.commit()


# This will be used to apply the action to the directory.
def apply_action_to_directory(email, environment, action, action_body, db_path=DB_PATH):
    """Patch directory rows after disable/activate based on API results."""
    if not email or not environment:
        return

    normalized = normalize_email(email)
    init_directory(db_path)
    now = _utc_now()
    verb = "disable" if action == "disable" else "activate"

    with sqlite3.connect(db_path) as conn:
        _ensure_row(conn, normalized, environment)

    if action_body.get("acc") and not action_body.get("acc_error"):
        update_platform_in_directory(
            normalized,
            environment,
            "acc",
            present=True,
            status="inactive" if verb == "disable" else "active",
            external_id=(action_body.get("acc") or {}).get("user_id"),
            db_path=db_path,
        )

    stratus = action_body.get("stratus") or {}
    if stratus.get("count") and not action_body.get("stratus_error"):
        update_platform_in_directory(
            normalized,
            environment,
            "stratus",
            present=True,
            status="Disabled" if verb == "disable" else "Active",
            db_path=db_path,
        )

    if action_body.get("revizto") and not action_body.get("revizto_error"):
        member = (action_body.get("revizto") or {}).get("member") or {}
        update_platform_in_directory(
            normalized,
            environment,
            "revizto",
            present=True,
            status="deactivated" if verb == "disable" else "active",
            external_id=member.get("member_uuid"),
            deactivated=verb == "disable",
            db_path=db_path,
        )

    if action_body.get("trackvia") and not action_body.get("trackvia_error"):
        trackvia = action_body["trackvia"]
        update_platform_in_directory(
            normalized,
            environment,
            "trackvia",
            present=True,
            status=trackvia.get("status")
            or ("Deactivated TrackVia User" if verb == "disable" else "Existing TrackVia User"),
            external_id=trackvia.get("record_id"),
            db_path=db_path,
        )

    if action_body.get("openspace") and not action_body.get("openspace_error"):
        if verb == "disable":
            update_platform_in_directory(
                normalized,
                environment,
                "openspace",
                present=False,
                status="removed",
                db_path=db_path,
            )

    if action_body.get("symetri") and not action_body.get("symetri_error"):
        if verb == "disable":
            update_platform_in_directory(
                normalized,
                environment,
                "symetri",
                present=False,
                status="removed",
                db_path=db_path,
            )

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE user_directory
            SET last_action_at = ?, last_action = ?
            WHERE email = ? AND environment = ?
            """,
            (now, verb, normalized, environment),
        )
        conn.commit()
