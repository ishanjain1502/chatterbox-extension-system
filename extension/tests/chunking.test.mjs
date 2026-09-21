import assert from "node:assert/strict";
import test from "node:test";

import { chunkText } from "../chunking.js";

test("rejects text above 10000 words before creating chunks", () => {
  assert.throws(() => chunkText("word ".repeat(10_001)), /10,000/);
});

test("keeps sentences together and gives a paragraph a pause", () => {
  const chunks = chunkText("First sentence. Second sentence.\n\nFinal sentence.");

  assert.deepEqual(chunks.map((chunk) => chunk.text), ["First sentence. Second sentence.", "Final sentence."]);
  assert.equal(chunks[0].gapAfterMs, 450);
});
