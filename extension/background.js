import { chunkText } from "./chunking.js";
import { encodeAudioBytes } from "./binary.js";
import { LocalProvider } from "./local-provider.js";
import { PairingStore } from "./pairing-store.js";
import { createSession } from "./session.js";
import { SessionManager } from "./session-manager.js";

const pairingStore = new PairingStore(chrome.storage.local);
let manager = null;
let popupState = { message: "" };
let offscreenReadyPromise = null;

function waitForOffscreenReady() {
  if (!offscreenReadyPromise) {
    offscreenReadyPromise = new Promise((resolve) => {
      const listener = (message) => {
        if (message.type === "offscreen-ready") {
          chrome.runtime.onMessage.removeListener(listener);
          resolve();
        }
      };
      chrome.runtime.onMessage.addListener(listener);
    });
  }
  return offscreenReadyPromise;
}

async function ensureOffscreen() {
  const existing = await chrome.runtime.getContexts({
    contextTypes: ["OFFSCREEN_DOCUMENT"],
    documentUrls: [chrome.runtime.getURL("offscreen.html")],
  });

  if (existing.length === 0) {
    offscreenReadyPromise = null;
    const ready = waitForOffscreenReady();
    await chrome.offscreen.createDocument({
      url: "offscreen.html",
      reasons: ["AUDIO_PLAYBACK"],
      justification: "Play synthesized narration while the popup is closed.",
    });
    await ready;
    await restorePlaybackIfNeeded();
    return;
  }

  await waitForOffscreenReady();
}

async function sendToOffscreen(message) {
  await ensureOffscreen();
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (response) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      if (response?.ok === false) {
        reject(new Error(response.error || "offscreen playback failed"));
        return;
      }
      resolve(response);
    });
  });
}

function selectionExtractor() {
  return window.getSelection()?.toString().trim() || "";
}

function articleExtractor() {
  const node = document.querySelector("article") || document.querySelector("main");
  const text = (node?.innerText || "").replace(/\s+/g, " ").trim();
  if (text.length < 200) return null;
  return text;
}

async function restorePlaybackIfNeeded() {
  const session = manager?.currentSession();
  const playback = manager?.playbackState();
  if (!session || !playback?.paused || playback.chunkIndex === null) return;

  try {
    const provider = await getProvider();
    const cached = await provider.getCachedAudio(session.id, playback.chunkIndex);
    await sendToOffscreen({
      type: "restore-playback",
      audioBase64: encodeAudioBytes(cached.bytes),
      currentTime: playback.currentTime,
      chunkIndex: playback.chunkIndex,
    });
  } catch (error) {
    console.error("Failed to restore cached playback", error);
  }
}

async function getProvider() {
  const pairing = await pairingStore.get();
  if (!pairing) throw new Error("Pair the local service token in the extension popup first.");
  return new LocalProvider(pairing);
}

async function extractFromTab(tabId, mode) {
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId },
    func: mode === "selection" ? selectionExtractor : articleExtractor,
  });

  if (mode === "selection") {
    if (!result) throw new Error("Select some text on the page first.");
    return result;
  }

  if (!result) {
    popupState.message = "Could not find a main article on this page. Please select text instead.";
    throw new Error(popupState.message);
  }

  return result;
}

function createManager(provider) {
  return new SessionManager(provider, async (event, payload) => {
    if (event === "chunk-ready") {
      await sendToOffscreen({
        type: "enqueue-chunk",
        audioBase64: encodeAudioBytes(payload.bytes),
        gapAfterMs: payload.gapAfterMs,
        chunkIndex: payload.chunkIndex,
      });
    }

    if (event === "session-updated") {
      await chrome.storage.session.set({
        readerSession: payload.session,
        popupState: buildPopupState(payload.session),
      });
    }

    if (event === "stopped") {
      sendToOffscreen({ type: "stop-playback" }).catch(() => {});
      await chrome.storage.session.set({ readerSession: null, popupState: { message: "Stopped." } });
    }
  });
}

