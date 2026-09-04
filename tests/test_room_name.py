import unittest

from omok_client.room_name import normalize_room_name


class RoomNameTests(unittest.TestCase):
    def test_normalizes_unicode_and_outer_whitespace(self) -> None:
        self.assertEqual(normalize_room_name("  Ｇａｍｅ 방  "), "Game 방")

    def test_rejects_empty_long_and_control_characters(self) -> None:
        for value in ("   ", "가" * 31, "first\nsecond", "bad\x00name"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_room_name(value)


if __name__ == "__main__":
    unittest.main()
