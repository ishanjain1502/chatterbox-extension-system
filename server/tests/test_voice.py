import struct
import tempfile
import unittest
import wave
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from server.talking_page_server import (
    EXTENSION_VOICE_SESSION_ID,
    Service,
    Settings,
    VoiceStore,
    validate_voice_wav,
)


def make_wav_bytes(duration_seconds=5.1, sample_rate=24_000):
    frame_count = int(duration_seconds * sample_rate)
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        silent_frame = struct.pack("<h", 0)
        wav_file.writeframes(silent_frame * frame_count)
    return buffer.getvalue()


class VoiceValidationTest(unittest.TestCase):
    def test_rejects_short_voice_samples(self):
        with self.assertRaisesRegex(ValueError, "longer than"):
            validate_voice_wav(make_wav_bytes(4.0))

    def test_accepts_samples_longer_than_five_seconds(self):
        validate_voice_wav(make_wav_bytes(5.1))


class VoiceStoreTest(unittest.TestCase):
    def test_extension_voice_overrides_env_for_new_sessions(self):
        store = VoiceStore(env_voice_path="C:\\voices\\env.wav")
        store.set_session_voice(EXTENSION_VOICE_SESSION_ID, make_wav_bytes())

        fingerprint, source = store.resolve("12-example.com")

        self.assertTrue(fingerprint.startswith("upload:"))
        self.assertEqual("bytes", source[0])

    def test_session_voice_overrides_extension_default(self):
        store = VoiceStore()
        store.set_session_voice(EXTENSION_VOICE_SESSION_ID, make_wav_bytes())
        session_wav = make_wav_bytes(5.2)
        store.set_session_voice("12-example.com", session_wav)

        fingerprint, source = store.resolve("12-example.com")

        self.assertEqual(session_wav, source[1])


class FakeEngine:
    def __init__(self):
        self.calls = []

    def synthesize(self, text, fingerprint, source):
        self.calls.append((fingerprint, source))
        from server.talking_page_server import GeneratedAudio

        return GeneratedAudio(b"wav", 100)


class ServiceVoiceTest(unittest.TestCase):
    def test_set_session_voice_clears_cached_chunks(self):
        engine = FakeEngine()
        service = Service(Settings("127.0.0.1", 8765, "a" * 32, None), engine)
        token = "a" * 32
        service.synthesize(token, "12-example.com", 0, "Hello.", now=100)
        service.set_session_voice(token, EXTENSION_VOICE_SESSION_ID, make_wav_bytes())

        self.assertIsNone(service.cached(token, "12-example.com", 0, now=101))


class SettingsVoiceTest(unittest.TestCase):
    def test_rejects_missing_env_voice_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "missing.wav")
            with patch.dict(
                "os.environ",
                {"TALKING_PAGE_TOKEN": "a" * 32, "TALKING_PAGE_VOICE_SAMPLE": missing},
                clear=True,
            ):
                with self.assertRaisesRegex(ValueError, "not found"):
                    Settings.from_environment()
