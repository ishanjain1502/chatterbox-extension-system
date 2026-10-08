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
            {"TALKING_PAGE_TOKEN": "a" * 32, "TALKING_PAGE_HOST": "192.168.0.1"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "TALKING_PAGE_HOST"):
                Settings.from_environment()

    def test_allows_container_bind_host(self):
        with patch.dict(
            os.environ,
            {"TALKING_PAGE_TOKEN": "a" * 32, "TALKING_PAGE_HOST": "0.0.0.0"},
            clear=True,
        ):
            settings = Settings.from_environment()

        self.assertEqual("0.0.0.0", settings.host)

    def test_tagger_threshold_must_be_between_zero_and_one(self):
        with patch.dict(
            os.environ,
            {
                "TALKING_PAGE_TOKEN": "a" * 32,
                "TALKING_PAGE_TAG_CONFIDENCE_THRESHOLD": "1.5",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "TALKING_PAGE_TAG_CONFIDENCE_THRESHOLD"):
                Settings.from_environment()

    def test_tagger_defaults(self):
        with patch.dict(os.environ, {"TALKING_PAGE_TOKEN": "a" * 32}, clear=True):
            settings = Settings.from_environment()
        self.assertTrue(settings.tagger_enabled)
        self.assertAlmostEqual(0.65, settings.tag_confidence_threshold)
