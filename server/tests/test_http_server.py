import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

from server.talking_page_server import EXTENSION_VOICE_SESSION_ID, GeneratedAudio, Service, Settings, make_handler
from server.tests.test_voice import make_wav_bytes


class FakeEngine:
    def synthesize(self, text, fingerprint, source):
        return GeneratedAudio(b"RIFFfake", 1200)


class HttpServerTest(unittest.TestCase):
    def setUp(self):
        service = Service(Settings("127.0.0.1", 8765, "a" * 32, None), FakeEngine())
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_health_returns_ready_json_without_a_token(self):
        with urlopen(f"{self.base_url}/v1/health") as response:
            self.assertEqual(200, response.status)
            self.assertEqual({"status": "ready"}, json.load(response))

    def test_synthesis_returns_wav_and_caches_it(self):
        request = Request(
            f"{self.base_url}/v1/sessions/12-example.com/chunks/0",
            data=json.dumps({"text": "Hello."}).encode(),
            headers={"Content-Type": "application/json", "X-Talking-Page-Token": "a" * 32},
            method="POST",
        )
        with urlopen(request) as response:
            self.assertEqual("audio/wav", response.headers["Content-Type"])
            self.assertEqual(b"RIFFfake", response.read())

        cached = Request(
            f"{self.base_url}/v1/sessions/12-example.com/chunks/0",
            headers={"X-Talking-Page-Token": "a" * 32},
        )
        with urlopen(cached) as response:
            self.assertEqual(b"RIFFfake", response.read())

    def test_voice_upload_and_status(self):
        upload = Request(
            f"{self.base_url}/v1/sessions/{EXTENSION_VOICE_SESSION_ID}/voice",
            data=make_wav_bytes(),
            headers={
                "Content-Type": "audio/wav",
                "X-Talking-Page-Token": "a" * 32,
            },
            method="PUT",
        )
        with urlopen(upload) as response:
            self.assertEqual(204, response.status)

        status = Request(
            f"{self.base_url}/v1/voice",
            headers={"X-Talking-Page-Token": "a" * 32},
        )
        with urlopen(status) as response:
            payload = json.load(response)
            self.assertTrue(payload["extension_voice"])
