import os
import unittest
from unittest.mock import patch

from server.talking_page_server import Settings


class SettingsTest(unittest.TestCase):
    def test_defaults_to_loopback_when_token_is_valid(self):
        with patch.dict(os.environ, {"TALKING_PAGE_TOKEN": "a" * 32}, clear=True):
            settings = Settings.from_environment()

        self.assertEqual("127.0.0.1", settings.host)
        self.assertEqual(8765, settings.port)

    def test_rejects_a_missing_token(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "TALKING_PAGE_TOKEN"):
                Settings.from_environment()

    def test_rejects_a_non_loopback_host(self):
        with patch.dict(
            os.environ,
            {"TALKING_PAGE_TOKEN": "a" * 32, "TALKING_PAGE_HOST": "0.0.0.0"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "loopback"):
                Settings.from_environment()
