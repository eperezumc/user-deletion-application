const disableForm = document.getElementById("disable-form");
const actionEmailInput = document.getElementById("action-email");
const actionUserIdInput = document.getElementById("action-user-id");
const submitBtn = document.getElementById("submit-btn");
const activateBtn = document.getElementById("activate-btn");
const messageEl = document.getElementById("message");
const envLabelEl = document.getElementById("env-label");
const syncStatusEl = document.getElementById("sync-status");
const stratusEnvLabelEl = document.getElementById("stratus-env-label");
const stratusStatusEl = document.getElementById("stratus-status");
const stratusIndicatorEl = document.getElementById("stratus-indicator");
const reviztoEnvLabelEl = document.getElementById("revizto-env-label");
const reviztoStatusEl = document.getElementById("revizto-status");
const reviztoIndicatorEl = document.getElementById("revizto-indicator");
const trackviaStatusEl = document.getElementById("trackvia-status");
const trackviaIndicatorEl = document.getElementById("trackvia-indicator");
const openspaceStatusEl = document.getElementById("openspace-status");
const openspaceIndicatorEl = document.getElementById("openspace-indicator");
const symetriStatusEl = document.getElementById("symetri-status");
const symetriIndicatorEl = document.getElementById("symetri-indicator");
const plangridStatusEl = document.getElementById("plangrid-status");
const plangridIndicatorEl = document.getElementById("plangrid-indicator");
const symetriFixBtn = document.getElementById("symetri-fix-btn");
const symetriReconnectBtn = document.getElementById("symetri-reconnect-btn");
const symetriReconnectDialog = document.getElementById("symetri-reconnect-dialog");
const symetriReconnectTokenInput = document.getElementById("symetri-reconnect-token");
const symetriReconnectStatusEl = document.getElementById("symetri-reconnect-status");
const symetriReconnectSaveBtn = document.getElementById("symetri-reconnect-save-btn");
const symetriReconnectAutoBtn = document.getElementById("symetri-reconnect-auto-btn");
const symetriReconnectOpenLoginBtn = document.getElementById("symetri-reconnect-open-login");
const syncBtn = document.getElementById("sync-btn");
const stratusFixBtn = document.getElementById("stratus-fix-btn");
const reviztoFixBtn = document.getElementById("revizto-fix-btn");
const stratusReconnectBtn = document.getElementById("stratus-reconnect-btn");
const reviztoReconnectBtn = document.getElementById("revizto-reconnect-btn");
const reviztoReconnectDialog = document.getElementById("revizto-reconnect-dialog");
const reviztoReconnectCodeInput = document.getElementById("revizto-reconnect-code");
const reviztoReconnectStatusEl = document.getElementById("revizto-reconnect-status");
const reviztoReconnectSaveBtn = document.getElementById("revizto-reconnect-save-btn");
const reviztoReconnectAutoBtn = document.getElementById("revizto-reconnect-auto-btn");
const reviztoReconnectOpenLoginBtn = document.getElementById("revizto-reconnect-open-login");
const sessionFixDialog = document.getElementById("session-fix-dialog");
const sessionFixTitle = document.getElementById("session-fix-title");
const sessionFixIntro = document.getElementById("session-fix-intro");
const sessionFixSteps = document.getElementById("session-fix-steps");
const sessionFixExtensionStatus = document.getElementById("session-fix-extension-status");
const sessionFixOpenLoginBtn = document.getElementById("session-fix-open-login");
const sessionFixCommandEl = document.getElementById("session-fix-command");
const sessionFixCopyBtn = document.getElementById("session-fix-copy");
const sessionFixRunScriptBtn = document.getElementById("session-fix-run-script");
const sessionFixCheckBtn = document.getElementById("session-fix-check");
const envButtons = document.querySelectorAll(".env-toggle__btn");
const platformLookupBtn = document.getElementById("platform-lookup-btn");
const membershipEmailInput = document.getElementById("membership-email");
const membershipSuggestionsEl = document.getElementById("membership-suggestions");
const platformLookupEmpty = document.getElementById("platform-lookup-empty");
const platformLookupResults = document.getElementById("platform-lookup-results");
const platformLookupSummary = document.getElementById("platform-lookup-summary");
const platformLookupSource = document.getElementById("platform-lookup-source");
const platformLookupList = document.getElementById("platform-lookup-list");
const platformLookupMessage = document.getElementById("platform-lookup-message");
const platformSyncBtn = document.getElementById("platform-sync-btn");
const platformSyncStatusEl = document.getElementById("platform-sync-status");

const PLATFORM_LOGIN_URLS = {
  stratus: "https://www.gtpstratus.com/",
  revizto: "https://ws.revizto.com/",
  symetri: "https://my.symetri.com/",
};
const DEFAULT_REVIZTO_ACCESS_CODE_URL =
  "https://ws.revizto.com/login?request=accessCode";
let reviztoAccessCodeUrl = DEFAULT_REVIZTO_ACCESS_CODE_URL;

const ENV_STORAGE_KEY = "acc_environment";
let currentEnvironment = localStorage.getItem(ENV_STORAGE_KEY) || "dev";
let membershipSearchTimer = null;
let membershipActiveIndex = -1;
let membershipCurrentResults = [];
let environmentLabels = { dev: "Dev Hub", prod: "Production" };
let stratusEnvironmentLabels = { dev: "Stratus Dev", prod: "Stratus Production" };
let hasLocalUsers = false;
let syncingEnvironment = null;
let stratusConfiguredByEnv = { dev: false, prod: false };
let reviztoConfiguredOnServer = false;
let trackviaConfiguredOnServer = false;
let openspaceConfiguredOnServer = false;
let symetriConfiguredOnServer = false;
let plangridConfiguredOnServer = false;
let reviztoLabel = "Revizto";
let trackviaLabel = "TrackVia";
let openspaceLabel = "OpenSpace";
let symetriLabel = "Symetri";
let plangridLabel = "PlanGrid";
let stratusHealthData = null;
let reviztoHealthData = null;
let trackviaHealthData = null;
let openspaceHealthData = null;
let symetriHealthData = null;
let plangridHealthData = null;
let reconnectPollTimer = null;
let sessionFixPlatform = null;
let sessionFixPollTimer = null;
let extensionInstalled = false;
let extensionInfo = null;

const SYNC_BTN_LABEL = "Sync from Autodesk";
const FIX_BTN_LABEL = "Fix connection";
const RECONNECT_BTN_LABEL = "Reconnect";
const HEALTH_INTERVAL_MS = 5 * 60 * 1000;
const HEALTH_FETCH_TIMEOUT_MS = 60000;
const RECONNECT_POLL_MS = 2000;
const SESSION_FIX_POLL_MS = 3000;
let stratusHealthTimer = null;
let reviztoHealthTimer = null;
let trackviaHealthTimer = null;
let openspaceHealthTimer = null;
let symetriHealthTimer = null;
let plangridHealthTimer = null;
let stratusHealthRequestId = 0;
let reviztoHealthRequestId = 0;
let trackviaHealthRequestId = 0;
let openspaceHealthRequestId = 0;
let symetriHealthRequestId = 0;
let plangridHealthRequestId = 0;

let platformSyncing = false;
let platformLookupRequestId = 0;
let platformLookupAbortController = null;
let lastRenderedLookupEmail = "";
const PLATFORM_LOOKUP_BTN_LABEL = "Look up platforms";
const PLATFORM_SYNC_BTN_LABEL = "Sync all platforms";
const PLATFORM_LOOKUP_ORDER = ["acc", "stratus", "revizto", "trackvia", "openspace", "symetri"];

window.addEventListener("session-sync-extension-ready", () => {
  extensionInstalled = true;
  if (!sessionFixDialog.open) {
    return;
  }
  sessionFixExtensionStatus.textContent = "Session Sync extension detected in this browser.";
});

window.addEventListener("session-sync-pushed", (event) => {
  const detail = event.detail || {};
  showMessage(detail.message || "Session pushed to server.", "success");
  refreshStratusHealth();
  refreshReviztoHealth();
  refreshTrackviaHealth();
  refreshOpenspaceHealth();
  refreshSymetriHealth();
  refreshPlangridHealth();
  if (sessionFixDialog.open) {
    sessionFixExtensionStatus.textContent = "Session pushed. Checking server status...";
  }
});

async function loadExtensionInfo() {
  try {
    const response = await fetch("/api/session/extension/info");
    extensionInfo = await response.json();
  } catch (_error) {
    extensionInfo = null;
  }
}

