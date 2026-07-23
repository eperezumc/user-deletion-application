"""Local SQLite registry of which users exist on each platform."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from env_loader import PROJECT_ROOT

# This will be used to store the platform membership data.
DB_PATH = PROJECT_ROOT / "platform_membership.db"

PLATFORM_KEYS = ("acc", "stratus", "revizto", "trackvia", "openspace", "symetri")

PLATFORM_LABELS = {
    "acc": "Autodesk ACC",
    "stratus": "GTP Stratus",
    "revizto": "Revizto",
    "trackvia": "TrackVia",
    "openspace": "OpenSpace",
    "symetri": "Symetri",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS platform_memberships (
    email TEXT NOT NULL COLLATE NOCASE,
    platform TEXT NOT NULL,
    environment TEXT NOT NULL,
    present INTEGER NOT NULL DEFAULT 0,
    status TEXT,
    external_id TEXT,
    details TEXT,
    synced_at TEXT NOT NULL,
    PRIMARY KEY (email, platform, environment)
);

CREATE INDEX IF NOT EXISTS idx_memberships_email_env
    ON platform_memberships(environment, email);

CREATE TABLE IF NOT EXISTS platform_sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    environment TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    user_count INTEGER DEFAULT 0,
    error TEXT
);
"""

# This will be used to normalize the email
def normalize_email(email):
    return email.strip().lower()


# This will be used to get the current UTC time
def _utc_now():
    return datetime.now(timezone.utc).isoformat()


# This will be used to initialize the database
def init_db(db_path=DB_PATH):
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)


# This will be used to upsert the membership
def upsert_membership(
    email,
    platform,
    environment,
    present,
    status=None,
    external_id=None,
    details=None,
    synced_at=None,
    db_path=DB_PATH,
):
    init_db(db_path)
    synced_at = synced_at or _utc_now()
    details_json = json.dumps(details) if details is not None else None
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO platform_memberships (
                email, platform, environment, present, status, external_id, details, synced_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email, platform, environment) DO UPDATE SET
                present = excluded.present,
                status = excluded.status,
                external_id = excluded.external_id,
                details = excluded.details,
                synced_at = excluded.synced_at
            """,
            (
                normalize_email(email),
                platform,
                environment,
                1 if present else 0,
                status,
                external_id,
                details_json,
                synced_at,
            ),
        )
        conn.commit()

# This will be used to lookup the email in the cache.
def lookup_email_in_cache(email, environment, db_path=DB_PATH):
    """Return platform membership rows for one email from the local registry."""
    if not db_path.exists():
        return {}

    normalized = normalize_email(email)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT platform, present, status, external_id, details, synced_at
            FROM platform_memberships
            WHERE environment = ? AND email = ?
            """,
            (environment, normalized),
        ).fetchall()

    result = {}
    for row in rows:
        details = None
        if row["details"]:
            try:
                details = json.loads(row["details"])
            except json.JSONDecodeError:
                details = row["details"]
        result[row["platform"]] = {
            "present": bool(row["present"]),
            "status": row["status"],
            "external_id": row["external_id"],
            "details": details,
            "synced_at": row["synced_at"],
            "configured": True,
            "label": PLATFORM_LABELS.get(row["platform"], row["platform"]),
        }
    return result

# This will be used to get the sync status
def get_sync_status(environment, db_path=DB_PATH):
    if not db_path.exists():
        return {
            "environment": environment,
            "synced": False,
            "user_count": 0,
            "last_sync": None,
            "last_status": None,
        }

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        user_count = conn.execute(
            """
            SELECT COUNT(DISTINCT email)
            FROM platform_memberships
            WHERE environment = ? AND present = 1
            """,
            (environment,),
        ).fetchone()[0]
        last_run = conn.execute(
            """
            SELECT started_at, finished_at, status, user_count, error
            FROM platform_sync_runs
            WHERE environment = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (environment,),
        ).fetchone()

    return {
        "environment": environment,
        "synced": user_count > 0,
        "user_count": user_count,
        "last_sync": last_run["finished_at"] if last_run else None,
        "last_status": last_run["status"] if last_run else None,
        "last_error": last_run["error"] if last_run else None,
    }


# This will be used to record the sync start
def record_sync_start(environment, db_path=DB_PATH):
    init_db(db_path)
    started_at = _utc_now()
    with sqlite3.connect(db_path) as conn:
        run_id = conn.execute(
            """
            INSERT INTO platform_sync_runs (environment, started_at, status)
            VALUES (?, ?, 'running')
            """,
            (environment, started_at),
        ).lastrowid
        conn.commit()
    return run_id



# This will be used to record the sync finis
def record_sync_finish(run_id, environment, user_count, error=None, db_path=DB_PATH):
    status = "error" if error else "success"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE platform_sync_runs
            SET finished_at = ?, status = ?, user_count = ?, error = ?
            WHERE id = ?
            """,
            (_utc_now(), status, user_count, error, run_id),
        )
        conn.commit()
