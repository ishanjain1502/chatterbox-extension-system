import tempfile
import unittest
from pathlib import Path

from server.paralinguistic.train import train_model


class TrainModelTest(unittest.TestCase):
    def test_train_model_writes_checkpoint(self):
        fixture = Path(__file__).resolve().parents[1] / "data" / "paralinguistic_pairs.fixture.jsonl"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "tagger.pt"
            train_model(data_path=fixture, output_path=out, epochs=5)
            self.assertTrue(out.is_file())


if __name__ == "__main__":
    unittest.main()