function updateFixButtons(fixBtn, reconnectBtn, data, reconnecting = false) {
  const showFix = Boolean(data?.extension_reconnect && !reconnecting);
  const showLocalReconnect = Boolean(data?.interactive_reconnect && !reconnecting);

  if (fixBtn) {
    fixBtn.hidden = !showFix;
    fixBtn.disabled = reconnecting;
    fixBtn.textContent = FIX_BTN_LABEL;
  }
  if (reconnectBtn) {
    reconnectBtn.hidden = !showLocalReconnect;
    reconnectBtn.disabled = reconnecting;
    reconnectBtn.textContent = reconnecting ? "Signing in..." : RECONNECT_BTN_LABEL;
  }
}

function isStratusConfiguredOnServer() {
  return Boolean(stratusConfiguredByEnv[currentEnvironment]);
}

function isReviztoConfiguredOnServer() {
  return Boolean(reviztoConfiguredOnServer);
}

function setConnectionDisplay({
  statusEl,
  indicatorEl,
  fixBtn,
  reconnectBtn,
  data,
  notConfiguredMessage,
  reconnecting = false,
}) {
  let message = data?.message || "Status unknown.";
  if (!data?.ok && data?.reconnect_hint) {
    message = data.reconnect_hint;
  } else if (!data?.ok && data?.admin_hint) {
    message = `${message} ${data.admin_hint}`;
  }
  if (reconnecting) {
    message = "Browser opened on this PC — sign in to restore the connection.";
  }
  statusEl.textContent = message;
  statusEl.classList.remove("is-ok", "is-error", "is-warning");
  indicatorEl.classList.remove("is-ok", "is-error", "is-unknown", "is-warning");
  updateFixButtons(fixBtn, reconnectBtn, data, reconnecting);

  if (data?.ok && !reconnecting) {
    statusEl.classList.add("is-ok");
    indicatorEl.classList.add("is-ok");
    return;
  }

  if (data?.connection_error || data?.configured === true || reconnecting) {
    statusEl.classList.add("is-warning");
    indicatorEl.classList.add("is-warning");
    return;
  }

  statusEl.classList.add("is-error");
  indicatorEl.classList.add("is-error");
  if (data?.configured === false && notConfiguredMessage) {
    statusEl.textContent = notConfiguredMessage;
  }
}

function setTrackviaHealthDisplay(data) {
  trackviaHealthData = data;
  if (!trackviaStatusEl || !trackviaIndicatorEl) {
    return;
  }

  let message = data?.message || "Checking TrackVia connection...";
  if (data?.ok && !data?.connection_error) {
    trackviaStatusEl.textContent = message;
    trackviaStatusEl.classList.remove("is-error", "is-warning");
    trackviaStatusEl.classList.add("is-ok");
    trackviaIndicatorEl.classList.remove("is-error", "is-unknown", "is-warning");
    trackviaIndicatorEl.classList.add("is-ok");
    return;
  }

  if (data?.configured === false) {
    message = `${data?.label || trackviaLabel} not set up on this server. Add TRACKVIA_API_KEY and TRACKVIA_ACCESS_TOKEN in .env.`;
  }

  trackviaStatusEl.textContent = message;
  trackviaStatusEl.classList.remove("is-ok", "is-error");
  trackviaStatusEl.classList.add(data?.configured === false ? "is-error" : "is-warning");
  trackviaIndicatorEl.classList.remove("is-ok", "is-unknown");
  trackviaIndicatorEl.classList.add(data?.configured === false ? "is-error" : "is-warning");
}

function setStratusHealthDisplay(data, reconnecting = false) {
  stratusHealthData = data;
  setConnectionDisplay({
    statusEl: stratusStatusEl,
    indicatorEl: stratusIndicatorEl,
    fixBtn: stratusFixBtn,
    reconnectBtn: stratusReconnectBtn,
    data,
    notConfiguredMessage: `${data?.label || "Stratus"} not set up on this server. Contact IT if you need Stratus offboarding.`,
    reconnecting,
  });
}

function setReviztoHealthDisplay(data, reconnecting = false) {
  reviztoHealthData = data;
  setConnectionDisplay({
    statusEl: reviztoStatusEl,
    indicatorEl: reviztoIndicatorEl,
    fixBtn: reviztoFixBtn,
    reconnectBtn: reviztoReconnectBtn,
    data,
    notConfiguredMessage: `${data?.label || reviztoLabel} not set up on this server. Contact IT to configure Revizto.`,
    reconnecting,
  });

  if (!data?.ok && (data?.needs_reconnect || data?.token_expired) && reviztoReconnectBtn) {
    reviztoReconnectBtn.hidden = false;
    reviztoReconnectBtn.disabled = reconnecting;
    reviztoReconnectBtn.textContent = reconnecting ? "Reconnecting..." : RECONNECT_BTN_LABEL;
  }
}

function openReviztoReconnectDialog(statusMessage = "") {
  if (reviztoReconnectCodeInput) {
    reviztoReconnectCodeInput.value = "";
  }
  if (reviztoReconnectStatusEl) {
    reviztoReconnectStatusEl.textContent =
      statusMessage ||
      "Open the API access code page, sign in if needed, and paste the code from the API tab.";
  }
  if (reviztoReconnectAutoBtn) {
    reviztoReconnectAutoBtn.hidden = false;
    reviztoReconnectAutoBtn.disabled = false;
    reviztoReconnectAutoBtn.textContent = "Try automatic sign-in";
  }
  reviztoReconnectDialog?.showModal();
}

async function saveReviztoAccessCode() {
  const accessCode = reviztoReconnectCodeInput?.value?.trim() || "";
  if (!accessCode) {
    if (reviztoReconnectStatusEl) {
      reviztoReconnectStatusEl.textContent = "Paste the API access code first.";
    }
    return;
  }

  if (reviztoReconnectSaveBtn) {
    reviztoReconnectSaveBtn.disabled = true;
    reviztoReconnectSaveBtn.textContent = "Connecting...";
  }
  if (reviztoReconnectStatusEl) {
    reviztoReconnectStatusEl.textContent = "Exchanging access code for API tokens...";
  }

  try {
    const response = await fetch("/api/session/revizto/access-code", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_code: accessCode }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "Could not connect Revizto.");
    }

    if (reviztoReconnectStatusEl) {
      reviztoReconnectStatusEl.textContent = data.message || "Revizto connected.";
    }
    await refreshReviztoHealth();
    showMessage(data.message || "Revizto connected.", "success");
    reviztoReconnectDialog?.close();
  } catch (error) {
    if (reviztoReconnectStatusEl) {
      reviztoReconnectStatusEl.textContent = error.message || "Could not connect Revizto.";
    }
    showMessage(error.message || "Could not connect Revizto.", "error");
  } finally {
    if (reviztoReconnectSaveBtn) {
      reviztoReconnectSaveBtn.disabled = false;
      reviztoReconnectSaveBtn.textContent = "Connect";
    }
  }
}

async function startReviztoReconnect() {
  clearMessage();
  setReviztoHealthDisplay(reviztoHealthData || {}, true);

  try {
    const response = await fetch("/api/session/reconnect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform: "revizto", environment: currentEnvironment }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Could not start reconnect.");
    }

    const runningMessage =
      data.message ||
      "Check your taskbar — a NEW browser window is opening. Sign in there, then open My Account -> Active Sessions -> API.";

    if (reviztoStatusEl) {
      reviztoStatusEl.textContent = runningMessage;
    }
    showMessage(runningMessage, "success");

    const outcome = await pollReconnectJob(data.job_id, refreshReviztoHealth, {
      onRunning(job) {
        setReviztoHealthDisplay(
          {
            ...(reviztoHealthData || {}),
            ok: false,
            configured: true,
            needs_reconnect: true,
            message: job.message || runningMessage,
          },
          true
        );
      },
      onFinished() {
        setReviztoHealthDisplay(reviztoHealthData || {}, false);
      },
    });

    if (!outcome?.ok) {
      openReviztoReconnectDialog(
        outcome?.job?.message ||
          "Automatic sign-in did not finish. Paste the access code from Active Sessions -> API."
      );
    }
  } catch (error) {
    setReviztoHealthDisplay(reviztoHealthData || {}, false);
    openReviztoReconnectDialog(error.message || "Automatic reconnect failed. Paste the access code.");
  }
}

