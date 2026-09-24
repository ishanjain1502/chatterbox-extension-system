import { normalizeAudioBytes } from "./binary.js";

export class AudioController {
  constructor(audioElement, mediaSession, sendMessage = () => {}) {
    this.audio = audioElement;
    this.mediaSession = mediaSession;
    this.sendMessage = sendMessage;
    this.queue = [];
    this.playing = false;
    this.paused = false;
    this.currentUrl = null;
    this._activeChunkIndex = null;
    this.audio.volume = 1;
    this.#bindMediaSession();
  }

  #bindMediaSession() {
    if (!this.mediaSession) return;

    this.mediaSession.setActionHandler("play", () => {
      this.play();
    });
    this.mediaSession.setActionHandler("pause", () => {
      this.pause();
    });
    this.mediaSession.setActionHandler("stop", () => {
      this.stop();
    });
  }

  #setPlaybackState(state) {
    if (this.mediaSession) {
      this.mediaSession.playbackState = state;
    }
  }

  #revokeCurrentUrl() {
    if (this.currentUrl) {
      URL.revokeObjectURL(this.currentUrl);
      this.currentUrl = null;
    }
  }

  #toArrayBuffer(bytes) {
    return normalizeAudioBytes(bytes);
  }

  #setSource(bytes) {
    this.#revokeCurrentUrl();
    const buffer = this.#toArrayBuffer(bytes);
    this.currentUrl = URL.createObjectURL(new Blob([new Uint8Array(buffer)], { type: "audio/wav" }));
    this.audio.src = this.currentUrl;
  }

  async #waitForCanPlay() {
    if (this.audio.readyState >= 3) return;

    await new Promise((resolve, reject) => {
      const onReady = () => {
        cleanup();
        resolve();
      };
      const onError = () => {
        cleanup();
        reject(new Error("audio decode failed"));
      };
      const cleanup = () => {
        this.audio.removeEventListener("canplaythrough", onReady);
        this.audio.removeEventListener("error", onError);
      };

      this.audio.addEventListener("canplaythrough", onReady, { once: true });
      this.audio.addEventListener("error", onError, { once: true });
      this.audio.load();
    });
  }

  async enqueue({ bytes, audioBase64, gapAfterMs, chunkIndex }) {
    this.queue.push({ bytes: audioBase64 ?? bytes, gapAfterMs, chunkIndex });
    await this.#playQueue();
  }

  async restore({ bytes, audioBase64, currentTime = 0, chunkIndex }) {
    this.queue.length = 0;
    this._activeChunkIndex = chunkIndex;
    this.#setSource(audioBase64 ?? bytes);
    await this.#waitForCanPlay();
    this.audio.currentTime = currentTime;
    await this.play();
  }

  async play() {
    if (this.playing && this.paused) {
      this.paused = false;
      await this.audio.play();
      this.#setPlaybackState("playing");
      this.sendMessage({ type: "audio-resumed", chunkIndex: this._activeChunkIndex });
      return;
    }

    if (!this.playing) {
      await this.#playQueue();
    }
  }

  pause() {
    if (!this.playing || this.paused) return;
    this.paused = true;
    this.audio.pause();
    this.#setPlaybackState("paused");
    this.sendMessage({
      type: "audio-paused",
      chunkIndex: this._activeChunkIndex,
      currentTime: this.audio.currentTime,
    });
  }

  stop() {
    this.queue.length = 0;
    this.playing = false;
    this.paused = false;
    this.audio.pause();
    this.#revokeCurrentUrl();
    this._activeChunkIndex = null;
    this.#setPlaybackState("none");
    this.sendMessage({ type: "playback-stopped" });
  }

  currentChunkIndex() {
    return this._activeChunkIndex;
  }

  async #playQueue() {
    if (this.playing || this.queue.length === 0) return;
    this.playing = true;
    this.paused = false;

    if (this.mediaSession && globalThis.MediaMetadata) {
      this.mediaSession.metadata = new MediaMetadata({
        title: "Talking Page",
        artist: "Local narration",
      });
    }

    while (this.queue.length > 0 && !this.paused) {
      const { bytes, gapAfterMs, chunkIndex } = this.queue.shift();
      this._activeChunkIndex = chunkIndex;
      this.#setSource(bytes);

      try {
        await this.#waitForCanPlay();
        this.sendMessage({ type: "audio-started", chunkIndex });

        await new Promise((resolve, reject) => {
          this.audio.onended = resolve;
          this.audio.onerror = () => reject(new Error("audio playback failed"));
          this.audio.play().then(() => this.#setPlaybackState("playing")).catch(reject);
        });

        this.sendMessage({ type: "audio-ended", chunkIndex });

        if (gapAfterMs > 0 && !this.paused) {
          await new Promise((resolve) => setTimeout(resolve, gapAfterMs));
        }
      } catch (error) {
        this.sendMessage({ type: "audio-error", error: error.message });
        throw error;
      }
    }

    if (!this.paused) {
      this.#revokeCurrentUrl();
      this.playing = false;
      this._activeChunkIndex = null;
      this.#setPlaybackState("none");
      this.sendMessage({ type: "playback-idle" });
    }
  }
}
