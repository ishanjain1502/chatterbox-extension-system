import { AudioController } from "./audio-controller.js";

const controller = new AudioController(
  new Audio(),
  navigator.mediaSession,
  (message) => chrome.runtime.sendMessage(message),
);

chrome.runtime.sendMessage({ type: "offscreen-ready" });

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "enqueue-chunk") {
    controller
      .enqueue(message)
      .then(() => sendResponse({ ok: true }))
      .catch((error) => {
        chrome.runtime.sendMessage({ type: "audio-error", error: error.message });
        sendResponse({ ok: false, error: error.message });
      });
    return true;
  }

  if (message.type === "restore-playback") {
    controller
      .restore(message)
      .then(() => sendResponse({ ok: true }))
      .catch((error) => {
        chrome.runtime.sendMessage({ type: "audio-error", error: error.message });
        sendResponse({ ok: false, error: error.message });
      });
    return true;
  }

  if (message.type === "play-playback") {
    controller.play().catch((error) => {
      chrome.runtime.sendMessage({ type: "audio-error", error: error.message });
    });
    sendResponse({ ok: true });
    return false;
  }

  if (message.type === "pause-playback") {
    controller.pause();
    sendResponse({ ok: true });
    return false;
  }

  if (message.type === "stop-playback") {
    controller.stop();
    sendResponse({ ok: true });
    return false;
  }

  return false;
});

export { controller };
