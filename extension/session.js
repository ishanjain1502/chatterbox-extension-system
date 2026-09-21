export const SESSION_TTL_MS = 10_800_000;

export function createSession(tabId, url, chunks, now = Date.now()) {
  const websiteName = new URL(url).hostname;
  return {
    id: `${tabId}-${websiteName}`,
    tabId,
    websiteName,
    startedAt: now,
    phase: "generating",
    chunks: chunks.map((chunk, index) => ({ ...chunk, index, attempts: 0, status: "pending" })),
  };
}

export function sessionExpiresAt(session) {
  return session.startedAt + SESSION_TTL_MS;
}

export function isSessionExpired(session, now = Date.now()) {
  return now >= sessionExpiresAt(session);
}

export function scheduleSessionExpiry(session, onExpire, now = Date.now()) {
  const remainingMs = sessionExpiresAt(session) - now;
  if (remainingMs <= 0) {
    onExpire();
    return null;
  }
  return setTimeout(onExpire, remainingMs);
}
