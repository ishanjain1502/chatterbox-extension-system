import unittest

import torch

from server.paralinguistic.model import GapTaggerModel
from server.paralinguistic.tags import NUM_CLASSES


class GapTaggerModelTest(unittest.TestCase):
    def test_output_shape_has_one_more_gap_than_words(self):
        model = GapTaggerModel(vocab_size=50)
        x = torch.tensor([[1, 2, 3, 4]])
        logits = model(x)
        self.assertEqual((1, 5, NUM_CLASSES), tuple(logits.shape))


if __name__ == "__main__":
    unittest.main()
