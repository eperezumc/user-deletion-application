const SYNC_PARAM = "umci_session_sync";

function readAuth0AccessToken() {
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
}

function shouldSync() {
  return (
    window.__umciSymetriSyncArmed === true ||
    new URLSearchParams(window.location.search).has(SYNC_PARAM)
  );
}

function maybePushToken() {
  if (!shouldSync()) {
    return;
  }
  const token = readAuth0AccessToken();
  if (!token) {
    return;
  }
  chrome.runtime.sendMessage({ type: "symetri-push-token", token }, (response) => {
    if (chrome.runtime.lastError || !response?.ok) {
      return;
    }
    window.__umciSymetriSyncArmed = false;
    const params = new URLSearchParams(window.location.search);
    params.delete(SYNC_PARAM);
    const next = `${window.location.pathname}${params.toString() ? `?${params}` : ""}`;
    window.history.replaceState({}, "", next);
  });
}

if (new URLSearchParams(window.location.search).has(SYNC_PARAM)) {
  window.__umciSymetriSyncArmed = true;
}

window.addEventListener("umci-symetri-sync-arm", () => {
  window.__umciSymetriSyncArmed = true;
  maybePushToken();
});

setInterval(maybePushToken, 1500);
maybePushToken();
