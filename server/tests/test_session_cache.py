import unittest

from server.talking_page_server import SessionCache


class SessionCacheTest(unittest.TestCase):
    def test_returns_active_session_audio(self):
        cache = SessionCache(ttl_seconds=10)
        cache.put("12-example.com", 0, b"wav", 1200, now=100)

        self.assertEqual(b"wav", cache.get("12-example.com", 0, now=105).audio)

    def test_expired_session_audio_is_unavailable(self):
        cache = SessionCache(ttl_seconds=10)
        cache.put("12-example.com", 0, b"wav", 1200, now=100)

        self.assertIsNone(cache.get("12-example.com", 0, now=111))

    def test_clear_removes_all_chunks_from_one_session(self):
        cache = SessionCache(ttl_seconds=10)
        cache.put("12-example.com", 0, b"one", 100, now=100)
        cache.put("12-example.com", 1, b"two", 100, now=100)

        cache.clear("12-example.com")

        self.assertIsNone(cache.get("12-example.com", 0, now=100))
        self.assertIsNone(cache.get("12-example.com", 1, now=100))
