import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    token: str

    @classmethod
    def from_environment(cls):
        token = os.environ.get("TALKING_PAGE_TOKEN", "")
        host = os.environ.get("TALKING_PAGE_HOST", "127.0.0.1")
        port = int(os.environ.get("TALKING_PAGE_PORT", "8765"))
        if len(token) < 32:
            raise ValueError("TALKING_PAGE_TOKEN must contain at least 32 characters")
        if host not in {"127.0.0.1", "localhost"}:
            raise ValueError("TALKING_PAGE_HOST must be loopback-only")
        if not 1024 <= port <= 65535:
            raise ValueError("TALKING_PAGE_PORT must be between 1024 and 65535")
        return cls("127.0.0.1", port, token)


@dataclass(frozen=True)
class CachedAudio:
    audio: bytes
    duration_ms: int
    created_at: float


class SessionCache:
    def __init__(self, ttl_seconds=10_800):
        self.ttl_seconds = ttl_seconds
        self.sessions = {}

    def put(self, session_id, chunk_index, audio, duration_ms, now):
        self.purge(now)
        self.sessions.setdefault(session_id, {})[chunk_index] = CachedAudio(audio, duration_ms, now)

    def get(self, session_id, chunk_index, now):
        self.purge(now)
        return self.sessions.get(session_id, {}).get(chunk_index)

    def clear(self, session_id):
        self.sessions.pop(session_id, None)

    def purge(self, now):
        for session_id, chunks in list(self.sessions.items()):
            active = {
                index: cached
                for index, cached in chunks.items()
                if now - cached.created_at <= self.ttl_seconds
            }
            if active:
                self.sessions[session_id] = active
            else:
                self.sessions.pop(session_id, None)


def count_words(text):
    return len(re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", text))


def validate_chunk(text):
    if not text.strip():
        raise ValueError("text cannot be empty")
    if len(text) > 2000:
        raise ValueError("text cannot exceed 2,000 characters")


def prepare_text(text):
    validate_chunk(text)
    paragraphs = re.split(r"\s*\n\s*\n\s*", text.strip())
    normalized = [re.sub(r"\s+", " ", paragraph).strip() for paragraph in paragraphs]
    return " ".join(
        paragraph if paragraph.endswith((".", "!", "?", ":", ";")) else f"{paragraph}."
        for paragraph in normalized
        if paragraph
    )