function buildSessionFixSteps(platform) {
  const labels = { stratus: "Stratus", revizto: "Revizto", symetri: "Symetri" };
  const label = labels[platform] || platform;
  const script =
    platform === "stratus"
      ? `scripts\\connect-stratus-${currentEnvironment}.bat`
      : platform === "symetri"
        ? "scripts\\connect-symetri.bat"
        : "scripts\\connect-revizto.bat";
  const steps = [
    `Double-click ${script} in the project folder (or run the command below in PowerShell).`,
    "A browser opens — sign in to " + label + ".",
    platform === "symetri"
      ? "The script captures a fresh bearer token and saves it to the server when login finishes."
      : "The script saves the session to the server automatically when login finishes.",
    "Return to this page — status should turn green within a few seconds.",
    "Optional: if your company allows extensions, see browser_extension/INSTALL.md.",
  ];
  if (!extensionInfo?.admin_key_configured) {
    steps.unshift("Add SESSION_ADMIN_KEY to the server .env file first (ask IT).");
  }
  return steps;
}

async function loadSessionFixCommand(platform) {
  if (!sessionFixCommandEl) {
    return;
  }
  try {
    const response = await fetch(
      `/api/session/connect-command?platform=${encodeURIComponent(platform)}&environment=${encodeURIComponent(currentEnvironment)}`
    );
    const data = await response.json();
    const script = data.script_path || "scripts/connect-revizto.bat";
    sessionFixCommandEl.textContent =
      data.remote_command ||
      `.venv\\Scripts\\python connect_sessions.py --platform ${platform} --server ${window.location.origin}`;
    if (sessionFixRunScriptBtn) {
      sessionFixRunScriptBtn.dataset.scriptPath = script;
    }
  } catch (_error) {
    sessionFixCommandEl.textContent =
      `scripts\\connect-${platform === "stratus" ? `stratus-${currentEnvironment}` : platform === "symetri" ? "symetri" : "revizto"}.bat`;
  }
}

function renderSessionFixSteps(platform) {
  sessionFixSteps.innerHTML = "";
  for (const step of buildSessionFixSteps(platform)) {
    const item = document.createElement("li");
    item.textContent = step;
    sessionFixSteps.appendChild(item);
  }
}

function stopSessionFixPolling() {
  if (sessionFixPollTimer) {
    clearInterval(sessionFixPollTimer);
    sessionFixPollTimer = null;
  }
}

function startSessionFixPolling(refreshHealth) {
  stopSessionFixPolling();
  sessionFixPollTimer = setInterval(async () => {
    await refreshHealth({ silent: true });
    const healthByPlatform = {
      stratus: stratusHealthData,
      revizto: reviztoHealthData,
      symetri: symetriHealthData,
    };
    const data = healthByPlatform[sessionFixPlatform];
    if (data?.ok) {
      stopSessionFixPolling();
      sessionFixExtensionStatus.textContent = "Connection restored.";
      showMessage(data.message || "Connection restored.", "success");
    }
  }, SESSION_FIX_POLL_MS);
}

function sessionFixRefresh(platform) {
  if (platform === "stratus") {
    return refreshStratusHealth;
  }
  if (platform === "symetri") {
    return refreshSymetriHealth;
  }
  return refreshReviztoHealth;
}

function openSessionFixDialog(platform) {
  sessionFixPlatform = platform;
  const labels = { stratus: "Stratus", revizto: "Revizto", symetri: "Symetri" };
  const label = labels[platform] || platform;
  sessionFixTitle.textContent = `Fix ${label} connection`;
  sessionFixIntro.textContent =
    "Your company browser policy blocks the Chrome extension — that is normal on managed PCs. " +
    "Use the script or PowerShell command below instead. It works from any IT computer.";
  renderSessionFixSteps(platform);
  loadSessionFixCommand(platform);
  sessionFixExtensionStatus.textContent =
    "Chrome blocked the extension? Use the .bat file or copied command — no extension needed.";
  sessionFixDialog.showModal();
  startSessionFixPolling(sessionFixRefresh(platform));
}

sessionFixDialog?.addEventListener("close", () => {
  stopSessionFixPolling();
  sessionFixPlatform = null;
});

sessionFixOpenLoginBtn?.addEventListener("click", () => {
  if (!sessionFixPlatform) {
    return;
  }
  window.open(PLATFORM_LOGIN_URLS[sessionFixPlatform], "_blank", "noopener");
});

sessionFixCheckBtn?.addEventListener("click", async () => {
  if (sessionFixPlatform) {
    await sessionFixRefresh(sessionFixPlatform)({ silent: false });
  }
});

sessionFixCopyBtn?.addEventListener("click", async () => {
  const text = sessionFixCommandEl?.textContent?.trim() || "";
  if (!text) {
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    sessionFixExtensionStatus.textContent = "Command copied. Paste it into PowerShell from the project folder.";
  } catch (_error) {
    sessionFixExtensionStatus.textContent = "Could not copy automatically. Select and copy the command manually.";
  }
});

sessionFixRunScriptBtn?.addEventListener("click", () => {
  const script = sessionFixRunScriptBtn.dataset.scriptPath || "scripts\\connect-revizto.bat";
  sessionFixExtensionStatus.textContent =
    `In File Explorer, open the project folder and double-click: ${script}`;
});

function pollReconnectJob(jobId, refreshHealth, { onRunning, onFinished } = {}) {
  if (reconnectPollTimer) {
    clearInterval(reconnectPollTimer);
  }

  return new Promise((resolve) => {
    const finish = async (outcome) => {
      clearInterval(reconnectPollTimer);
      reconnectPollTimer = null;
      if (typeof onFinished === "function") {
        onFinished(outcome);
      }
      resolve(outcome);
    };

    reconnectPollTimer = setInterval(async () => {
      try {
        const response = await fetch(
          `/api/session/reconnect/status?job_id=${encodeURIComponent(jobId)}`
        );
        const job = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(job.error || "Reconnect status check failed.");
        }

        if (job.status === "running") {
          if (typeof onRunning === "function") {
            onRunning(job);
          }
          return;
        }

        if (job.status === "success") {
          await refreshHealth({ silent: false });
          showMessage(job.message || "Session reconnected.", "success");
          await finish({ ok: true, job });
          return;
        }

        await refreshHealth({ silent: false });
        showMessage(job.message || "Reconnect failed.", "error");
        if (jobId === "revizto" || String(jobId).startsWith("revizto")) {
          openReviztoReconnectDialog(
            job.message || "Automatic sign-in failed. Paste the access code from Active Sessions -> API."
          );
        }
        await finish({ ok: false, job });
      } catch (error) {
        await refreshHealth({ silent: false });
        showMessage(error.message || "Reconnect failed.", "error");
        await finish({ ok: false, error });
      }
    }, RECONNECT_POLL_MS);
  });
}

async function startPlatformReconnect(platform) {
  const refreshByPlatform = {
    stratus: refreshStratusHealth,
    revizto: refreshReviztoHealth,
    symetri: refreshSymetriHealth,
  };
  const displayByPlatform = {
    stratus: setStratusHealthDisplay,
    revizto: setReviztoHealthDisplay,
    symetri: setSymetriHealthDisplay,
  };
  const healthByPlatform = {
    stratus: stratusHealthData,
    revizto: reviztoHealthData,
    symetri: symetriHealthData,
  };
  const refreshHealth = refreshByPlatform[platform] || refreshReviztoHealth;
  const setDisplay = displayByPlatform[platform] || setReviztoHealthDisplay;
  const healthData = healthByPlatform[platform];

  setDisplay(healthData || {}, true);
  clearMessage();

  try {
    const response = await fetch("/api/session/reconnect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        platform,
        environment: currentEnvironment,
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Could not start reconnect.");
    }
    const runningMessage =
      platform === "revizto"
        ? "Sign in in the separate browser window. The app will fetch an API access code and renew OAuth tokens."
        : data.message || "Browser opened — sign in when prompted.";
    showMessage(runningMessage, "success");
    await pollReconnectJob(data.job_id, refreshHealth, {
      onRunning(job) {
        if (platform === "revizto" && reviztoStatusEl) {
          setReviztoHealthDisplay(
            {
              ...(reviztoHealthData || {}),
              ok: false,
              configured: true,
              needs_reconnect: true,
              message: job.message || runningMessage,
            },
            true
          );
        }
      },
      onFinished() {
        setDisplay(healthData || {}, false);
      },
    });
  } catch (error) {
    setDisplay(healthData || {}, false);
    showMessage(error.message || "Could not start reconnect.", "error");
  }
}

