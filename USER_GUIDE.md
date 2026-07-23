# User Disabling Platform — Operator Guide

How to run and use the app day to day. For GitHub setup / teammate install, see [README.md](README.md).

---

## What this app does

It helps IT disable (or reactivate) a person’s access across company platforms from one place:

| Platform | What disable does |
|---|---|
| **Autodesk ACC** | Disables the user in the selected ACC account (Dev Hub or Production) |
| **GTP Stratus** | Moves them toward former-employee / inactive (group, role, status) |
| **Revizto** | Deactivates their license membership |
| **TrackVia** | Marks them deactivated in the roster view |
| **OpenSpace** | Removes them from the organization (not reversible here) |
| **Symetri** | Removes them from the company account (not reversible here) |
| **PlanGrid** | Shown in status / membership; removal uses Admin Console session |

**Activate** reverses disable where the platform supports it (ACC, Stratus, Revizto, TrackVia). OpenSpace and Symetri removals are not undone from this app.

---

## Start the app

1. Open the project folder.
2. Double-click **`scripts\run-app.bat`**.
3. In your browser go to **http://127.0.0.1:5000**.

Leave the terminal/window open while you use the app. Close it (or Ctrl+C) to stop.

First time on a PC? Use **`scripts\setup.bat`**, then put the vault `.env` next to `app.py` (see README).

Optional check: double-click **`scripts\smoke-test.bat`** — green/OK means connections work; FAIL usually means reconnect a session.

---

## The screen at a glance

### 1. Environment toggle (top right)

- **Dev Hub** — safer for testing (ACC + Stratus Dev).
- **Production** — real company accounts.

Always confirm this before you disable anyone.

### 2. Platform status panels

Each platform shows whether this PC can talk to it right now:

- Green / connected → ready  
- Yellow / failed → session expired or not configured  

**Sync from Autodesk** — pulls ACC projects/users into the local database (needed on a new PC, or when the list looks stale).

**Fix connection** / **Reconnect** — appears when Stratus, Revizto, or Symetri need a fresh login. Prefer the `scripts\connect-*.bat` files on managed PCs.

### 3. Platform membership (lookup)

Use this to **see where someone exists** before you change anything.

1. Type a **name or email**.
2. Click **Look up platforms**.
3. Review which platforms show them as present.

**Sync all platforms** refreshes the local membership registry (can take a while). Do this occasionally, not before every single lookup.

### 4. Disable or activate (action card)

This is separate from lookup — it **changes** access.

1. Enter the person’s **email**.
2. Confirm **Dev Hub** vs **Production**.
3. Click **Disable account** or **Activate account**.
4. Read the message under the buttons — it lists what each platform did (or skipped).

OpenSpace / Symetri: disable path **removes** the user; you cannot reverse that from this UI.

---

## Typical workflows

### Offboard someone (production)

1. Start the app → open http://127.0.0.1:5000  
2. Set toggle to **Production**.  
3. Confirm status panels look healthy (reconnect if needed).  
4. **Look up platforms** with their email — confirm you have the right person.  
5. Paste the same email under **Disable or activate**.  
6. Click **Disable account**.  
7. Keep the result message for your ticket / notes.  

### Test safely

1. Use **Dev Hub**.  
2. Look up a known test account.  
3. Disable, then Activate, and confirm panels/messages look right.  

### Fix a disconnected platform

| Platform | What to do |
|---|---|
| Stratus Production | Double-click `scripts\connect-stratus-prod.bat` and sign in |
| Stratus Dev | `scripts\connect-stratus-dev.bat` |
| Revizto | `scripts\connect-revizto.bat` (or use Reconnect / access code in the UI) |
| Symetri | `scripts\connect-symetri.bat` or paste a fresh bearer token in Reconnect |
| TrackVia / API keys | Usually fixed by updating `.env` from the vault (not a daily login) |
| ACC | Needs `AUTODESK_CLIENT_ID` / `SECRET` in `.env`; then Sync from Autodesk |

After reconnecting, refresh the page or click **Check connection** if a dialog is open.

---

## Important warnings

- **Production disables real accounts.** Double-check email and environment.  
- **OpenSpace and Symetri remove users** — not a soft disable you can flip back here.  
- **Sessions expire** (especially Stratus, Revizto, Symetri). That does not mean the app is broken; reconnect and continue.  
- **Never commit `.env`** or share it in Slack/email. Use the password vault.  
- Do not run the old `test_*_disable.py` scripts unless you intend to change a real test account.

---

## Quick reference

| Task | Action |
|---|---|
| Start | `scripts\run-app.bat` → http://127.0.0.1:5000 |
| Check connections | `scripts\smoke-test.bat` |
| First-time PC setup | `scripts\setup.bat` + vault `.env` |
| Refresh ACC users | **Sync from Autodesk** |
| Refresh membership cache | **Sync all platforms** |
| See where a user lives | **Look up platforms** |
| Offboard | Production → Disable account |
| Re-enable (supported platforms) | Activate account |
| Get code updates | `git pull` in the project folder |

---

## Need install / GitHub help?

See **[README.md](README.md)** — Part A (push to GitHub), Part B (teammate install), and troubleshooting (Egnyte / dubious ownership).
