# User Disabling Platform

Internal IT tool: search a user and disable them across connected services (ACC, Stratus, Revizto, TrackVia, OpenSpace, Symetri, PlanGrid).

**How we use it:** there is no shared server deploy. Each person clones this repo, puts a `.env` on their PC, and runs the app locally.

---

## Part A — You (first time on GitHub)

Do this once so the team can clone the code. Secrets never go to GitHub.

### 1. Put secrets somewhere safe (not GitHub)

1. Copy your working `.env` file (the one next to `app.py`).
2. Store it in **1Password / IT vault** as something like `User Disabling Platform — .env`.
3. Share vault access with the IT people who will run this tool.

That file is what makes the app work on their machines. GitHub only has the code.

### 2. Confirm nothing secret will be committed

This repo already has a `.gitignore` that blocks:

- `.env` (secrets)
- `.venv/` (Python install)
- `*.db` (local user databases)

Safe to commit: code, `scripts/`, `.env.example`, `README.md`, `browser_extension/`.

### 3. Create the repo and push (private)

In PowerShell, from the project folder:

```powershell
cd h:\coding\user_disabling_platform

git init
git add .
git status
```

**Stop and check:** `.env` must **not** appear in the staged files. You should see `.gitignore` and `.env.example`. If `.env` is listed, do not commit — fix `.gitignore` first.

#### If you see `fatal: detected dubious ownership`

This happens when the project lives on a network / Egnyte drive (`//EgnyteDrive/...`). Git blocks it until you mark the folder as safe. Run **once** on your PC:

```powershell
git config --global --add safe.directory "%(prefix)///EgnyteDrive/Private/coding/user_disabling_platform"
```

Then retry your `git` command. (Use the exact path from the error message if yours differs.)

**Also:** the commit flag is `-m` with **no space** — use `git commit -m "message"`, not `git commit - m "message"`.

Then:

```powershell
git commit -m "Initial commit of user disabling platform"

# Option 1 — GitHub CLI (creates a PRIVATE repo and pushes)
gh repo create user_disabling_platform --private --source=. --remote=origin --push

# Option 2 — manual: create an empty PRIVATE repo on github.com, then:
# git remote add origin https://github.com/YOUR_ORG/user_disabling_platform.git
# git branch -M main
# git push -u origin main
```

Use a **private** repo.

### 4. Tell the team

Send them:

1. The GitHub repo URL  
2. Access to the vault `.env`  
3. The **Part B** steps below  

---

## Part B — Teammates (install on your PC)

### Requirements

- Windows PC  
- [Python 3.11+](https://www.python.org/downloads/) installed (check **“Add python.exe to PATH”** during install)  
- Access to this private GitHub repo  
- The shared `.env` from the password vault  

### Install (about 5–10 minutes)

1. Clone the repo (GitHub Desktop, or):

   ```powershell
   git clone https://github.com/YOUR_ORG/user_disabling_platform.git
   cd user_disabling_platform
   ```

2. Double-click **`scripts\setup.bat`**  
   - Creates `.venv`  
   - Installs packages  
   - Creates a blank `.env` from the example if you don’t have one yet  

3. **Replace `.env` with the vault file**  
   - Download the shared `.env` from 1Password / IT vault  
   - Put it in the project folder (same place as `app.py`)  
   - Overwrite the blank one if setup created it  
   - Never commit this file  

4. Double-click **`scripts\run-app.bat`**

5. Open **http://127.0.0.1:5000** in your browser  

6. If the user list is empty, use **Sync from Autodesk** in the UI (first run only, or when you need fresh ACC data).

### Verify it works (safe smoke test)

After setup + vault `.env`, double-click **`scripts\smoke-test.bat`**.

This only checks connections. It does **not** disable anyone.

- **OK / SKIP** = fine on this machine  
- **FAIL** on a platform = usually an expired session → run the matching `scripts\connect-*.bat`  

Or from a terminal:

```powershell
.\.venv\Scripts\python test_smoke.py
```

You can also start the app and watch the platform status panels in the UI (green = connected).

> Do **not** use `test_stratus_disable.py`, `test_symetri.py`, etc. for this — those can change real accounts.

### Day to day

| Task | What to do |
|---|---|
| Start the app | Double-click `scripts\run-app.bat` → http://127.0.0.1:5000 |
| Pull code updates | `git pull` in the project folder, then run the app again |
| Check connections | Double-click `scripts\smoke-test.bat` |
| Stratus / Revizto / Symetri shows disconnected | Double-click the matching `scripts\connect-*.bat`, sign in when the browser opens |
| ACC list looks stale | Click **Sync from Autodesk** in the UI |

### Will it work on my machine?

Yes. Same code + same `.env` = same app. Nothing is tied to one person’s PC.

- **API keys / account IDs** in `.env` work from any machine.  
- **Session cookies** expire over time — that’s normal. Use the `connect-*.bat` scripts to refresh them.  
- **User databases** start empty on a new PC until you sync.  

---

## Environments

The UI toggle switches between **Dev Hub** and **Production**:

| Environment | Database | Account env var |
|---|---|---|
| Dev Hub | `acc_dev_users.db` | `AUTODESK_DEV_ACCOUNT_ID` |
| Production | `acc_users.db` | `AUTODESK_PROD_ACCOUNT_ID` |

Search, sync, and disable all respect the selected environment.

## Sync ACC (optional CLI)

```powershell
.\.venv\Scripts\python sync_acc.py --environment dev
.\.venv\Scripts\python sync_acc.py --environment prod
```

If Autodesk sync fails with an auth error, set `AUTODESK_IMPERSONATION_USER_ID` in `.env`.

## Manual setup (if you skip setup.bat)

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Then replace .env with the vault file
python app.py
```

## Browser extension (optional)

Most people do **not** need this. Prefer `scripts\connect-*.bat`.

If company policy allows unpacked extensions, see `browser_extension\INSTALL.md`.

## Do not commit

- `.env`  
- `.venv/`  
- `*.db`  

If `git status` ever shows `.env`, unstage it and make sure it stays gitignored.