async function fetchHealth(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), HEALTH_FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(url, { signal: controller.signal });
    const data = await response.json().catch(() => ({}));
    const normalized = {
      ...data,
      ok: typeof data.ok === "boolean" ? data.ok : response.ok,
      configured: typeof data.configured === "boolean" ? data.configured : false,
      message:
        data.message ||
        data.error ||
        (response.ok ? "Connected." : `Health check failed (HTTP ${response.status}).`),
    };
    return { response, data: normalized };
  } finally {
    clearTimeout(timeout);
  }
}

async function refreshStratusHealth({ silent = false } = {}) {
  const requestId = ++stratusHealthRequestId;
  const environment = currentEnvironment;

  if (!silent) {
    stratusStatusEl.textContent = "Checking Stratus connection...";
    stratusStatusEl.classList.remove("is-ok", "is-error", "is-warning");
    stratusIndicatorEl.classList.remove("is-ok", "is-error", "is-warning");
    stratusIndicatorEl.classList.add("is-unknown");
  }

  try {
    const { data } = await fetchHealth(
      `/api/stratus/health?environment=${encodeURIComponent(environment)}`
    );
    if (requestId !== stratusHealthRequestId || environment !== currentEnvironment) {
      return;
    }
    setStratusHealthDisplay(data);
  } catch (error) {
    if (requestId !== stratusHealthRequestId || environment !== currentEnvironment) {
      return;
    }
    if (!silent || !stratusHealthData) {
      setStratusHealthDisplay({
        ok: false,
        configured: isStratusConfiguredOnServer(),
        connection_error: true,
        message:
          error.name === "AbortError"
            ? "Stratus health check timed out. The server may still be loading user data — try again in a moment."
            : "Unable to reach Stratus health check. Is the app server running?",
      });
    }
  }
}

async function refreshReviztoHealth({ silent = false } = {}) {
  const requestId = ++reviztoHealthRequestId;

  if (!silent) {
    reviztoStatusEl.textContent = "Checking Revizto connection...";
    reviztoStatusEl.classList.remove("is-ok", "is-error", "is-warning");
    reviztoIndicatorEl.classList.remove("is-ok", "is-error", "is-warning");
    reviztoIndicatorEl.classList.add("is-unknown");
  }

  try {
    const { data } = await fetchHealth("/api/revizto/health");
    if (requestId !== reviztoHealthRequestId) {
      return;
    }
    setReviztoHealthDisplay(data);
  } catch (error) {
    if (requestId !== reviztoHealthRequestId) {
      return;
    }
    if (!silent || !reviztoHealthData) {
      setReviztoHealthDisplay({
        ok: false,
        configured: isReviztoConfiguredOnServer(),
        connection_error: true,
        message:
          error.name === "AbortError"
            ? "Revizto health check timed out. Try again in a moment."
            : "Unable to reach Revizto health check. Is the app server running?",
      });
    }
  }
}

function setOpenspaceHealthDisplay(data) {
  openspaceHealthData = data;
  if (!openspaceStatusEl || !openspaceIndicatorEl) {
    return;
  }

  let message = data?.message || "Checking OpenSpace connection...";
  if (data?.ok) {
    openspaceStatusEl.textContent = message;
    openspaceStatusEl.classList.remove("is-error", "is-warning");
    openspaceStatusEl.classList.add("is-ok");
    openspaceIndicatorEl.classList.remove("is-error", "is-unknown", "is-warning");
    openspaceIndicatorEl.classList.add("is-ok");
    return;
  }

  if (data?.configured === false) {
    message = `${data?.label || openspaceLabel} not set up on this server. Set OPENSPACE_ORG_ID and OPENSPACE_SESSION_COOKIE in .env.`;
  }

  openspaceStatusEl.textContent = message;
  openspaceStatusEl.classList.remove("is-ok", "is-error");
  openspaceStatusEl.classList.add(data?.configured === false ? "is-error" : "is-warning");
  openspaceIndicatorEl.classList.remove("is-ok", "is-unknown");
  openspaceIndicatorEl.classList.add(data?.configured === false ? "is-error" : "is-warning");
}

async function refreshTrackviaHealth({ silent = false } = {}) {
  const requestId = ++trackviaHealthRequestId;

  if (!silent && trackviaStatusEl && trackviaIndicatorEl) {
    trackviaStatusEl.textContent = "Checking TrackVia connection...";
    trackviaStatusEl.classList.remove("is-ok", "is-error", "is-warning");
    trackviaIndicatorEl.classList.remove("is-ok", "is-error", "is-warning");
    trackviaIndicatorEl.classList.add("is-unknown");
  }

  try {
    const { data } = await fetchHealth("/api/trackvia/health");
    if (requestId !== trackviaHealthRequestId) {
      return;
    }
    setTrackviaHealthDisplay(data);
  } catch (error) {
    if (requestId !== trackviaHealthRequestId) {
      return;
    }
    if (!silent || !trackviaHealthData) {
      setTrackviaHealthDisplay({
        ok: false,
        configured: trackviaConfiguredOnServer,
        connection_error: true,
        message:
          error.name === "AbortError"
            ? "TrackVia health check timed out. Try again in a moment."
            : "Unable to reach TrackVia health check. Is the app server running?",
      });
    }
  }
}

async function refreshOpenspaceHealth({ silent = false } = {}) {
  const requestId = ++openspaceHealthRequestId;

  if (!silent && openspaceStatusEl && openspaceIndicatorEl) {
    openspaceStatusEl.textContent = "Checking OpenSpace connection...";
    openspaceStatusEl.classList.remove("is-ok", "is-error", "is-warning");
    openspaceIndicatorEl.classList.remove("is-ok", "is-error", "is-warning");
    openspaceIndicatorEl.classList.add("is-unknown");
  }

  try {
    const { data } = await fetchHealth("/api/openspace/health");
    if (requestId !== openspaceHealthRequestId) {
      return;
    }
    setOpenspaceHealthDisplay(data);
  } catch (error) {
    if (requestId !== openspaceHealthRequestId) {
      return;
    }
    if (!silent || !openspaceHealthData) {
      setOpenspaceHealthDisplay({
        ok: false,
        configured: openspaceConfiguredOnServer,
        connection_error: true,
        message:
          error.name === "AbortError"
            ? "OpenSpace health check timed out. Try again in a moment."
            : "Unable to reach OpenSpace health check. Is the app server running?",
      });
    }
  }
}

function setSymetriHealthDisplay(data, reconnecting = false) {
  symetriHealthData = data;
  if (!symetriStatusEl || !symetriIndicatorEl) {
    return;
  }
  setConnectionDisplay({
    statusEl: symetriStatusEl,
    indicatorEl: symetriIndicatorEl,
    fixBtn: symetriFixBtn,
    reconnectBtn: symetriReconnectBtn,
    data,
    notConfiguredMessage: `${data?.label || symetriLabel} not set up on this server. Set SYMETRI_ACCOUNT_ID and SYMETRI_BEARER_TOKEN in .env.`,
    reconnecting,
  });

  if (!data?.ok && (data?.token_expired || data?.needs_reconnect) && symetriReconnectBtn) {
    symetriReconnectBtn.hidden = false;
    symetriReconnectBtn.disabled = reconnecting;
    symetriReconnectBtn.textContent = reconnecting ? "Reconnecting..." : RECONNECT_BTN_LABEL;
  }
}

function openSymetriReconnectDialog() {
  if (symetriReconnectTokenInput) {
    symetriReconnectTokenInput.value = "";
  }
  if (symetriReconnectStatusEl) {
    symetriReconnectStatusEl.textContent =
      "Automatic reconnect failed. Paste a bearer token from DevTools if needed.";
  }
  if (symetriReconnectAutoBtn) {
    symetriReconnectAutoBtn.hidden = false;
    symetriReconnectAutoBtn.disabled = false;
    symetriReconnectAutoBtn.textContent = "Try automatic sign-in again";
  }
  symetriReconnectDialog?.showModal();
}

