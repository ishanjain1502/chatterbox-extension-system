import { chunkText } from "./chunking.js";
import { createSession } from "./session.js";
import { SessionManager } from "./session-manager.js";

export function createWorkerHarness(options = {}) {
  const popupState = { message: "" };

  const readyProvider = {
    calls: 0,
    cleared: [],
    async synthesize() {
      this.calls += 1;
      return { bytes: new ArrayBuffer(8), durationMs: 500 };
    },
    async clearSession(sessionId) {
      this.cleared.push(sessionId);
    },
  };

  const harnessManager = new SessionManager(options.provider || readyProvider, () => {});
  const harness = {
    manager: harnessManager,
    popupState,
    async onContextMenu(info, tab) {
      if (info.menuItemId === "read-selection") {
        const chunks = chunkText(info.selectionText.trim());
        const session = createSession(tab.id, tab.url, chunks);
        harnessManager.startedWith = session;
        await harnessManager.start(session);
        return;
      }

      if (info.menuItemId === "read-page") {
        const articleResult = options.articleResult || { ok: true, text: "x".repeat(201) };
        if (!articleResult.ok) {
          popupState.message = "Could not find a main article on this page. Please select text instead.";
          return;
        }
        const session = createSession(tab.id, tab.url, chunkText(articleResult.text));
        await harnessManager.start(session);
      }
    },
    async onTabUpdated(tabId, changeInfo) {
      if (changeInfo.status === "loading" && harnessManager.currentSession()?.tabId === tabId) {
        await harnessManager.stop();
      }
    },
  };

  return harness;
}
