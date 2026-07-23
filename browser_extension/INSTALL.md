# Install the Session Sync extension (Chrome or Edge)

## Blocked by company policy?

UMCI (and most companies) **block "Load unpacked" extensions** in Chrome/Edge. That is not a bug in this project — IT controls that policy.

**Use the scripts instead (no extension needed):**

| Task | Double-click this file |
|---|---|
| Stratus Production | `scripts\connect-stratus-prod.bat` |
| Stratus Dev | `scripts\connect-stratus-dev.bat` |
| Revizto | `scripts\connect-revizto.bat` |

Edit `SERVER_URL` at the top of each `.bat` if the app is hosted somewhere other than `http://127.0.0.1:5000`.

You still need `SESSION_ADMIN_KEY` in the server `.env` (Part 1 below).

---

This extension lets **any IT person on any PC** refresh Stratus/Revizto sessions on the shared server. Everyone else just uses the website normally.

**Only try the extension if** `chrome://extensions` → Developer mode is not greyed out / blocked.

## Part 1 — One-time server setup (IT admin)

1. Open the server `.env` file for User Disabling Platform.

2. Add a secret key (generate one):

```powershell
cd h:\coding\user_disabling_platform
.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(32))"
```

3. Put the result in `.env`:

```
SESSION_ADMIN_KEY=paste-the-generated-key-here
```

4. Restart the app (`python app.py` or your Windows Service).

## Part 2 — Install the extension (each IT person, once)

Works in **Google Chrome** and **Microsoft Edge**.

1. Open the browser.

2. Go to extensions:
   - **Chrome:** `chrome://extensions`
   - **Edge:** `edge://extensions`

3. Turn on **Developer mode** (toggle in the top-right).

4. Click **Load unpacked**.

5. Select this folder:

```
h:\coding\user_disabling_platform\browser_extension
```

6. Pin the extension:
   - Click the puzzle-piece icon in the toolbar
   - Pin **UMCI Session Sync**

## Part 3 — Configure the extension (each IT person, once)

1. Click the **UMCI Session Sync** extension icon.

2. Click **Extension settings**.

3. Set:
   - **App server URL** — e.g. `http://192.168.1.50:5000` or `http://127.0.0.1:5000`
   - **SESSION_ADMIN_KEY** — same value as in the server `.env`

4. Click **Test connection** — you should see “Extension connection OK.”

5. Click **Save**.

## Part 4 — When a session expires (2 minutes)

From the User Disabling Platform website, click **Fix connection** on the yellow Stratus or Revizto panel.

Or do it manually:

### Stratus

1. Extension → **Open Stratus login** → sign in
2. Extension → **Push Stratus (Production)** or **Push Stratus (Dev)**
3. Refresh the app — Stratus should be green

### Revizto

1. Extension → **Open Revizto login** → sign in
2. Extension → **Push Revizto**
3. Refresh the app — Revizto should be green

## Troubleshooting

| Problem | Fix |
|---|---|
| “Set SESSION_ADMIN_KEY in settings” | Complete Part 1 and Part 3 |
| “Invalid SESSION_ADMIN_KEY” | Key in extension must exactly match server `.env` |
| “Sign-in does not look complete” | Finish logging in before pushing |
| “Server error (401)” | Wrong admin key |
| “Server error (503)” | `SESSION_ADMIN_KEY` missing on server |
| Extension not listed after load | Make sure you selected the `browser_extension` folder itself |

## Sharing with the team

- **HR / managers:** only need the website URL — no extension.
- **IT (1–2 people):** install the extension on their own PCs.
- **Server:** hosts the app and `.env` — cookies live on the server, not on each user’s PC.

## Optional: pre-fill extension settings from the app

Open extension settings with the server URL filled in:

```
chrome-extension://<extension-id>/options.html?server=http://YOUR-SERVER:5000
```

(You can find the extension ID on `chrome://extensions` after loading it.)