function buildPopupState(session) {
  if (!session) return { message: "Ready." };

  const skipped = session.chunks.filter((chunk) => chunk.status === "skipped").length;
  const messageByPhase = {
    extracting: "Extracting page text...",
    generating: "Generating speech...",
    playing: "Playing narration.",
    paused: "Paused.",
    complete: "Reading complete.",
    "complete with skipped chunks": `Reading complete with ${skipped} skipped chunk${skipped === 1 ? "" : "s"}.`,
    failed: "Reading failed.",
  };

  return {
    message: messageByPhase[session.phase] || session.phase,
    phase: session.phase,
    skippedChunks: skipped,
  };
}

async function startRead(mode) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !tab.url?.startsWith("http")) {
    throw new Error("Open a normal web page before starting a read.");
  }

  const provider = await getProvider();
  await provider.health();

  popupState.message = mode === "page" ? "Extracting page text..." : "Starting selected text...";
  await chrome.storage.session.set({ popupState: { message: popupState.message, phase: "extracting" } });

  const text = await extractFromTab(tab.id, mode);
  const chunks = chunkText(text);
  const session = createSession(tab.id, tab.url, chunks);

  manager = createManager(provider);
  await manager.start(session);
  return { sessionId: session.id, chunks: chunks.length };
}

async function stopRead() {
  try {
    await sendToOffscreen({ type: "stop-playback" });
  } catch {
    // offscreen may already be gone
  }
  if (manager) await manager.stop();
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "read-selection",
      title: "Read selection with Talking Page",
      contexts: ["selection"],
    });
    chrome.contextMenus.create({
      id: "read-page",
      title: "Read page with Talking Page",
      contexts: ["page"],
    });
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (!tab?.id) return;

  try {
    if (info.menuItemId === "read-selection") {
      if (!info.selectionText?.trim()) return;
      const provider = await getProvider();
      const chunks = chunkText(info.selectionText.trim());
      const session = createSession(tab.id, tab.url, chunks);
      manager = createManager(provider);
      await manager.start(session);
      return;
    }

    if (info.menuItemId === "read-page") {
      await startRead("page");
    }
  } catch (error) {
    console.error(error);
    await chrome.storage.session.set({ popupState: { message: error.message, phase: "failed" } });
  }
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo) => {
  if (changeInfo.status === "loading" && manager?.currentSession()?.tabId === tabId) {
    await stopRead();
  }
});

chrome.tabs.onRemoved.addListener(async (tabId) => {
  if (manager?.currentSession()?.tabId === tabId) {
    await stopRead();
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "start-read") {
    startRead(message.mode)
      .then((result) => sendResponse({ ok: true, ...result }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }

  if (message.type === "stop-read") {
    stopRead()
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }

  if (message.type === "play-read") {
    sendToOffscreen({ type: "play-playback" })
      .then(() => manager?.onAudioResumed())
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    sendResponse({ ok: true });
    return false;
  }

  if (message.type === "pause-read") {
    sendToOffscreen({ type: "pause-playback" }).catch(() => {});
    sendResponse({ ok: true });
    return false;
  }

  if (message.type === "audio-started") {
    manager?.onAudioStarted(message.chunkIndex);
  }

  if (message.type === "audio-ended") {
    manager?.onAudioEnded(message.chunkIndex);
  }

  if (message.type === "audio-paused") {
    manager?.onAudioPaused(message.chunkIndex, message.currentTime);
  }

  if (message.type === "audio-resumed") {
    manager?.onAudioResumed();
  }

  if (message.type === "playback-stopped") {
    manager?.onPlaybackStopped();
  }

  if (message.type === "audio-error") {
    console.error(message.error);
    chrome.storage.session.set({
      popupState: { message: `Playback error: ${message.error}`, phase: "failed" },
    });
  }

  if (message.type === "get-popup-state") {
    chrome.storage.session.get(["popupState", "readerSession"]).then((result) => {
      sendResponse({
        popupState: result.popupState || { message: "Ready." },
        readerSession: result.readerSession || null,
      });
    });
    return true;
  }

  return false;
});
