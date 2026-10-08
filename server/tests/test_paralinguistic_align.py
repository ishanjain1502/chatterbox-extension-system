import unittest

from server.paralinguistic.align import align_pair, build_tagged_string
from server.paralinguistic.tags import TAG_TO_INDEX
from server.paralinguistic.tokens import tokenize_words


class AlignPairTest(unittest.TestCase):
    def test_aligns_mid_sentence_chuckle(self):
        plain = "Oh that is hilarious anyway we have a model."
        tagged = "Oh that is hilarious! [chuckle] anyway we have a model."
        labels = align_pair(plain, tagged)
        self.assertIsNotNone(labels)
        words = tokenize_words(plain)
        self.assertEqual(len(words) + 1, len(labels))
        anyway_index = words.index("anyway")
        self.assertEqual(TAG_TO_INDEX["[chuckle]"], labels[anyway_index])

    def test_build_tagged_string_round_trip(self):
        plain = "Hello world"
        tagged = "Hello [sigh] world"
        labels = align_pair(plain, tagged)
        self.assertIsNotNone(labels)
        rebuilt = build_tagged_string(tokenize_words(plain), labels)
        self.assertEqual(tagged, rebuilt)

    def test_returns_none_when_words_differ(self):
        self.assertIsNone(align_pair("Hello", "Hello [chuckle] there"))


if __name__ == "__main__":
    unittest.main()
