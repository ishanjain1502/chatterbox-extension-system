import assert from "node:assert/strict";
import test from "node:test";

import {
  SESSION_TTL_MS,
  createSession,
  isSessionExpired,
  scheduleSessionExpiry,
  sessionExpiresAt,
} from "../session.js";

test("session identity combines Chrome tab ID and website name", () => {
  const session = createSession(12, "https://www.example.com/article", [{ text: "Hello.", gapAfterMs: 0 }], 1_000);

  assert.equal(session.id, "12-www.example.com");
  assert.equal(session.tabId, 12);
  assert.equal(session.phase, "generating");
  assert.equal(session.startedAt, 1_000);
});

test("session expires three hours after creation", () => {
  const session = createSession(12, "https://www.example.com/article", [{ text: "Hello.", gapAfterMs: 0 }], 1_000);

  assert.equal(SESSION_TTL_MS, 10_800_000);
  assert.equal(sessionExpiresAt(session), 1_000 + SESSION_TTL_MS);
  assert.equal(isSessionExpired(session, 1_000 + SESSION_TTL_MS - 1), false);
  assert.equal(isSessionExpired(session, 1_000 + SESSION_TTL_MS), true);
});

test("scheduleSessionExpiry fires at the hard session cap", () => {
  let expired = false;
  const session = createSession(12, "https://www.example.com/article", [{ text: "Hello.", gapAfterMs: 0 }], 1_000);
  const timer = scheduleSessionExpiry(session, () => {
    expired = true;
  }, 1_000 + SESSION_TTL_MS - 5);

  assert.ok(timer);
  assert.equal(expired, false);
  clearTimeout(timer);
});
