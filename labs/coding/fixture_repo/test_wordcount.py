import unittest

from wordcount import count_words


class CountWordsTests(unittest.TestCase):
    def test_counts_single_spaced_words(self) -> None:
        self.assertEqual(count_words("one two three"), 3)

    def test_ignores_repeated_and_mixed_whitespace(self) -> None:
        self.assertEqual(count_words("  one   two\tthree\n"), 3)

    def test_counts_no_words_in_blank_text(self) -> None:
        self.assertEqual(count_words("   "), 0)


if __name__ == "__main__":
    unittest.main()
