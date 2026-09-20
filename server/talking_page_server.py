import os
import re
import struct
import wave
from io import BytesIO
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


@dataclass(frozen=True)
class GeneratedAudio:
    audio: bytes
    duration_ms: int


class NanoEngine:
    def __init__(self, factory=None):
        self.factory = factory or self._load_model
        self.model = None

    @staticmethod
    def _load_model(device, nano):
        from chatterbox.tts_turbo import ChatterboxTurboTTS

        return ChatterboxTurboTTS.from_pretrained(device=device, nano=nano)

    def load(self):
        if self.model is None:
            self.model = self.factory("cpu", True)

    def synthesize(self, text):
        self.load()
        samples = self.model.generate(text)
        if hasattr(samples, "detach"):
            samples = samples.detach().cpu().flatten().tolist()
        elif samples and isinstance(samples[0], (list, tuple)):
            samples = samples[0]
        pcm = b"".join(struct.pack("<h", max(-32768, min(32767, round(sample * 32767)))) for sample in samples)
        output = BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.model.sr)
            wav.writeframes(pcm)
        return GeneratedAudio(output.getvalue(), max(1, round(len(samples) * 1000 / self.model.sr)))