async function startSymetriReconnect() {
  clearMessage();
  setSymetriHealthDisplay(symetriHealthData || {}, true);

  try {
    const response = await fetch("/api/session/reconnect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform: "symetri" }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Could not start reconnect.");
    }
    if (symetriStatusEl) {
      symetriStatusEl.textContent =
        data.message ||
        "A separate browser window opened — sign in to my.symetri.com in THAT window.";
    }
    showMessage(
      "Sign in using the separate browser window that just opened (not this tab).",
      "success"
    );
    await pollReconnectJob(data.job_id, refreshSymetriHealth, {
      onRunning(job) {
        setSymetriHealthDisplay(
          {
            ...(symetriHealthData || {}),
            ok: false,
            configured: true,
            needs_reconnect: true,
            message:
              job.message ||
              "Waiting for sign-in in the Playwright browser window...",
          },
          true
        );
      },
      onFinished() {
        setSymetriHealthDisplay(symetriHealthData || {}, false);
      },
    });
  } catch (error) {
    setSymetriHealthDisplay(symetriHealthData || {}, false);
    if (extensionInstalled) {
      const syncUrl = `${PLATFORM_LOGIN_URLS.symetri}?umci_session_sync=1`;
      window.open(syncUrl, "_blank", "noopener");
      showMessage(
        "Automatic reconnect is unavailable. Symetri opened in a new tab — sign in and the extension will push the token.",
        "error"
      );
      startSymetriExtensionPolling();
      return;
    }
    window.location.href = "/connect/symetri";
  }
}

let symetriExtensionPollTimer = null;

function stopSymetriExtensionPolling() {
  if (symetriExtensionPollTimer) {
    clearInterval(symetriExtensionPollTimer);
    symetriExtensionPollTimer = null;
  }
}

function startSymetriExtensionPolling() {
  stopSymetriExtensionPolling();
  let attempts = 0;
  symetriExtensionPollTimer = setInterval(async () => {
    attempts += 1;
    await refreshSymetriHealth({ silent: true });
    if (symetriHealthData?.ok) {
      stopSymetriExtensionPolling();
      showMessage(symetriHealthData.message || "Symetri reconnected.", "success");
      return;
    }
    if (attempts >= 100) {
      stopSymetriExtensionPolling();
      openSymetriReconnectDialog();
    }
  }, 3000);
}

async function saveSymetriBearerToken() {
  const token = symetriReconnectTokenInput?.value?.trim() || "";
  if (!token) {
    if (symetriReconnectStatusEl) {
      symetriReconnectStatusEl.textContent = "Paste a bearer token first.";
    }
    return;
  }

  if (symetriReconnectSaveBtn) {
    symetriReconnectSaveBtn.disabled = true;
    symetriReconnectSaveBtn.textContent = "Saving...";
  }
  if (symetriReconnectStatusEl) {
    symetriReconnectStatusEl.textContent = "Validating token with Symetri...";
  }

  try {
    const response = await fetch("/api/session/symetri/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bearer_token: token }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "Could not save Symetri token.");
    }

    if (symetriReconnectStatusEl) {
      symetriReconnectStatusEl.textContent = data.message || "Symetri reconnected.";
    }
    await refreshSymetriHealth();
    showMessage(data.message || "Symetri reconnected.", "success");
    symetriReconnectDialog?.close();
  } catch (error) {
    if (symetriReconnectStatusEl) {
      symetriReconnectStatusEl.textContent = error.message || "Could not save Symetri token.";
    }
    showMessage(error.message || "Could not save Symetri token.", "error");
  } finally {
    if (symetriReconnectSaveBtn) {
      symetriReconnectSaveBtn.disabled = false;
      symetriReconnectSaveBtn.textContent = "Save token";
    }
  }
}

async function refreshSymetriHealth({ silent = false } = {}) {
  const requestId = ++symetriHealthRequestId;

  if (!silent && symetriStatusEl && symetriIndicatorEl) {
    symetriStatusEl.textContent = "Checking Symetri connection...";
    symetriStatusEl.classList.remove("is-ok", "is-error", "is-warning");
    symetriIndicatorEl.classList.remove("is-ok", "is-error", "is-warning");
    symetriIndicatorEl.classList.add("is-unknown");
  }

  try {
    const { data } = await fetchHealth("/api/symetri/health");
    if (requestId !== symetriHealthRequestId) {
      return;
    }
    setSymetriHealthDisplay(data);
  } catch (error) {
    if (requestId !== symetriHealthRequestId) {
      return;
    }
    if (!silent || !symetriHealthData) {
      setSymetriHealthDisplay({
        ok: false,
        configured: symetriConfiguredOnServer,
        connection_error: true,
        message:
          error.name === "AbortError"
            ? "Symetri health check timed out. Try again in a moment."
            : "Unable to reach Symetri health check. Is the app server running?",
      });
    }
  }
}

function setPlangridHealthDisplay(data) {
  plangridHealthData = data;
  if (!plangridStatusEl || !plangridIndicatorEl) {
    return;
  }

  let message = data?.message || "Checking PlanGrid connection...";
  if (data?.ok) {
    plangridStatusEl.textContent = message;
    plangridStatusEl.classList.remove("is-error", "is-warning");
    plangridStatusEl.classList.add("is-ok");
    plangridIndicatorEl.classList.remove("is-error", "is-unknown", "is-warning");
    plangridIndicatorEl.classList.add("is-ok");
    return;
  }

  if (data?.configured === false) {
    message =
      data?.message ||
      `${data?.label || plangridLabel} not set up. Add PLANGRID_ORG_ID and PLANGRID_SESSION_COOKIE from Admin Console DevTools.`;
  }

  plangridStatusEl.textContent = message;
  plangridStatusEl.classList.remove("is-ok", "is-error");
  plangridStatusEl.classList.add(data?.configured === false ? "is-error" : "is-warning");
  plangridIndicatorEl.classList.remove("is-ok", "is-unknown");
  plangridIndicatorEl.classList.add(data?.configured === false ? "is-error" : "is-warning");
}

async function refreshPlangridHealth({ silent = false } = {}) {
  const requestId = ++plangridHealthRequestId;

  if (!silent && plangridStatusEl && plangridIndicatorEl) {
    plangridStatusEl.textContent = "Checking PlanGrid connection...";
    plangridStatusEl.classList.remove("is-ok", "is-error", "is-warning");
    plangridIndicatorEl.classList.remove("is-ok", "is-error", "is-warning");
    plangridIndicatorEl.classList.add("is-unknown");
  }

  try {
    const { data } = await fetchHealth("/api/plangrid/health");
    if (requestId !== plangridHealthRequestId) {
      return;
    }
    setPlangridHealthDisplay(data);
  } catch (error) {
    if (requestId !== plangridHealthRequestId) {
      return;
    }
    if (!silent || !plangridHealthData) {
      setPlangridHealthDisplay({
        ok: false,
        configured: plangridConfiguredOnServer,
        connection_error: true,
        message:
          error.name === "AbortError"
            ? "PlanGrid health check timed out. Try again in a moment."
            : "Unable to reach PlanGrid health check. Is the app server running?",
      });
    }
  }
}

function startHealthPolling() {
  if (stratusHealthTimer) {
    clearInterval(stratusHealthTimer);
  }
  if (reviztoHealthTimer) {
    clearInterval(reviztoHealthTimer);
  }
  if (trackviaHealthTimer) {
    clearInterval(trackviaHealthTimer);
  }
  if (openspaceHealthTimer) {
    clearInterval(openspaceHealthTimer);
  }
  if (symetriHealthTimer) {
    clearInterval(symetriHealthTimer);
  }
  if (plangridHealthTimer) {
    clearInterval(plangridHealthTimer);
  }
  stratusHealthTimer = setInterval(() => refreshStratusHealth({ silent: true }), HEALTH_INTERVAL_MS);
  reviztoHealthTimer = setInterval(() => refreshReviztoHealth({ silent: true }), HEALTH_INTERVAL_MS);
  trackviaHealthTimer = setInterval(() => refreshTrackviaHealth({ silent: true }), HEALTH_INTERVAL_MS);
  openspaceHealthTimer = setInterval(() => refreshOpenspaceHealth({ silent: true }), HEALTH_INTERVAL_MS);
  symetriHealthTimer = setInterval(() => refreshSymetriHealth({ silent: true }), HEALTH_INTERVAL_MS);
  plangridHealthTimer = setInterval(() => refreshPlangridHealth({ silent: true }), HEALTH_INTERVAL_MS);
  refreshSymetriHealth();
  refreshPlangridHealth();
}

function setEnvToggleDisabled(disabled) {
  envButtons.forEach((button) => {
    button.disabled = disabled;
  });
}

function updateSyncButtonState() {
  if (syncingEnvironment === currentEnvironment) {
    syncBtn.textContent = "Syncing...";
    syncBtn.disabled = true;
    syncStatusEl.textContent = `Syncing ${environmentLabels[currentEnvironment]} from Autodesk...`;
    return;
  }

  syncBtn.textContent = SYNC_BTN_LABEL;
  syncBtn.disabled = syncingEnvironment !== null;
}

