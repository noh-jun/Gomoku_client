import unittest

from omok_client.chat import MAX_CHAT_TEXT_LENGTH, normalize_chat_text


class ChatTextTests(unittest.TestCase):
    def test_strips_surrounding_whitespace(self) -> None:
        self.assertEqual(normalize_chat_text("  안녕하세요  "), "안녕하세요")

    def test_keeps_inner_spacing_and_full_width_characters(self) -> None:
        self.assertEqual(normalize_chat_text("한 수  더！"), "한 수  더！")

    def test_rejects_empty_and_whitespace_only(self) -> None:
        for value in ("", "   ", None, 42):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_chat_text(value)

    def test_rejects_over_length(self) -> None:
        self.assertEqual(
            len(normalize_chat_text("가" * MAX_CHAT_TEXT_LENGTH)), MAX_CHAT_TEXT_LENGTH
        )
        with self.assertRaises(ValueError):
            normalize_chat_text("가" * (MAX_CHAT_TEXT_LENGTH + 1))

    def test_rejects_control_and_line_separator_characters(self) -> None:
        for value in ("첫줄\n둘째줄", "탭\t포함", "줄 구분", "\x07벨"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_chat_text(value)


if __name__ == "__main__":
    unittest.main()
