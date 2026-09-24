export class LocalProvider {
  constructor({ endpoint, token }, fetchFn) {
    this.endpoint = endpoint.replace(/\/$/, "");
    this.token = token;
    this.fetch = fetchFn ?? ((...args) => fetch(...args));
  }

  async health() {
    const response = await this.fetch(`${this.endpoint}/v1/health`);
    if (!response.ok) throw new Error("service unavailable");
    const payload = await response.json();
    if (payload.status !== "ready") throw new Error("service not ready");
  }

  async synthesize(sessionId, chunkIndex, text) {
    const response = await this.fetch(
      `${this.endpoint}/v1/sessions/${encodeURIComponent(sessionId)}/chunks/${chunkIndex}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Talking-Page-Token": this.token,
        },
        body: JSON.stringify({ text }),
      },
    );

    if (response.status === 401) throw new Error("unauthorized");
    if (response.status === 422) throw new Error("invalid content");
    if (response.status === 502) throw new Error("synthesis failed");
    if (response.status === 503) throw new Error("service unavailable");
    if (!response.ok) {
      throw new Error(`synthesis failed (${response.status})`);
    }

    const contentType = response.headers.get("Content-Type") || "";
    if (!contentType.includes("audio/wav")) {
      throw new Error("expected audio/wav response");
    }

    return {
      bytes: await response.arrayBuffer(),
      durationMs: Number.parseInt(response.headers.get("X-Talking-Page-Duration-Ms") || "0", 10),
    };
  }

  async getCachedAudio(sessionId, chunkIndex) {
    const response = await this.fetch(
      `${this.endpoint}/v1/sessions/${encodeURIComponent(sessionId)}/chunks/${chunkIndex}`,
      {
        headers: { "X-Talking-Page-Token": this.token },
      },
    );

    if (response.status === 404) throw new Error("cache miss");
    if (response.status === 401) throw new Error("unauthorized");
    if (!response.ok) throw new Error(`cache lookup failed (${response.status})`);

    return {
      bytes: await response.arrayBuffer(),
      durationMs: Number.parseInt(response.headers.get("X-Talking-Page-Duration-Ms") || "0", 10),
    };
  }

  async clearSession(sessionId) {
    await this.fetch(`${this.endpoint}/v1/sessions/${encodeURIComponent(sessionId)}`, {
      method: "DELETE",
      headers: { "X-Talking-Page-Token": this.token },
    });
  }
}
