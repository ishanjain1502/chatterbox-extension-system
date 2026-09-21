import assert from "node:assert/strict";
import test from "node:test";

import { LocalProvider } from "../local-provider.js";

function fakeFetchWav(durationMs = 800) {
  const state = { lastHeaders: {} };
  const fetchFn = async (_url, options = {}) => {
    state.lastHeaders = options.headers || {};
    if (options.method === "POST") {
      return {
        ok: true,
        status: 200,
        headers: {
          get(name) {
            if (name === "Content-Type") return "audio/wav";
            if (name === "X-Talking-Page-Duration-Ms") return String(durationMs);
            return null;
          },
        },
        async arrayBuffer() {
          return new TextEncoder().encode("RIFFfake").buffer;
        },
      };
    }

    return {
      ok: true,
      status: 200,
      headers: {
        get(name) {
          if (name === "Content-Type") return "audio/wav";
          if (name === "X-Talking-Page-Duration-Ms") return String(durationMs);
          return null;
        },
      },
      async arrayBuffer() {
        return new TextEncoder().encode("RIFFcached").buffer;
      },
    };
  };

  fetchFn.lastHeaders = state.lastHeaders;
  Object.defineProperty(fetchFn, "lastHeaders", {
    get() {
      return state.lastHeaders;
    },
  });

  return fetchFn;
}

test("sends the pairing token and returns WAV bytes", async () => {
  const fetch = fakeFetchWav(800);
  const provider = new LocalProvider({ endpoint: "http://127.0.0.1:8765", token: "a".repeat(32) }, fetch);
  const result = await provider.synthesize("12-example", 0, "Hello.");

  assert.equal(fetch.lastHeaders["X-Talking-Page-Token"], "a".repeat(32));
  assert.equal(result.durationMs, 800);
});

test("returns cached audio bytes", async () => {
  const fetch = fakeFetchWav(900);
  const provider = new LocalProvider({ endpoint: "http://127.0.0.1:8765", token: "a".repeat(32) }, fetch);
  const result = await provider.getCachedAudio("12-example", 2);

  assert.equal(result.durationMs, 900);
});
