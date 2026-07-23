document.documentElement.dataset.sessionSyncExtension = "installed";
window.dispatchEvent(new CustomEvent("session-sync-extension-ready"));

window.addEventListener("session-sync-open-options", () => {
  chrome.runtime.sendMessage({ type: "open-options" });
});

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "session-sync-pushed") {
    window.dispatchEvent(
      new CustomEvent("session-sync-pushed", { detail: message.detail || {} })
    );
  }
});
