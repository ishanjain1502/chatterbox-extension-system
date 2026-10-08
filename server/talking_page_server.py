import hashlib
import os
import sys
import re
import struct
import hmac
import json
import tempfile
import threading
import time
import wave
from io import BytesIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from dataclasses import dataclass, field
from pathlib import Path

EXTENSION_VOICE_SESSION_ID = "extension-default"
MAX_VOICE_UPLOAD_BYTES = 10 * 1024 * 1024
MIN_VOICE_SECONDS = 5.0


def _ensure_project_root_on_path():
    """Allow `python server/talking_page_server.py` to import the `server` package."""
    root = Path(__file__).resolve().parent.parent
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def load_project_env():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key] = value


def _parse_tagger_enabled():
    raw = os.environ.get("TALKING_PAGE_TAGGER_ENABLED", "1").strip().lower()
    return raw not in ("0", "false")


def _parse_tag_confidence_threshold():
    raw = os.environ.get("TALKING_PAGE_TAG_CONFIDENCE_THRESHOLD", "0.65").strip()
    try:
        value = float(raw)
    except ValueError:
        raise ValueError("TALKING_PAGE_TAG_CONFIDENCE_THRESHOLD must be a number between 0 and 1")
    if not 0.0 <= value <= 1.0:
        raise ValueError("TALKING_PAGE_TAG_CONFIDENCE_THRESHOLD must be between 0 and 1")
    return value


def _default_tagger_model_path():
    return str(Path(__file__).resolve().parent / "models" / "paralinguistic_tagger.pt")


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    token: str
    voice_sample_path: str | None
    tagger_enabled: bool = True
    tag_confidence_threshold: float = 0.65
    tagger_model_path: str = field(default_factory=_default_tagger_model_path)

    @classmethod
    def from_environment(cls):
        token = os.environ.get("TALKING_PAGE_TOKEN", "")
        host = os.environ.get("TALKING_PAGE_HOST", "127.0.0.1")
        port = int(os.environ.get("TALKING_PAGE_PORT", "8765"))
        voice_raw = os.environ.get("TALKING_PAGE_VOICE_SAMPLE", "").strip()
        if len(token) < 32:
            raise ValueError("TALKING_PAGE_TOKEN must contain at least 32 characters")
        allowed_hosts = {"127.0.0.1", "localhost", "0.0.0.0"}
        if host not in allowed_hosts:
            raise ValueError(
                "TALKING_PAGE_HOST must be 127.0.0.1, localhost, or 0.0.0.0 (Docker bind)"
            )
        if not 1024 <= port <= 65535:
            raise ValueError("TALKING_PAGE_PORT must be between 1024 and 65535")
        voice_sample_path = None
        if voice_raw:
            voice_sample_path = str(Path(voice_raw).expanduser().resolve())
            if not Path(voice_sample_path).is_file():
                raise ValueError(f"TALKING_PAGE_VOICE_SAMPLE not found: {voice_sample_path}")
        bind_host = "127.0.0.1" if host == "localhost" else host
        tagger_path_raw = os.environ.get("TALKING_PAGE_TAGGER_MODEL_PATH", "").strip()
        tagger_model_path = (
            str(Path(tagger_path_raw).expanduser().resolve())
            if tagger_path_raw
            else _default_tagger_model_path()
        )
        return cls(
            bind_host,
            port,
            token,
            voice_sample_path,
            _parse_tagger_enabled(),
            _parse_tag_confidence_threshold(),
            tagger_model_path,
        )


@dataclass(frozen=True)
class CachedAudio:
    audio: bytes
    duration_ms: int
    created_at: float
    voice_fingerprint: str


@dataclass
class CachedSession:
    created_at: float
    chunks: dict


class SessionCache:
    def __init__(self, ttl_seconds=10_800):
        self.ttl_seconds = ttl_seconds
        self.sessions = {}

    def put(self, session_id, chunk_index, voice_fingerprint, audio, duration_ms, now):
        self.purge(now)
        session = self.sessions.get(session_id)
        if session is None:
            session = CachedSession(created_at=now, chunks={})
            self.sessions[session_id] = session
        session.chunks[chunk_index] = CachedAudio(audio, duration_ms, now, voice_fingerprint)

    def get(self, session_id, chunk_index, voice_fingerprint, now):
        self.purge(now)
        session = self.sessions.get(session_id)
        if session is None:
            return None
        cached = session.chunks.get(chunk_index)
        if cached is None or cached.voice_fingerprint != voice_fingerprint:
            return None
        return cached

    def clear(self, session_id):
        self.sessions.pop(session_id, None)

    def purge(self, now):
        for session_id, session in list(self.sessions.items()):
            if now - session.created_at > self.ttl_seconds:
                self.sessions.pop(session_id, None)


