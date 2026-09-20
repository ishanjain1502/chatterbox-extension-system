import unittest

from server.talking_page_server import NanoEngine


class FakeModel:
    sr = 24_000

    def generate(self, text):
        return [[0.0, 0.25, -0.25]]


class EngineTest(unittest.TestCase):
    def test_loads_nano_once_on_cpu(self):
        calls = []

        def factory(device, nano):
            calls.append((device, nano))
            return FakeModel()

        engine = NanoEngine(factory)
        engine.load()
        engine.load()

        self.assertEqual([("cpu", True)], calls)

    def test_serializes_generated_audio_as_wav(self):
        engine = NanoEngine(lambda device, nano: FakeModel())
        engine.load()

        generated = engine.synthesize("A short sentence.")

        self.assertTrue(generated.audio.startswith(b"RIFF"))
        self.assertGreater(generated.duration_ms, 0)
