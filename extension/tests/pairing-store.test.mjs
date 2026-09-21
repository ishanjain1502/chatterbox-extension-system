import assert from "node:assert/strict";
import test from "node:test";

import { PairingStore, validatePairing } from "../pairing-store.js";

function fakeChromeStorage() {
  const data = {};
  return {
    async get(key) {
      return key === "pairing" ? { pairing: data.pairing } : data;
    },
    async set(values) {
      Object.assign(data, values);
    },
    async remove(key) {
      delete data[key];
    },
  };
}

test("stores only the local endpoint and token", async () => {
  const store = new PairingStore(fakeChromeStorage());
  await store.save({ endpoint: "http://127.0.0.1:8765", token: "a".repeat(32) });

  assert.deepEqual(await store.get(), {
    endpoint: "http://127.0.0.1:8765",
    token: "a".repeat(32),
  });
});

test("rejects a non-loopback endpoint", () => {
  assert.throws(
    () => validatePairing({ endpoint: "https://example.com", token: "a".repeat(32) }),
    /loopback/,
  );
});

test("rejects a short token", () => {
  assert.throws(
    () => validatePairing({ endpoint: "http://127.0.0.1:8765", token: "short" }),
    /32 characters/,
  );
});
