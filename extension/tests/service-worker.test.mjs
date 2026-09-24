import assert from "node:assert/strict";
import test from "node:test";

import { createWorkerHarness } from "../worker-harness.js";
import { createSession } from "../session.js";

function makeSession(texts, tabId = 8, url = "https://example.com/a", now = Date.now()) {
  return createSession(
    tabId,
    url,
    texts.map((text) => ({ text, gapAfterMs: 0 })),
    now,
  );
}

test("selection command requests selection extraction from the active tab", async () => {
  const worker = createWorkerHarness();
  await worker.onContextMenu(
    { menuItemId: "read-selection", selectionText: "Selected words" },
    { id: 8, url: "https://example.com/a" },
  );

  assert.equal(worker.manager.startedWith?.tabId, 8);
  assert.equal(worker.manager.startedWith?.chunks[0].text, "Selected words");
});

test("navigation stops the tab session", async () => {
  const worker = createWorkerHarness();
  await worker.manager.start(makeSession(["One."]));
  await worker.onTabUpdated(8, { status: "loading" });
  assert.equal(worker.manager.currentSession(), null);
});

test("page extraction failure asks for selection", async () => {
  const worker = createWorkerHarness({ articleResult: { ok: false, reason: "select-text" } });
  await worker.onContextMenu({ menuItemId: "read-page" }, { id: 8, url: "https://example.com/a" });
  assert.match(worker.popupState.message, /select text/i);
});
