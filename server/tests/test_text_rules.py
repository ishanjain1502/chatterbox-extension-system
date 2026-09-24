import unittest

from server.talking_page_server import count_words, prepare_text, validate_chunk, validate_total_word_count


class TextRulesTest(unittest.TestCase):
    def test_counts_words_without_counting_punctuation(self):
        self.assertEqual(5, count_words("Hello, world! This is three."))

    def test_normalizes_whitespace_without_rewriting_words(self):
        self.assertEqual("A heading. With space.", prepare_text("A heading\n\nWith   space."))

    def test_rejects_a_chunk_over_the_model_limit(self):
        with self.assertRaisesRegex(ValueError, "2,000"):
            validate_chunk("a" * 2001)

    def test_rejects_text_over_10000_words(self):
        with self.assertRaisesRegex(ValueError, "10,000"):
            validate_total_word_count("word " * 10_001)
