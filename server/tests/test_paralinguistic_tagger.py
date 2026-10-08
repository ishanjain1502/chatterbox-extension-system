import tempfile
import unittest
from pathlib import Path

import torch

from server.paralinguistic.model import GapTaggerModel
from server.paralinguistic.tags import TAG_TO_INDEX
from server.paralinguistic.tagger import ParalinguisticTagger


class ParalinguisticTaggerTest(unittest.TestCase):
    def _write_tiny_checkpoint(self, path: Path):
        vocab = {"<unk>": 0, "hello": 1, "world": 2}
        model = GapTaggerModel(vocab_size=len(vocab))
        with torch.no_grad():
            model.gap_head.bias.zero_()
            model.gap_head.bias[TAG_TO_INDEX["[sigh]"]] = 10.0
        torch.save({"vocab": vocab, "model_state": model.state_dict()}, path)

    def test_high_threshold_skips_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "tagger.pt"
            self._write_tiny_checkpoint(ckpt)
            tagger = ParalinguisticTagger(ckpt, confidence_threshold=1.0, enabled=True)
            self.assertEqual("Hello world", tagger.annotate("Hello world"))

    def test_low_threshold_inserts_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "tagger.pt"
            self._write_tiny_checkpoint(ckpt)
            tagger = ParalinguisticTagger(ckpt, confidence_threshold=0.01, enabled=True)
            out = tagger.annotate("Hello world")
            self.assertIn("[sigh]", out)

    def test_missing_model_passes_plain_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            tagger = ParalinguisticTagger(Path(tmp) / "missing.pt", confidence_threshold=0.5, enabled=True)
            self.assertEqual("Hello world", tagger.annotate("Hello world"))


if __name__ == "__main__":
    unittest.main()
