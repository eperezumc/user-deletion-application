async function pushSymetriToken(token) {
  const settings = await chrome.storage.sync.get({
    serverUrl: "http://127.0.0.1:5000",
    adminKey: "",
  });
  if (!settings.adminKey) {
    throw new Error("Open extension settings and set SESSION_ADMIN_KEY first.");
  }

  const response = await fetch(
    `${settings.serverUrl.replace(/\/$/, "")}/api/admin/sessions/symetri`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-Admin-Key": settings.adminKey,
      },
      body: JSON.stringify({ bearer_token: token, validate: true }),
    }
  );
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

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "open-tab" && message.url) {
    chrome.tabs.create({ url: message.url });
    sendResponse({ ok: true });
    return;
  }
  if (message?.type === "open-options") {
    chrome.runtime.openOptionsPage();
    sendResponse({ ok: true });
    return;
  }
  if (message?.type === "symetri-push-token" && message.token) {
    pushSymetriToken(message.token)
      .then((data) => sendResponse({ ok: true, data }))
      .catch((error) => sendResponse({ ok: false, error: error.message || String(error) }));
    return true;
  }
  return false;
});
