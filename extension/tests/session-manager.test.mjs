import assert from "node:assert/strict";
import test from "node:test";

import { SessionManager } from "../session-manager.js";
import { createSession } from "../session.js";

function makeSession(texts, tabId = 12, url = "https://example.com/a", now = Date.now()) {
  return createSession(
    tabId,
    url,
    texts.map((text) => ({ text, gapAfterMs: 0 })),
    now,
  );
}

test("retries exactly three times and skips a failed chunk", async () => {
  const failingFirstChunkProvider = {
    calls: 0,
    cleared: [],
    async synthesize(_sessionId, chunkIndex) {
      this.calls += 1;
      if (chunkIndex === 0) throw new Error("fail");
      return { bytes: new ArrayBuffer(4), durationMs: 100 };
    },
    async clearSession() {},
  };

  const manager = new SessionManager(failingFirstChunkProvider, () => {});
  await manager.start(makeSession(["First.", "Second."]));

  assert.equal(failingFirstChunkProvider.calls, 4);
  assert.equal(manager.currentSession()?.chunks[0].status, "skipped");
  assert.equal(manager.currentSession()?.chunks[1].status, "ready");
});

test("new session clears the old provider cache before starting", async () => {
  const readyProvider = {
    calls: 0,
    cleared: [],
    async synthesize() {
      this.calls += 1;
      return { bytes: new ArrayBuffer(4), durationMs: 100 };
    },
    async clearSession(sessionId) {
      this.cleared.push(sessionId);
    },
  };

  const now = Date.now();
  const manager = new SessionManager(readyProvider, () => {});
  await manager.start(makeSession(["Old."], 1, "https://old.example/a", now));
  await manager.start(makeSession(["New."], 2, "https://new.example/a", now));

  assert.deepEqual(readyProvider.cleared, ["1-old.example"]);
  assert.equal(manager.currentSession()?.id, "2-new.example");
});
