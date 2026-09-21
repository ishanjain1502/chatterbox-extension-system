export function encodeAudioBytes(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

export function decodeAudioBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

export function normalizeAudioBytes(value) {
  if (value == null) {
    throw new Error("invalid audio bytes payload");
  }
  if (typeof value === "string") {
    return decodeAudioBytes(value);
  }
  if (ArrayBuffer.isView(value)) {
    return value.buffer.slice(value.byteOffset, value.byteOffset + value.byteLength);
  }
  if (typeof value === "object" && typeof value.byteLength === "number" && typeof value.slice === "function") {
    return value.slice(0);
  }
  if (value?.data && Array.isArray(value.data)) {
    return new Uint8Array(value.data).buffer;
  }
  throw new Error("invalid audio bytes payload");
}
