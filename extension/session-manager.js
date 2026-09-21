import { isSessionExpired, scheduleSessionExpiry } from "./session.js";

const MAX_ATTEMPTS = 3;

export class SessionManager {
  constructor(provider, onEvent) {
    this.provider = provider;
    this.onEvent = onEvent;
    this.session = null;
    this.expiryTimer = null;
    this.processing = false;
    this.playback = { chunkIndex: null, currentTime: 0, paused: false };
  }

  currentSession() {
    return this.session;
  }

  playbackState() {
    return { ...this.playback };
  }

  async start(session) {
    if (this.session) {
      await this.provider.clearSession(this.session.id);
    }

    this.session = session;
    this.playback = { chunkIndex: null, currentTime: 0, paused: false };
    clearTimeout(this.expiryTimer);
    this.expiryTimer = scheduleSessionExpiry(session, () => this.stop());

    this.#publishSession();
    await this.#processQueue();
  }

  async stop() {
    clearTimeout(this.expiryTimer);
    this.expiryTimer = null;
    this.processing = false;
    this.playback = { chunkIndex: null, currentTime: 0, paused: false };

    if (this.session) {
      const sessionId = this.session.id;
      this.session = null;
      await this.provider.clearSession(sessionId);
      this.onEvent("stopped", { sessionId });
    }
  }

  onAudioStarted(chunkIndex) {
    if (!this.session) return;

    const chunk = this.session.chunks.find((item) => item.index === chunkIndex);
    if (chunk && chunk.status === "ready") {
      chunk.status = "playing";
    }

    this.playback = { chunkIndex, currentTime: 0, paused: false };
    this.session.phase = "playing";
    this.#publishSession();
  }

  onAudioEnded(chunkIndex) {
    if (!this.session) return;

    const chunk = this.session.chunks.find((item) => item.index === chunkIndex);
    if (chunk) {
      chunk.status = "complete";
    }

    this.playback = { chunkIndex: null, currentTime: 0, paused: false };
    this.#updatePhase();
    this.#publishSession();
  }

  onAudioPaused(chunkIndex, currentTime) {
    if (!this.session) return;
    this.playback = { chunkIndex, currentTime, paused: true };
    this.session.phase = "paused";
    this.#publishSession();
  }

  onAudioResumed() {
    if (!this.session) return;
    this.playback.paused = false;
    this.session.phase = "playing";
    this.#publishSession();
  }

  onPlaybackStopped() {
    if (!this.session) return;
    this.session.phase = "paused";
    this.playback.paused = true;
    this.#publishSession();
  }

  async #processQueue() {
    if (this.processing || !this.session) return;
    this.processing = true;

    try {
      while (this.session && !isSessionExpired(this.session)) {
        const chunk = this.session.chunks.find((item) => item.status === "pending");
        if (!chunk) {
          this.#updatePhase();
          this.#publishSession();
          break;
        }

        chunk.status = "generating";
        this.session.phase = "generating";
        this.#publishSession();

        let ready = false;
        for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt += 1) {
          chunk.attempts = attempt + 1;
          try {
            const audio = await this.provider.synthesize(this.session.id, chunk.index, chunk.text);
            chunk.status = "ready";
            chunk.durationMs = audio.durationMs;
            this.onEvent("chunk-ready", {
              sessionId: this.session.id,
              chunkIndex: chunk.index,
              bytes: audio.bytes,
              gapAfterMs: chunk.gapAfterMs,
            });
            ready = true;
            break;
          } catch {
            // retry
          }
        }

        if (!ready) {
          chunk.status = "skipped";
          this.#publishSession();
        }
      }
    } finally {
      this.processing = false;
    }
  }

  #updatePhase() {
    if (!this.session) return;

    const chunks = this.session.chunks;
    const hasPending = chunks.some((chunk) => chunk.status === "pending" || chunk.status === "generating");
    const hasPlaying = chunks.some((chunk) => chunk.status === "playing");
    const hasSkipped = chunks.some((chunk) => chunk.status === "skipped");

    if (this.playback.paused && this.playback.chunkIndex !== null) {
      this.session.phase = "paused";
      return;
    }

    if (hasPlaying || this.playback.chunkIndex !== null) {
      this.session.phase = "playing";
      return;
    }

    if (hasPending) {
      this.session.phase = "generating";
      return;
    }

    this.session.phase = hasSkipped ? "complete with skipped chunks" : "complete";
  }

  #publishSession() {
    this.onEvent("session-updated", { session: this.session });
  }
}
