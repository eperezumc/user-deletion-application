from pathlib import Path
import os
import re
import threading

from dotenv import load_dotenv, set_key

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"
_env_lock = threading.Lock()
_ENV_KEY_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=")
load_dotenv(ENV_PATH)


def reload_env():
    """Re-read .env so edits apply without restarting the server."""
    with _env_lock:
        load_dotenv(ENV_PATH, override=True)


def env_value(key, default=""):
    """Read one env value after reload, stripping optional quotes."""
    with _env_lock:
        load_dotenv(ENV_PATH, override=True)
        value = (os.getenv(key) or default).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1].strip()
    return value


def _quote_env_value(value):
    value = "" if value is None else str(value)
    if value == "":
        return "''"
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _write_env_keys_direct(updates):
    """Update .env in place — for network drives that block dotenv atomic rename."""
    path = Path(ENV_PATH)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    new_lines = []

    for line in lines:
        match = _ENV_KEY_PATTERN.match(line.strip())
        if match and match.group(1) in remaining:
            key = match.group(1)
            new_lines.append(f"{key}={_quote_env_value(remaining.pop(key))}")
        else:
            new_lines.append(line)

    for key, value in remaining.items():
        new_lines.append(f"{key}={_quote_env_value(value)}")

    text = "\n".join(new_lines)
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def set_env_key(key, value):
    """Persist one key to .env (Egnyte-safe fallback)."""
    set_env_keys({key: value})


def _env_on_network_drive():
    path = str(ENV_PATH)
    return path.startswith("\\\\") or "egnytedrive" in path.lower()


def set_env_keys(updates):
    """Persist multiple keys to .env."""
    if not updates:
        return

    with _env_lock:
        if _env_on_network_drive():
            _write_env_keys_direct(updates)
        else:
            try:
                for key, value in updates.items():
                    set_key(str(ENV_PATH), key, value)
            except (PermissionError, OSError):
                _write_env_keys_direct(updates)
        load_dotenv(ENV_PATH, override=True)