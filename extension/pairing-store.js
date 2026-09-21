const DEFAULT_ENDPOINT = "http://127.0.0.1:8765";

export function validatePairing({ endpoint, token }) {
  if (!endpoint.startsWith("http://127.0.0.1")) {
    throw new Error("loopback endpoint required");
  }
  if (token.length < 32) {
    throw new Error("token must be at least 32 characters");
  }
}

export class PairingStore {
  constructor(storage) {
    this.storage = storage;
  }

  async save({ endpoint = DEFAULT_ENDPOINT, token }) {
    validatePairing({ endpoint, token });
    await this.storage.set({ pairing: { endpoint, token } });
  }

  async get() {
    const result = await this.storage.get("pairing");
    return result.pairing ?? null;
  }

  async clear() {
    await this.storage.remove("pairing");
  }
}
