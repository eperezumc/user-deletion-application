const statusEl = document.getElementById("status");

const STRATUS_URL = "https://www.gtpstratus.com/";
const REVIZTO_URL = "https://ws.revizto.com/";
const SYMETRI_URL = "https://my.symetri.com/?umci_session_sync=1";

const STRATUS_COOKIE_NAMES = new Set([
  "GTPUserCompany",
  ".AspNetCore.Cookies.v2.Production",
  ".AspNetCore.Cookies.v2.ProductionC1",
]);

function cookieValue(cookies, key) {
  const match = cookies.find((cookie) => cookie.name === key);
  return match?.value || "";
}

function cookieHasNamePrefix(cookies, prefix) {
  return cookies.some((cookie) => cookie.name.startsWith(prefix));
}

function setStatus(text, ok) {
  statusEl.textContent = text;
  statusEl.className = ok === true ? "ok" : ok === false ? "err" : "";
}

async function getSettings() {
  return chrome.storage.sync.get({
    serverUrl: "http://127.0.0.1:5000",
    adminKey: "",
  });
}

function cookieHeader(cookies) {
  return cookies.map((cookie) => `${cookie.name}=${cookie.value}`).join("; ");
}

function hasSessionCookies(platform, cookies) {
  if (platform === "revizto") {
    return (
      Boolean(cookieValue(cookies, "w_key")) &&
      Boolean(cookieValue(cookies, "ssoKey")) &&
      cookieValue(cookies, "lastAuth") === "login" &&
      cookieHasNamePrefix(cookies, "currentAccountUuid_")
    );
  }

  const names = new Set(cookies.map((cookie) => cookie.name));
  for (const name of STRATUS_COOKIE_NAMES) {
    if (names.has(name)) {
      return true;
    }
  }
  return false;
}

async function pushSession({ platform, path, payload, loginUrl }) {
  const settings = await getSettings();
  if (!settings.adminKey) {
    throw new Error("Open extension settings and set SESSION_ADMIN_KEY first.");
  }

  const cookies = await chrome.cookies.getAll({ url: loginUrl });
  if (!cookies.length) {
    throw new Error(`Sign in at ${loginUrl} first, then push again.`);
  }
  if (!hasSessionCookies(platform, cookies)) {
    throw new Error("Sign-in is not complete yet. Finish logging in, then push again.");
  }

  setStatus("Sending session to server...", null);
  const response = await fetch(`${settings.serverUrl.replace(/\/$/, "")}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Admin-Key": settings.adminKey,
    },
    body: JSON.stringify({ ...payload, cookie: cookieHeader(cookies) }),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `Server error (${response.status})`);
  }

  chrome.tabs.query({}, (tabs) => {
    for (const tab of tabs) {
      if (!tab.id || !tab.url) {
        continue;
      }
      try {
        const tabOrigin = new URL(tab.url).origin;
        const serverOrigin = new URL(settings.serverUrl).origin;
        if (tabOrigin === serverOrigin) {
          chrome.tabs.sendMessage(tab.id, {
            type: "session-sync-pushed",
            detail: data,
          }).catch(() => {});
        }
      } catch (_error) {
        // Ignore tabs with non-http URLs.
      }
    }
  });

  return data;
}

function openLogin(url) {
  chrome.tabs.create({ url });
}

async function runPush(config) {
  try {
    const data = await pushSession(config);
    setStatus(data.message || "Session updated on server.", true);
  } catch (error) {
    setStatus(error.message || String(error), false);
  }
}

document.getElementById("open-stratus").addEventListener("click", () => {
  openLogin(STRATUS_URL);
  setStatus("Stratus opened — sign in, then click Push Stratus below.", null);
});

document.getElementById("stratus-prod").addEventListener("click", () => {
  runPush({
    platform: "stratus",
    path: "/api/admin/sessions/stratus",
    payload: { environment: "prod", validate: true },
    loginUrl: STRATUS_URL,
  });
});

document.getElementById("stratus-dev").addEventListener("click", () => {
  runPush({
    platform: "stratus",
    path: "/api/admin/sessions/stratus",
    payload: { environment: "dev", validate: true },
    loginUrl: STRATUS_URL,
  });
});

document.getElementById("open-revizto").addEventListener("click", () => {
  openLogin(REVIZTO_URL);
  setStatus("Revizto opened — sign in, then click Push Revizto below.", null);
});

document.getElementById("revizto").addEventListener("click", () => {
  runPush({
    platform: "revizto",
    path: "/api/admin/sessions/revizto",
    payload: { validate: true },
    loginUrl: REVIZTO_URL,
  });
});

async function readSymetriTokenFromTab(tabId) {
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      for (let index = 0; index < localStorage.length; index += 1) {
        const key = localStorage.key(index);
        if (!key || !key.includes("auth0spajs")) {
          continue;
        }
        try {
          const item = JSON.parse(localStorage.getItem(key));
          const body = item?.body || item;
          const token = body?.access_token;
          if (typeof token === "string" && token.split(".").length === 3) {
            return token;
          }
        } catch (_error) {
          // Ignore malformed cache entries.
        }
      }
      return null;
    },
  });
  return result || null;
}

async function pushSymetriToken() {
  const settings = await getSettings();
  if (!settings.adminKey) {
    throw new Error("Open extension settings and set SESSION_ADMIN_KEY first.");
  }

  setStatus("Looking for Symetri sign-in...", null);
  const tabs = await chrome.tabs.query({ url: "https://my.symetri.com/*" });
  let targetTab = tabs[0];
  if (!targetTab) {
    await chrome.tabs.create({ url: SYMETRI_URL });
    throw new Error("Symetri opened — sign in, then click Push Symetri token again.");
  }

  const token = await readSymetriTokenFromTab(targetTab.id);
  if (!token) {
    await chrome.tabs.update(targetTab.id, { url: SYMETRI_URL });
    throw new Error("Sign-in is not complete yet. Finish logging into my.symetri.com, then push again.");
  }

  setStatus("Sending Symetri token to server...", null);
  const response = await fetch(`${settings.serverUrl.replace(/\/$/, "")}/api/admin/sessions/symetri`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Admin-Key": settings.adminKey,
    },
    body: JSON.stringify({ bearer_token: token, validate: true }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `Server error (${response.status})`);
  }

  chrome.tabs.query({}, (allTabs) => {
    for (const tab of allTabs) {
      if (!tab.id || !tab.url) {
        continue;
      }
      try {
        const tabOrigin = new URL(tab.url).origin;
        const serverOrigin = new URL(settings.serverUrl).origin;
        if (tabOrigin === serverOrigin) {
          chrome.tabs.sendMessage(tab.id, {
            type: "session-sync-pushed",
            detail: data,
          }).catch(() => {});
        }
      } catch (_error) {
        // Ignore tabs with non-http URLs.
      }
    }
  });

  return data;
}

document.getElementById("open-symetri").addEventListener("click", () => {
  openLogin(SYMETRI_URL);
  setStatus("Symetri opened — sign in, then click Push Symetri below.", null);
});

document.getElementById("symetri").addEventListener("click", async () => {
  try {
    const data = await pushSymetriToken();
    setStatus(data.message || "Symetri token updated on server.", true);
  } catch (error) {
    setStatus(error.message || String(error), false);
  }
});

getSettings().then((settings) => {
  if (!settings.adminKey) {
    setStatus("Configure server URL and SESSION_ADMIN_KEY in settings first.", false);
  }
});
