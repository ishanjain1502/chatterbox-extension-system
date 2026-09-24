import { PairingStore } from "./pairing-store.js";

const store = new PairingStore(chrome.storage.local);
const form = document.getElementById("pair-form");
const tokenInput = document.getElementById("token");
const statusEl = document.getElementById("status");
const pairedPanel = document.getElementById("paired-panel");
const setupPanel = document.getElementById("setup-panel");

async function checkHealth(endpoint) {
  const response = await fetch(`${endpoint}/v1/health`);
  if (!response.ok) {
    throw new Error("health check failed");
  }
  const payload = await response.json();
  if (payload.status !== "ready") {
    throw new Error("service not ready");
  }
}

function setStatus(message, tone = "muted") {
  statusEl.textContent = message;
  statusEl.dataset.tone = tone;
}

function showSetup(show) {
  setupPanel.hidden = !show;
  pairedPanel.hidden = show;
}

async function refreshStatus() {
  const pairing = await store.get();
  if (!pairing) {
    showSetup(true);
    setStatus("Enter the same token you used to start the local service.");
    return;
  }

  showSetup(false);
  tokenInput.value = pairing.token;

  const sessionState = await chrome.runtime.sendMessage({ type: "get-popup-state" });
  if (sessionState?.popupState?.message) {
    setStatus(sessionState.popupState.message, sessionState.popupState.phase === "failed" ? "error" : "ok");
  } else {
    setStatus("Checking local service...");
  }

  try {
    await checkHealth(pairing.endpoint);
    if (!sessionState?.readerSession) {
      setStatus(sessionState?.popupState?.message || "Connected. Local service is ready.", "ok");
    }
  } catch {
    setStatus(
      "Local service unavailable. Start it in a terminal, confirm http://127.0.0.1:8765/v1/health returns ready, then click Reconnect.",
      "error",
    );
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const token = tokenInput.value.trim();

  try {
    await store.save({ token });
    await refreshStatus();
  } catch (error) {
    setStatus(error.message, "error");
  }
});

document.getElementById("reconnect").addEventListener("click", refreshStatus);
document.getElementById("forget").addEventListener("click", async () => {
  await store.clear();
  tokenInput.value = "";
  await refreshStatus();
});

document.getElementById("read-selection").addEventListener("click", async () => {
  const result = await chrome.runtime.sendMessage({ type: "start-read", mode: "selection" });
  if (!result?.ok) {
    setStatus(result?.error || "Could not start reading.", "error");
    return;
  }
  await refreshStatus();
});

document.getElementById("read-page").addEventListener("click", async () => {
  const result = await chrome.runtime.sendMessage({ type: "start-read", mode: "page" });
  if (!result?.ok) {
    setStatus(result?.error || "Could not start reading.", "error");
    return;
  }
  await refreshStatus();
});

document.getElementById("play").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "play-read" });
});

document.getElementById("pause").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "pause-read" });
});

document.getElementById("stop").addEventListener("click", async () => {
  await chrome.runtime.sendMessage({ type: "stop-read" });
  await refreshStatus();
});

refreshStatus();
setInterval(refreshStatus, 2000);
