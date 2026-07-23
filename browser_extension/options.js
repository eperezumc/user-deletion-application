const serverUrlInput = document.getElementById("serverUrl");
const adminKeyInput = document.getElementById("adminKey");
const savedEl = document.getElementById("saved");
const statusEl = document.getElementById("status");

function setStatus(text, ok) {
  statusEl.textContent = text;
  statusEl.className = ok === true ? "ok" : ok === false ? "err" : "";
}

async function loadDefaults() {
  const params = new URLSearchParams(window.location.search);
  const defaults = await chrome.storage.sync.get({
    serverUrl: params.get("server") || "http://127.0.0.1:5000",
    adminKey: "",
  });
  serverUrlInput.value = defaults.serverUrl;
  adminKeyInput.value = defaults.adminKey;

  if (!defaults.adminKey) {
    try {
      const response = await fetch(`${defaults.serverUrl.replace(/\/$/, "")}/api/session/extension/info`);
      const data = await response.json();
      if (data.admin_key_configured) {
        setStatus("Server is ready. Paste SESSION_ADMIN_KEY from the server .env file.", null);
      } else {
        setStatus("Server is missing SESSION_ADMIN_KEY in .env. Ask IT to add one first.", false);
      }
    } catch (_error) {
      setStatus("Could not reach the app server. Check the server URL.", false);
    }
  }
}

document.getElementById("save").addEventListener("click", () => {
  chrome.storage.sync.set(
    {
      serverUrl: serverUrlInput.value.trim(),
      adminKey: adminKeyInput.value.trim(),
    },
    () => {
      savedEl.textContent = "Saved.";
      setTimeout(() => {
        savedEl.textContent = "";
      }, 2000);
    }
  );
});

document.getElementById("test").addEventListener("click", async () => {
  const serverUrl = serverUrlInput.value.trim();
  const adminKey = adminKeyInput.value.trim();
  if (!serverUrl || !adminKey) {
    setStatus("Enter both server URL and SESSION_ADMIN_KEY.", false);
    return;
  }

  setStatus("Testing connection...", null);
  try {
    const response = await fetch(`${serverUrl.replace(/\/$/, "")}/api/session/extension/info`, {
      headers: { "X-Session-Admin-Key": adminKey },
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || `Server error (${response.status})`);
    }
    setStatus(data.message || "Connection OK.", true);
  } catch (error) {
    setStatus(error.message || "Connection failed.", false);
  }
});

loadDefaults();
