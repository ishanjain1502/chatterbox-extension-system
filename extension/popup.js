import { EXTENSION_VOICE_SESSION_ID, LocalProvider } from "./local-provider.js";
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

async function getProvider() {
  const pairing = await store.get();
  if (!pairing) return null;
  return new LocalProvider(pairing);
}

async function uploadVoiceFile(file) {
  if (!file) return;
  const provider = await getProvider();
  if (!provider) {
    setStatus("Pair the local service before uploading a voice sample.", "error");
    return;
  }
  const bytes = await file.arrayBuffer();
  try {
    await provider.uploadSessionVoice(EXTENSION_VOICE_SESSION_ID, bytes);
    setStatus("Custom voice uploaded. New reads will use it.", "ok");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function clearExtensionVoice() {
  const provider = await getProvider();
  if (!provider) {
    setStatus("Pair the local service first.", "error");
    return;
  }
  try {
    await provider.clearSessionVoice(EXTENSION_VOICE_SESSION_ID);
    setStatus("Using server default voice (env sample or built-in).", "ok");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

function bindVoiceInput(input) {
  input?.addEventListener("change", async () => {
    const file = input.files?.[0];
    input.value = "";
    await uploadVoiceFile(file);
  });
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
    const provider = await getProvider();
    const voiceStatus = await provider.getVoiceStatus();
    const voiceHint = voiceStatus.extension_voice
      ? " Custom extension voice active."
      : voiceStatus.default_mode === "env"
        ? " Server env voice active."
        : " Built-in voice active.";
    if (!sessionState?.readerSession) {
      setStatus((sessionState?.popupState?.message || "Connected. Local service is ready.") + voiceHint, "ok");
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

bindVoiceInput(document.getElementById("voice-file"));
bindVoiceInput(document.getElementById("voice-file-paired"));
document.getElementById("clear-voice").addEventListener("click", clearExtensionVoice);
document.getElementById("clear-voice-paired").addEventListener("click", clearExtensionVoice);

refreshStatus();
setInterval(refreshStatus, 2000);
