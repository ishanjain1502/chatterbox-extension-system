import assert from "node:assert/strict";
import test from "node:test";

import { decodeAudioBytes, encodeAudioBytes, normalizeAudioBytes } from "../binary.js";

test("round-trips audio bytes through base64", () => {
  const original = new Uint8Array([0x52, 0x49, 0x46, 0x46, 0x00, 0x00]).buffer;
  const encoded = encodeAudioBytes(original);
  const decoded = decodeAudioBytes(encoded);

  assert.equal(new Uint8Array(decoded).join(","), new Uint8Array(original).join(","));
});

test("accepts raw array buffers and base64 strings", () => {
  const original = new Uint8Array([1, 2, 3]).buffer;
  const encoded = encodeAudioBytes(original);

  assert.equal(new Uint8Array(normalizeAudioBytes(original)).join(","), "1,2,3");
  assert.equal(new Uint8Array(normalizeAudioBytes(encoded)).join(","), "1,2,3");
});
