import assert from "node:assert/strict";
import test from "node:test";

import { AudioController } from "../audio-controller.js";

class FakeAudioElement {
  constructor() {
    this.src = "";
    this.currentTime = 0;
    this.volume = 1;
    this.readyState = 4;
    this.playedSources = [];
    this.onended = null;
    this.onerror = null;
  }

  load() {}

  addEventListener(event, handler) {
    if (event === "canplaythrough") {
      queueMicrotask(handler);
    }
  }

  removeEventListener() {}

  play() {
    this.playedSources.push(this.src);
    queueMicrotask(() => this.onended?.());
    return Promise.resolve();
  }

  pause() {}
}

const fakeMediaSession = {
  metadata: null,
  playbackState: "none",
  setActionHandler() {},
};

function wavBytes(label) {
  return new TextEncoder().encode(label).buffer;
}

test("plays queued WAV chunks in order and observes their gaps", async () => {
  const audio = new FakeAudioElement();
  const controller = new AudioController(audio, fakeMediaSession);
  await controller.enqueue({ bytes: wavBytes("one"), gapAfterMs: 0, chunkIndex: 0 });
  await controller.enqueue({ bytes: wavBytes("two"), gapAfterMs: 0, chunkIndex: 1 });
  assert.equal(audio.playedSources.length, 2);
});

test("recreates current playback from cached bytes after an offscreen restart", async () => {
  const controller = new AudioController(new FakeAudioElement(), fakeMediaSession);
  await controller.restore({ bytes: wavBytes("cached"), currentTime: 1.2, chunkIndex: 3 });
  assert.equal(controller.currentChunkIndex(), 3);
});
