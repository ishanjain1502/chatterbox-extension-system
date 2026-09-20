import unittest

from server.talking_page_server import GeneratedAudio, Service, Settings


class FakeEngine:
    def synthesize(self, text):
        return GeneratedAudio(b"wav", 1200)


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = Service(Settings("127.0.0.1", 8765, "a" * 32), FakeEngine())

    def test_rejects_synthesis_without_the_pairing_token(self):
        with self.assertRaises(PermissionError):
            self.service.synthesize("wrong", "12-example.com", 0, "Hello.", now=100)

    def test_synthesis_is_cached_for_the_active_session(self):
        result = self.service.synthesize("a" * 32, "12-example.com", 0, "Hello.", now=100)

        self.assertEqual(b"wav", result.audio)
        self.assertEqual(b"wav", self.service.cached("a" * 32, "12-example.com", 0, now=101).audio)

    def test_clear_removes_cached_session_audio(self):
        self.service.synthesize("a" * 32, "12-example.com", 0, "Hello.", now=100)
        self.service.clear("a" * 32, "12-example.com")

        self.assertIsNone(self.service.cached("a" * 32, "12-example.com", 0, now=100))
