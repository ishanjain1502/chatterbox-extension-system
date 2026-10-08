import unittest

from server.paralinguistic.tags import NUM_CLASSES, PARALINGUISTIC_TAGS, TAG_TO_INDEX
from server.paralinguistic.tokens import tokenize_words


class TokenizeWordsTest(unittest.TestCase):
    def test_tokenize_words_matches_apostrophe_words(self):
        words = tokenize_words("It's a 2nd test.")
        self.assertEqual(["It's", "a", "2nd", "test"], words)

    def test_tag_inventory_has_nine_tags_plus_none_in_model(self):
        self.assertEqual(9, len(PARALINGUISTIC_TAGS))
        self.assertIn("[chuckle]", TAG_TO_INDEX)
        self.assertEqual(NUM_CLASSES, 10)


if __name__ == "__main__":
    unittest.main()