function showMessage(text, type) {
  messageEl.textContent = text;
  messageEl.className = `message ${type}`;
  messageEl.hidden = false;
}

function clearMessage() {
  messageEl.hidden = true;
  messageEl.textContent = "";
  messageEl.className = "message";
}

function setEnvironment(environment) {
  currentEnvironment = environment;
  localStorage.setItem(ENV_STORAGE_KEY, environment);

  envButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.environment === environment);
  });

  const accLabel = environmentLabels[environment] || environment;
  envLabelEl.textContent = `Autodesk ACC · ${accLabel}`;
  if (stratusEnvLabelEl) {
    stratusEnvLabelEl.textContent = `GTP Stratus · ${
      stratusEnvironmentLabels[environment] || environment
    }`;
  }
  if (reviztoEnvLabelEl) {
    reviztoEnvLabelEl.textContent = reviztoLabel;
  }

  hideMembershipSuggestions();
  if (membershipEmailInput) {
    membershipEmailInput.value = "";
  }
  if (actionEmailInput) {
    actionEmailInput.value = "";
  }
  if (actionUserIdInput) {
    actionUserIdInput.value = "";
  }
  clearMessage();
  updateSyncButtonState();
  refreshStratusHealth();
  refreshReviztoHealth();
  refreshTrackviaHealth();
  refreshOpenspaceHealth();
  refreshSymetriHealth();
  refreshPlangridHealth();
  if (syncingEnvironment !== currentEnvironment) {
    refreshSyncStatus();
  }
  refreshPlatformSyncStatus();
  cancelInFlightPlatformLookup();
  hidePlatformLookupResults();
}

function isValidEmail(value) {
  const trimmed = (value || "").trim();
  return trimmed.includes("@") && trimmed.includes(".");
}

function getActionEmail() {
  return actionEmailInput?.value.trim() || "";
}

function getMembershipEmail() {
  return membershipEmailInput?.value.trim() || "";
}

function cancelInFlightPlatformLookup() {
  if (platformLookupAbortController) {
    platformLookupAbortController.abort();
    platformLookupAbortController = null;
  }
  platformLookupRequestId += 1;
}

function resetPlatformLookupDisplay() {
  hidePlatformLookupResults();
  clearPlatformLookupMessage();
}

function clearPlatformLookupMessage() {
  if (!platformLookupMessage) {
    return;
  }
  platformLookupMessage.hidden = true;
  platformLookupMessage.textContent = "";
  platformLookupMessage.className = "message platform-lookup-message";
}

function showPlatformLookupMessage(text, type = "error") {
  if (!platformLookupMessage) {
    return;
  }
  platformLookupMessage.hidden = false;
  platformLookupMessage.textContent = text;
  platformLookupMessage.className = `message platform-lookup-message message--${type}`;
}

function hidePlatformLookupResults() {
  if (!platformLookupResults) {
    return;
  }
  platformLookupResults.hidden = true;
  if (platformLookupList) {
    platformLookupList.innerHTML = "";
  }
  if (platformLookupSummary) {
    platformLookupSummary.textContent = "";
  }
  if (platformLookupSource) {
    platformLookupSource.hidden = true;
    platformLookupSource.textContent = "";
  }
  if (platformLookupEmpty) {
    platformLookupEmpty.hidden = false;
  }
  lastRenderedLookupEmail = "";
}

function showPlatformLookupLoading(email) {
  if (!platformLookupResults || !platformLookupList || !platformLookupSummary) {
    return;
  }
  if (platformLookupEmpty) {
    platformLookupEmpty.hidden = true;
  }
  platformLookupList.innerHTML = "";
  platformLookupSummary.textContent = `Looking up ${email}...`;
  if (platformLookupSource) {
    platformLookupSource.hidden = true;
    platformLookupSource.textContent = "";
  }
  platformLookupResults.hidden = false;
  clearPlatformLookupMessage();
}

function resolveMembershipStatus(entry) {
  if (entry.membership_status) {
    return entry.membership_status;
  }
  if (!entry.present) {
    return "absent";
  }
  const raw = (entry.status || entry.account_status || "").toLowerCase();
  if (["inactive", "disabled", "deactivated", "2"].includes(raw)) {
    return "disabled";
  }
  return "active";
}

function platformBadgeClass(entry) {
  const state = entry.check_state || (entry.present ? "present" : "absent");
  if (state === "not_configured") {
    return "platform-lookup-item__badge platform-lookup-item__badge--muted";
  }
  if (state === "unavailable") {
    return "platform-lookup-item__badge platform-lookup-item__badge--unavailable";
  }
  if (state === "present") {
    if (resolveMembershipStatus(entry) === "disabled") {
      return "platform-lookup-item__badge platform-lookup-item__badge--inactive";
    }
    return "platform-lookup-item__badge platform-lookup-item__badge--yes";
  }
  return "platform-lookup-item__badge platform-lookup-item__badge--no";
}

function platformBadgeText(entry) {
  const state = entry.check_state || (entry.present ? "present" : "absent");
  if (state === "not_configured") {
    return "Not set up";
  }
  if (state === "unavailable") {
    return "Unavailable";
  }
  if (state === "present") {
    return resolveMembershipStatus(entry) === "disabled" ? "Disabled" : "Active";
  }
  return "Not in platform";
}

function platformDetailText(entry) {
  const state = entry.check_state || (entry.present ? "present" : "absent");
  if (state === "not_configured") {
    return entry.message || "Not configured on this server.";
  }
  if (state === "unavailable") {
    return entry.message || "Could not check this platform right now.";
  }
  if (entry.present) {
    const parts = [];
    if (entry.details?.name) {
      parts.push(entry.details.name);
    } else if (entry.details?.user_name) {
      parts.push(entry.details.user_name);
    } else if (entry.details?.first_name || entry.details?.last_name) {
      parts.push(`${entry.details.first_name || ""} ${entry.details.last_name || ""}`.trim());
    }
    if (entry.details?.role) {
      parts.push(entry.details.role);
    }
    if (entry.details?.license_name) {
      parts.push(entry.details.license_name);
    }
    if (entry.details?.status) {
      parts.push(entry.details.status);
    }
    if (entry.platform === "openspace" && entry.external_id) {
      parts.push(`account ${entry.external_id}`);
    }
    if (entry.platform === "symetri" && entry.external_id) {
      parts.push(`user ${entry.external_id}`);
    }
    if (entry.details?.count && entry.details.count > 1) {
      parts.push(`${entry.details.count} Stratus rows`);
    }
    if (parts.length) {
      return parts.join(" · ");
    }
    return resolveMembershipStatus(entry) === "disabled"
      ? "Account is disabled."
      : "Account is active.";
  }
  return entry.message || "User is not in this platform.";
}

function renderPlatformLookupResults(data, requestedEmail) {
  if (!platformLookupResults || !platformLookupList || !platformLookupSummary) {
    return;
  }

  const requestedKey = (requestedEmail || "").trim().toLowerCase();
  const returnedKey = (data.email || "").trim().toLowerCase();
  if (requestedKey && returnedKey && requestedKey !== returnedKey) {
    return;
  }

  const platforms = data.platforms || {};
  const order = PLATFORM_LOOKUP_ORDER;
  platformLookupList.innerHTML = "";

  for (const key of order) {
    const entry = platforms[key];
    if (!entry) {
      continue;
    }

    const item = document.createElement("li");
    item.className = `platform-lookup-item platform-lookup-item--${key}`;
    item.innerHTML = `
      <div>
        <p class="platform-lookup-item__name">${entry.label || key}</p>
        <p class="platform-lookup-item__detail">${platformDetailText(entry)}</p>
      </div>
      <span class="${platformBadgeClass(entry)}">${platformBadgeText(entry)}</span>
    `;
    platformLookupList.appendChild(item);
  }

  const count = data.present_count || 0;
  const activeCount = order.filter(
    (key) => platforms[key]?.present && resolveMembershipStatus(platforms[key]) === "active"
  ).length;
  const disabledCount = count - activeCount;
  let summary = `${data.email} is not in any connected platform.`;
  if (count > 0) {
    const parts = [];
    if (activeCount) {
      parts.push(`active on ${activeCount}`);
    }
    if (disabledCount) {
      parts.push(`disabled on ${disabledCount}`);
    }
    summary = `${data.email} is ${parts.join(" and ")} platform${count === 1 ? "" : "s"}.`;
  }
  platformLookupSummary.textContent = summary;
  if (platformLookupSource) {
    if (data.source === "directory") {
      if (data.directory_miss) {
        platformLookupSource.textContent = data.message || "Email not found in synced directory.";
      } else {
        const when = data.synced_at ? new Date(data.synced_at).toLocaleString() : "unknown";
        platformLookupSource.textContent = `From synced directory · last update ${when}`;
      }
      platformLookupSource.hidden = false;
    } else {
      platformLookupSource.hidden = true;
      platformLookupSource.textContent = "";
    }
  }
  platformLookupResults.hidden = false;
  if (platformLookupEmpty) {
    platformLookupEmpty.hidden = true;
  }
  lastRenderedLookupEmail = (data.email || "").trim().toLowerCase();
  clearPlatformLookupMessage();
}