def count_words(text):
    return len(re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", text))


def validate_total_word_count(text):
    if count_words(text) > 10_000:
        raise ValueError("Talking Page reads up to 10,000 words at once.")


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


def wav_duration_seconds(wav_bytes):
    with wave.open(BytesIO(wav_bytes), "rb") as wav_file:
        return wav_file.getnframes() / float(wav_file.getframerate())


def validate_voice_wav(wav_bytes):
    if len(wav_bytes) > MAX_VOICE_UPLOAD_BYTES:
        raise ValueError("voice sample exceeds 10 MB limit")
    if not wav_bytes.startswith(b"RIFF"):
        raise ValueError("voice sample must be WAV audio")
    if wav_duration_seconds(wav_bytes) <= MIN_VOICE_SECONDS:
        raise ValueError(f"voice sample must be longer than {MIN_VOICE_SECONDS} seconds")


def validate_voice_file(path):
    wav_bytes = Path(path).read_bytes()
    validate_voice_wav(wav_bytes)


class VoiceStore:
    def __init__(self, env_voice_path=None):
        self.env_voice_path = env_voice_path
        self.env_fingerprint = (
            f"env:{hashlib.sha256(env_voice_path.encode()).hexdigest()[:16]}" if env_voice_path else None
        )
        self.session_samples = {}
        self._temp_paths = {}

    def set_session_voice(self, session_id, wav_bytes):
        validate_voice_wav(wav_bytes)
        fingerprint = f"upload:{hashlib.sha256(wav_bytes).hexdigest()[:16]}"
        self._remove_temp(session_id)
        self.session_samples[session_id] = (fingerprint, wav_bytes)
        return fingerprint

    def clear_session_voice(self, session_id):
        self.session_samples.pop(session_id, None)
        self._remove_temp(session_id)

    def _remove_temp(self, session_id):
        path = self._temp_paths.pop(session_id, None)
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass

    def temp_path_for(self, session_id, wav_bytes):
        existing = self._temp_paths.get(session_id)
        if existing:
            return existing
        handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        handle.write(wav_bytes)
        handle.close()
        self._temp_paths[session_id] = handle.name
        return handle.name

    def resolve(self, session_id):
        if session_id in self.session_samples:
            fingerprint, wav_bytes = self.session_samples[session_id]
            return fingerprint, ("bytes", wav_bytes, session_id)
        if EXTENSION_VOICE_SESSION_ID in self.session_samples:
            fingerprint, wav_bytes = self.session_samples[EXTENSION_VOICE_SESSION_ID]
            return fingerprint, ("bytes", wav_bytes, EXTENSION_VOICE_SESSION_ID)
        if self.env_fingerprint:
            return self.env_fingerprint, ("path", self.env_voice_path)
        return "builtin", ("builtin",)

    def status(self, session_id=None):
        default_mode = "env" if self.env_voice_path else "builtin"
        return {
            "default_mode": default_mode,
            "env_configured": self.env_voice_path is not None,
            "extension_voice": EXTENSION_VOICE_SESSION_ID in self.session_samples,
            "session_voice": session_id in self.session_samples if session_id else False,
        }


@dataclass(frozen=True)
class GeneratedAudio:
    audio: bytes
    duration_ms: int


class NanoEngine:
    def __init__(self, factory=None, voice_store=None):
        self.factory = factory or self._load_model
        self.voice_store = voice_store
        self.model = None
        self._builtin_conds = None
        self._active_fingerprint = None
        self._lock = threading.Lock()

    @staticmethod
    def _load_model(device, nano):
        from chatterbox.tts_turbo import ChatterboxTurboTTS

        return ChatterboxTurboTTS.from_pretrained(device=device, nano=nano)

    def load(self):
        if self.model is None:
            self.model = self.factory("cpu", True)
            self._builtin_conds = self.model.conds

    def warm_env_voice(self):
        if not self.voice_store or not self.voice_store.env_voice_path:
            return
        fingerprint, source = self.voice_store.resolve("__startup__")
        self._apply_voice(fingerprint, source)

    def _apply_voice(self, fingerprint, source):
        if self._active_fingerprint == fingerprint:
            return
        self.load()
        kind = source[0]
        if kind == "builtin":
            if self._builtin_conds is None:
                raise RuntimeError("builtin voice is unavailable")
            self.model.conds = self._builtin_conds
        elif kind == "path":
            self.model.prepare_conditionals(source[1])
        elif kind == "bytes":
            wav_bytes, session_key = source[1], source[2]
            prompt_path = self.voice_store.temp_path_for(session_key, wav_bytes)
            self.model.prepare_conditionals(prompt_path)
        else:
            raise RuntimeError(f"unknown voice source: {kind}")
        self._active_fingerprint = fingerprint

    def synthesize(self, text, fingerprint, source):
        self.load()
        with self._lock:
            self._apply_voice(fingerprint, source)
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
    def __init__(self, settings, engine, voice_store=None, tagger=None):
        self.settings = settings
        self.engine = engine
        self.voice_store = voice_store or VoiceStore(settings.voice_sample_path)
        self.cache = SessionCache()
        if tagger is None:
            from server.paralinguistic.tagger import ParalinguisticTagger

            tagger = ParalinguisticTagger(
                settings.tagger_model_path,
                settings.tag_confidence_threshold,
                enabled=settings.tagger_enabled,
            )
        self.tagger = tagger

    def _authorize(self, token):
        if not hmac.compare_digest(self.settings.token, token or ""):
            raise PermissionError("invalid pairing token")

    def synthesize(self, token, session_id, chunk_index, text, now=None):
        self._authorize(token)
        validate_total_word_count(text)
        fingerprint, source = self.voice_store.resolve(session_id)
        normalized = prepare_text(text)
        for_synth = self.tagger.annotate(normalized)
        validate_chunk(for_synth)
        print(f"for_synth: {for_synth}")
        generated = self.engine.synthesize(for_synth, fingerprint, source)
        self.cache.put(
            session_id,
            chunk_index,
            fingerprint,
            generated.audio,
            generated.duration_ms,
            now or time.monotonic(),
        )
        return generated

    def cached(self, token, session_id, chunk_index, now=None):
        self._authorize(token)
        fingerprint, _ = self.voice_store.resolve(session_id)
        return self.cache.get(session_id, chunk_index, fingerprint, now or time.monotonic())

    def clear(self, token, session_id):
        self._authorize(token)
        self.cache.clear(session_id)
        self.voice_store.clear_session_voice(session_id)

    def set_session_voice(self, token, session_id, wav_bytes):
        self._authorize(token)
        self.voice_store.set_session_voice(session_id, wav_bytes)
        self.cache.clear(session_id)

    def clear_session_voice(self, token, session_id):
        self._authorize(token)
        self.voice_store.clear_session_voice(session_id)
        self.cache.clear(session_id)

    def voice_status(self, token, session_id=None):
        self._authorize(token)
        return self.voice_store.status(session_id)


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

        def session_voice_path(self):
            parts = self.path.strip("/").split("/")
            if len(parts) != 4 or parts[0:2] != ["v1", "sessions"] or parts[3] != "voice":
                return None
            return parts[2]

        def do_GET(self):
            if self.path == "/v1/health":
                self.send_bytes(200, "application/json", b'{"status":"ready"}')
                return
            if self.path.startswith("/v1/voice"):
                session_id = None
                if "?" in self.path:
                    query = self.path.split("?", 1)[1]
                    for part in query.split("&"):
                        if part.startswith("session_id="):
                            session_id = part.split("=", 1)[1]
                try:
                    payload = service.voice_status(self.headers.get("X-Talking-Page-Token"), session_id)
                except PermissionError:
                    self.send_error(401)
                    return
                self.send_bytes(200, "application/json", json.dumps(payload).encode())
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

        def do_PUT(self):
            session_id = self.session_voice_path()
            if not session_id:
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                wav_bytes = self.rfile.read(length)
                service.set_session_voice(self.headers.get("X-Talking-Page-Token"), session_id, wav_bytes)
            except PermissionError:
                self.send_error(401)
                return
            except ValueError:
                self.send_error(422)
                return
            self.send_response(204)
            self.end_headers()

        def do_DELETE(self):
            session_id = self.session_voice_path()
            if session_id:
                try:
                    service.clear_session_voice(self.headers.get("X-Talking-Page-Token"), session_id)
                except PermissionError:
                    self.send_error(401)
                    return
                self.send_response(204)
                self.end_headers()
                return
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
    _ensure_project_root_on_path()
    load_project_env()
    settings = Settings.from_environment()
    voice_store = VoiceStore(settings.voice_sample_path)
    if settings.voice_sample_path:
        validate_voice_file(settings.voice_sample_path)
    engine = NanoEngine(voice_store=voice_store)
    engine.load()
    engine.warm_env_voice()
    service = Service(settings, engine, voice_store)
    ThreadingHTTPServer((settings.host, settings.port), make_handler(service)).serve_forever()


if __name__ == "__main__":
    run()
