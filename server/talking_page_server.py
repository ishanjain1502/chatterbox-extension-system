import os
import re
import struct
import hmac
import json
import time
import wave
from io import BytesIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


@dataclass
class CachedSession:
    created_at: float
    chunks: dict


class SessionCache:
    def __init__(self, ttl_seconds=10_800):
        self.ttl_seconds = ttl_seconds
        self.sessions = {}

    def put(self, session_id, chunk_index, audio, duration_ms, now):
        self.purge(now)
        session = self.sessions.get(session_id)
        if session is None:
            session = CachedSession(created_at=now, chunks={})
            self.sessions[session_id] = session
        session.chunks[chunk_index] = CachedAudio(audio, duration_ms, now)

    def get(self, session_id, chunk_index, now):
        self.purge(now)
        session = self.sessions.get(session_id)
        if session is None:
            return None
        return session.chunks.get(chunk_index)

    def clear(self, session_id):
        self.sessions.pop(session_id, None)

    def purge(self, now):
        for session_id, session in list(self.sessions.items()):
            if now - session.created_at > self.ttl_seconds:
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


class Service:
    def __init__(self, settings, engine):
        self.settings = settings
        self.engine = engine
        self.cache = SessionCache()

    def _authorize(self, token):
        if not hmac.compare_digest(self.settings.token, token or ""):
            raise PermissionError("invalid pairing token")

    def synthesize(self, token, session_id, chunk_index, text, now=None):
        self._authorize(token)
        generated = self.engine.synthesize(prepare_text(text))
        self.cache.put(session_id, chunk_index, generated.audio, generated.duration_ms, now or time.monotonic())
        return generated

    def cached(self, token, session_id, chunk_index, now=None):
        self._authorize(token)
        return self.cache.get(session_id, chunk_index, now or time.monotonic())

    def clear(self, token, session_id):
        self._authorize(token)
        self.cache.clear(session_id)


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def send_bytes(self, status, content_type, body, duration_ms=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if duration_ms is not None:
                self.send_header("X-Talking-Page-Duration-Ms", str(duration_ms))
            self.end_headers()
            self.wfile.write(body)

        def session_path(self):
            parts = self.path.strip("/").split("/")
            if len(parts) != 5 or parts[0:2] != ["v1", "sessions"] or parts[3] != "chunks":
                return None
            try:
                return parts[2], int(parts[4])
            except ValueError:
                return None

        def do_GET(self):
            if self.path == "/v1/health":
                self.send_bytes(200, "application/json", b'{"status":"ready"}')
                return
            route = self.session_path()
            if not route:
                self.send_error(404)
                return
            try:
                cached = service.cached(self.headers.get("X-Talking-Page-Token"), *route)
            except PermissionError:
                self.send_error(401)
                return
            if cached is None:
                self.send_error(404)
                return
            self.send_bytes(200, "audio/wav", cached.audio, cached.duration_ms)

        def do_POST(self):
            route = self.session_path()
            if not route:
                self.send_error(404)
                return
            try:
                payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                generated = service.synthesize(self.headers.get("X-Talking-Page-Token"), *route, payload["text"])
            except PermissionError:
                self.send_error(401)
                return
            except (KeyError, ValueError, json.JSONDecodeError):
                self.send_error(422)
                return
            except Exception:
                self.send_error(502)
                return
            self.send_bytes(200, "audio/wav", generated.audio, generated.duration_ms)

        def do_DELETE(self):
            parts = self.path.strip("/").split("/")
            if len(parts) != 3 or parts[0:2] != ["v1", "sessions"]:
                self.send_error(404)
                return
            try:
                service.clear(self.headers.get("X-Talking-Page-Token"), parts[2])
            except PermissionError:
                self.send_error(401)
                return
            self.send_response(204)
            self.end_headers()

    return Handler


def run():
    settings = Settings.from_environment()
    engine = NanoEngine()
    engine.load()
    ThreadingHTTPServer((settings.host, settings.port), make_handler(Service(settings, engine))).serve_forever()


if __name__ == "__main__":
    run()
