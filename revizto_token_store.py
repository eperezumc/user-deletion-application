"""Local Revizto OAuth token cache (avoids Egnyte .env write failures)."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

STORE_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "user_disabling_platform"
TOKEN_FILE = STORE_DIR / "revizto_oauth.json"

# This will be used to store the Revizto tokens.
TOKEN_FIELDS = (
    ("access_token", "REVIZTO_ACCESS_TOKEN"),
    ("refresh_code", "REVIZTO_REFRESH_CODE"),
    ("access_token_expires_at", "REVIZTO_ACCESS_TOKEN_EXPIRES_AT"),
    ("tokens_updated_at", "REVIZTO_TOKENS_UPDATED_AT"),
)

# This will be used to load the Revizto tokens.
def load_tokens():
    if not TOKEN_FILE.exists():
        return None
    try:
        data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None

# This will be used to save the Revizto tokens.
def save_tokens(
    access_token,
    refresh_code,
    access_token_expires_at,
    tokens_updated_at=None,
):
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "access_token": access_token,
        "refresh_code": refresh_code,
        "access_token_expires_at": access_token_expires_at,
        "tokens_updated_at": tokens_updated_at or datetime.now(timezone.utc).isoformat(),
    }
    tmp_path = TOKEN_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(TOKEN_FILE)
    return payload


# This will be used to hydrate the Revizto environment.
def hydrate_revizto_env():
    """Load cached tokens into os.environ when present."""
    data = load_tokens()
    if not data:
        return False
    for field, env_key in TOKEN_FIELDS:
        value = data.get(field)
        if value is not None and str(value).strip():
            os.environ[env_key] = str(value)
    os.environ.pop("REVIZTO_REFRESH_TOKEN", None)
    return True


def store_path():
    return str(TOKEN_FILE)