async function runPlatformLookup(email) {
  const normalized = (email || "").trim();
  if (!normalized || !isValidEmail(normalized)) {
    showPlatformLookupMessage("Select a user from search or enter a full email address.", "error");
    resetPlatformLookupDisplay();
    return;
  }

  const normalizedKey = normalized.toLowerCase();
  resetPlatformLookupDisplay();

  if (platformLookupAbortController) {
    platformLookupAbortController.abort();
  }
  platformLookupAbortController = new AbortController();
  const { signal } = platformLookupAbortController;

  const requestId = ++platformLookupRequestId;
  showPlatformLookupLoading(normalized);

  if (platformLookupBtn) {
    platformLookupBtn.disabled = true;
    platformLookupBtn.textContent = "Looking up...";
  }

  try {
    const response = await fetch("/api/platforms/lookup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      signal,
      body: JSON.stringify({
        email: normalized,
        environment: currentEnvironment,
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Platform lookup failed.");
    }

    const returnedEmail = (data.email || "").trim().toLowerCase();
    const currentMembershipEmail = getMembershipEmail().toLowerCase();
    if (
      requestId !== platformLookupRequestId ||
      returnedEmail !== normalizedKey ||
      (currentMembershipEmail && currentMembershipEmail !== normalizedKey)
    ) {
      return;
    }

    renderPlatformLookupResults(data, normalized);
    if (data.directory_miss) {
      showPlatformLookupMessage(data.message, "warning");
    }
  } catch (error) {
    if (error.name === "AbortError") {
      return;
    }
    if (requestId !== platformLookupRequestId) {
      return;
    }
    resetPlatformLookupDisplay();
    showPlatformLookupMessage(error.message, "error");
  } finally {
    if (requestId === platformLookupRequestId && platformLookupBtn) {
      platformLookupBtn.disabled = false;
      platformLookupBtn.textContent = PLATFORM_LOOKUP_BTN_LABEL;
    }
  }
}

async function refreshPlatformSyncStatus() {
  if (!platformSyncStatusEl) {
    return;
  }

  try {
    const response = await fetch(`/api/platforms/sync/status?environment=${currentEnvironment}`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      platformSyncStatusEl.textContent = data.error || "Registry status unavailable.";
      return;
    }

    if (!data.synced) {
      platformSyncStatusEl.textContent = "Registry not synced yet.";
      return;
    }

    const when = data.last_sync ? new Date(data.last_sync).toLocaleString() : "recently";
    platformSyncStatusEl.textContent = `${data.user_count} users cached · last sync ${when}`;
  } catch (_error) {
    platformSyncStatusEl.textContent = "Registry status unavailable.";
  }
}

async function runPlatformSync() {
  if (!platformSyncBtn || platformSyncing) {
    return;
  }

  platformSyncing = true;
  platformSyncBtn.disabled = true;
  platformSyncBtn.textContent = "Syncing...";
  clearPlatformLookupMessage();

  try {
    const response = await fetch("/api/platforms/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ environment: currentEnvironment }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Platform sync failed.");
    }
    showPlatformLookupMessage(
      `Synced ${data.user_count} users across platforms for ${environmentLabels[currentEnvironment] || currentEnvironment}.`,
      "success"
    );
    await refreshPlatformSyncStatus();
    const email = getMembershipEmail();
    if (email && isValidEmail(email)) {
      await runPlatformLookup(email);
    }
  } catch (error) {
    showPlatformLookupMessage(error.message, "error");
  } finally {
    platformSyncing = false;
    platformSyncBtn.disabled = false;
    platformSyncBtn.textContent = PLATFORM_SYNC_BTN_LABEL;
  }
}

async function loadConfig() {
  const response = await fetch("/api/config");
  const data = await response.json();
  environmentLabels = Object.fromEntries(
    (data.environments || []).map((env) => [env.key, env.label])
  );
  stratusEnvironmentLabels = Object.fromEntries(
    (data.stratus_environments || []).map((env) => [env.key, env.label])
  );
  stratusConfiguredByEnv = Object.fromEntries(
    (data.stratus_environments || []).map((env) => [env.key, Boolean(env.configured)])
  );
  reviztoConfiguredOnServer = Boolean(data.revizto_configured);
  trackviaConfiguredOnServer = Boolean(data.trackvia_configured);
  openspaceConfiguredOnServer = Boolean(data.openspace_configured);
  symetriConfiguredOnServer = Boolean(data.symetri_configured);
  plangridConfiguredOnServer = Boolean(data.plangrid_configured);
  if (data.revizto_access_code_url) {
    reviztoAccessCodeUrl = data.revizto_access_code_url;
  }
  if (data.revizto_base_url) {
    reviztoLabel = "Revizto";
  }
  if (data.trackvia_base_url) {
    trackviaLabel = "TrackVia";
  }
  setEnvironment(currentEnvironment || data.default_environment || "dev");
}

async function refreshSyncStatus() {
  if (syncingEnvironment === currentEnvironment) {
    return;
  }

  syncStatusEl.textContent = "Checking local data...";
  syncBtn.disabled = syncingEnvironment !== null;

  try {
    const response = await fetch(`/api/sync/status?environment=${currentEnvironment}`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Unable to read sync status.");
    }

    if (!data.synced) {
      hasLocalUsers = false;
      syncStatusEl.textContent = "No local data yet. Run sync before searching.";
      return;
    }

    hasLocalUsers = true;

    const lastSync = data.last_sync
      ? `Last sync: ${new Date(data.last_sync).toLocaleString()}`
      : "Synced";
    syncStatusEl.textContent = `${data.project_count} projects, ${data.user_count} users. ${lastSync}`;
  } catch (error) {
    syncStatusEl.textContent = error.message;
  } finally {
    updateSyncButtonState();
  }
}

async function runSync() {
  if (
    currentEnvironment === "prod" &&
    !window.confirm("Sync production data from Autodesk? This replaces the local prod cache.")
  ) {
    return;
  }

  clearMessage();
  syncingEnvironment = currentEnvironment;
  setEnvToggleDisabled(true);
  updateSyncButtonState();

  try {
    const response = await fetch("/api/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ environment: currentEnvironment }),
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Sync failed.");
    }

    showMessage(
      `Synced ${data.project_count} projects and ${data.user_count} users for ${environmentLabels[currentEnvironment]}.`,
      "success"
    );
  } catch (error) {
    showMessage(error.message, "error");
  } finally {
    syncingEnvironment = null;
    setEnvToggleDisabled(false);
    updateSyncButtonState();
    await refreshSyncStatus();
  }
}

function hideMembershipSuggestions() {
  if (!membershipSuggestionsEl || !membershipEmailInput) {
    return;
  }
  membershipSuggestionsEl.hidden = true;
  membershipSuggestionsEl.innerHTML = "";
  membershipEmailInput.setAttribute("aria-expanded", "false");
  membershipActiveIndex = -1;
  membershipCurrentResults = [];
}

function showEmptyMembershipSuggestions(message) {
  if (!membershipSuggestionsEl || !membershipEmailInput) {
    return;
  }
  membershipCurrentResults = [];
  membershipActiveIndex = -1;
  membershipSuggestionsEl.innerHTML = "";
  const item = document.createElement("li");
  item.className = "suggestion-empty";
  item.textContent = message;
  membershipSuggestionsEl.appendChild(item);
  membershipSuggestionsEl.hidden = false;
  membershipEmailInput.setAttribute("aria-expanded", "true");
}

function renderMembershipSuggestions(results, hint) {
  if (!membershipSuggestionsEl || !membershipEmailInput) {
    return;
  }
  membershipCurrentResults = results;
  membershipActiveIndex = -1;
  membershipSuggestionsEl.innerHTML = "";

  if (!results.length) {
    if (hint || !hasLocalUsers) {
      showEmptyMembershipSuggestions(
        hint || "No users cached for this environment. Run Sync from Autodesk first."
      );
      return;
    }
    hideMembershipSuggestions();
    return;
  }

  for (const user of results) {
    const item = document.createElement("li");
    item.className = "suggestion-item";
    item.role = "option";
    item.innerHTML = `
      <span class="suggestion-name">${user.first_name} ${user.last_name}</span>
      <span class="suggestion-email">${user.email}${user.status === "inactive" ? " · disabled" : ""}</span>
    `;
    item.addEventListener("mousedown", (event) => {
      event.preventDefault();
      selectMembershipUser(user);
    });
    membershipSuggestionsEl.appendChild(item);
  }

  membershipSuggestionsEl.hidden = false;
  membershipEmailInput.setAttribute("aria-expanded", "true");
}

function highlightMembershipSuggestion() {
  if (!membershipSuggestionsEl) {
    return;
  }
  const items = membershipSuggestionsEl.querySelectorAll(".suggestion-item");
  items.forEach((item, index) => {
    item.classList.toggle("is-active", index === membershipActiveIndex);
  });
  if (membershipActiveIndex >= 0 && items[membershipActiveIndex]) {
    items[membershipActiveIndex].scrollIntoView({ block: "nearest" });
  }
}

async function selectMembershipUser(user) {
  cancelInFlightPlatformLookup();
  resetPlatformLookupDisplay();
  membershipEmailInput.value = user.email;
  await runPlatformLookup(user.email);
  hideMembershipSuggestions();
}

async function fetchSuggestions(query) {
  const response = await fetch(
    `/api/users/search?q=${encodeURIComponent(query)}&environment=${currentEnvironment}`
  );
  const data = await response.json().catch(() => ({ results: [] }));

  if (!response.ok) {
    throw new Error(data.error || "Search failed.");
  }

  return { results: data.results || [], hint: data.hint || null };
}

if (membershipEmailInput) {
  membershipEmailInput.addEventListener("input", () => {
    cancelInFlightPlatformLookup();
    resetPlatformLookupDisplay();

    const query = membershipEmailInput.value.trim();
    clearTimeout(membershipSearchTimer);

    if (query.length < 2) {
      hideMembershipSuggestions();
      return;
    }

    membershipSearchTimer = setTimeout(async () => {
      try {
        const { results, hint } = await fetchSuggestions(query);
        renderMembershipSuggestions(results, hint);
      } catch (error) {
        hideMembershipSuggestions();
        showPlatformLookupMessage(error.message, "error");
      }
    }, 250);
  });

  membershipEmailInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      if (!membershipSuggestionsEl.hidden && membershipActiveIndex >= 0) {
        selectMembershipUser(membershipCurrentResults[membershipActiveIndex]);
        return;
      }
      if (!membershipSuggestionsEl.hidden && membershipCurrentResults.length === 1) {
        selectMembershipUser(membershipCurrentResults[0]);
        return;
      }
      runPlatformLookup(getMembershipEmail());
      return;
    }

    if (membershipSuggestionsEl.hidden || !membershipCurrentResults.length) {
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      membershipActiveIndex = Math.min(
        membershipActiveIndex + 1,
        membershipCurrentResults.length - 1
      );
      highlightMembershipSuggestion();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      membershipActiveIndex = Math.max(membershipActiveIndex - 1, 0);
      highlightMembershipSuggestion();
    } else if (event.key === "Escape") {
      hideMembershipSuggestions();
    }
  });

  membershipEmailInput.addEventListener("blur", () => {
    setTimeout(hideMembershipSuggestions, 150);
  });
}

disableForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitAccountAction({
    endpoint: "/api/disable",
    activeBtn: submitBtn,
    otherBtn: activateBtn,
    loadingText: "Disabling...",
    defaultText: "Disable account",
    successFallback: "Disable request submitted. OpenSpace and Symetri remove the user; other platforms are disabled.",
    requireConfirm: true,
  });
});

activateBtn.addEventListener("click", async () => {
  const confirmed = window.confirm(
    `Activate ${getActionEmail() || "this user"} across connected platforms?`
  );
  if (!confirmed) {
    return;
  }
  await submitAccountAction({
    endpoint: "/api/activate",
    activeBtn: activateBtn,
    otherBtn: submitBtn,
    loadingText: "Activating...",
    defaultText: "Activate account",
    successFallback: "Activate request submitted for ACC, Stratus, Revizto, and TrackVia. OpenSpace and Symetri are skipped on activate.",
  });
});

async function submitAccountAction({
  endpoint,
  activeBtn,
  otherBtn,
  loadingText,
  defaultText,
  successFallback,
  requireConfirm = false,
}) {
  clearMessage();

  const email = getActionEmail();
  const userId = actionUserIdInput?.value.trim() || "";

  if (!email) {
    showMessage("Enter the email address to change in the disable section.", "error");
    return;
  }

  if (!isValidEmail(email)) {
    showMessage("Enter a valid email address in the disable section.", "error");
    return;
  }

  if (requireConfirm) {
    const confirmed = window.confirm(
      `Disable ${email} across connected platforms?\n\nThis affects ACC, Stratus, Revizto, TrackVia, and may remove them from OpenSpace/Symetri.`
    );
    if (!confirmed) {
      return;
    }
  }

  activeBtn.disabled = true;
  otherBtn.disabled = true;
  activeBtn.textContent = loadingText;

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        user_id: userId || undefined,
        environment: currentEnvironment,
      }),
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(data.detail || data.error || data.message || "Something went wrong.");
    }

    const messageType = data.partial ? "warning" : "success";
    showMessage(data.message || successFallback, messageType);
    refreshStratusHealth();
    refreshReviztoHealth();
    refreshTrackviaHealth();
    refreshOpenspaceHealth();
    refreshSymetriHealth();
    refreshPlangridHealth();
    if (membershipEmailInput) {
      membershipEmailInput.value = email;
    }
    await runPlatformLookup(email);
  } catch (error) {
    showMessage(error.message, "error");
  } finally {
    activeBtn.disabled = false;
    otherBtn.disabled = false;
    activeBtn.textContent = defaultText;
  }
}

envButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setEnvironment(button.dataset.environment);
  });
});

syncBtn.addEventListener("click", runSync);
if (platformLookupBtn) {
  platformLookupBtn.addEventListener("click", async () => {
    await runPlatformLookup(getMembershipEmail());
  });
}
if (platformSyncBtn) {
  platformSyncBtn.addEventListener("click", runPlatformSync);
}
if (symetriFixBtn) {
  symetriFixBtn.addEventListener("click", () => openSessionFixDialog("symetri"));
}
if (symetriReconnectBtn) {
  symetriReconnectBtn.addEventListener("click", () => startSymetriReconnect());
}
symetriReconnectOpenLoginBtn?.addEventListener("click", () => {
  window.open(PLATFORM_LOGIN_URLS.symetri, "_blank", "noopener");
});
symetriReconnectAutoBtn?.addEventListener("click", async () => {
  symetriReconnectDialog?.close();
  await startSymetriReconnect();
});
symetriReconnectSaveBtn?.addEventListener("click", () => saveSymetriBearerToken());
if (stratusFixBtn) {
  stratusFixBtn.addEventListener("click", () => openSessionFixDialog("stratus"));
}
if (reviztoFixBtn) {
  reviztoFixBtn.addEventListener("click", () => openSessionFixDialog("revizto"));
}
if (stratusReconnectBtn) {
  stratusReconnectBtn.addEventListener("click", () => startPlatformReconnect("stratus"));
}
if (reviztoReconnectBtn) {
  reviztoReconnectBtn.addEventListener("click", () => openReviztoReconnectDialog());
}
reviztoReconnectOpenLoginBtn?.addEventListener("click", () => {
  window.open(reviztoAccessCodeUrl, "_blank", "noopener");
});
reviztoReconnectAutoBtn?.addEventListener("click", () => {
  reviztoReconnectDialog?.close();
  startReviztoReconnect();
});
reviztoReconnectSaveBtn?.addEventListener("click", () => saveReviztoAccessCode());
loadExtensionInfo().then(async () => {
  await loadConfig();
  startHealthPolling();
  if (new URLSearchParams(window.location.search).has("symetri_manual")) {
    openSymetriReconnectDialog();
  }
});
