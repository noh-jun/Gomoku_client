import unittest

from omok_client.state import (
    AppState,
    ChatMessage,
    IN_ROOM,
    MAX_CHAT_HISTORY,
)


def chat_payload(nickname: str = "관전자A", text: str = "안녕", sent_at: int = 1_725_760_000_000) -> dict:
    return {
        "type": "chat_message",
        "nickname": nickname,
        "text": text,
        "sent_at_unix_ms": sent_at,
    }


class ChatStateTests(unittest.TestCase):
    def room_state(self) -> AppState:
        state = AppState()
        state.apply_server_message({"type": "connected"})
        state.apply_server_message(
            {
                "type": "joined",
                "room_id": "room_001",
                "room_name": "친선 대국",
                "your_role": "OBSERVER",
                "your_color": None,
                "board_size": 15,
                "win_length": 5,
            }
        )
        self.assertEqual(state.view_state, IN_ROOM)
        return state

    def test_chat_message_appends_in_order_and_reports_line(self) -> None:
        state = self.room_state()
        change = state.apply_server_message(chat_payload("관전자A", "  심심하다  ", 1))
        self.assertTrue(change.handled)
        self.assertFalse(change.redraw_board)
        self.assertEqual(change.message, "관전자A: 심심하다")
        state.apply_server_message(chat_payload("관전자B", "나도", 2))
        self.assertEqual(
            state.chat_messages,
            [ChatMessage("관전자A", "심심하다", 1), ChatMessage("관전자B", "나도", 2)],
        )

    def test_history_is_capped_to_most_recent_messages(self) -> None:
        state = self.room_state()
        for index in range(MAX_CHAT_HISTORY + 5):
            state.apply_server_message(chat_payload("N", f"m{index}", index))
        self.assertEqual(len(state.chat_messages), MAX_CHAT_HISTORY)
        self.assertEqual(state.chat_messages[0].text, "m5")
        self.assertEqual(state.chat_messages[-1].text, f"m{MAX_CHAT_HISTORY + 4}")

    def test_rejected_outside_room_and_state_is_untouched(self) -> None:
        state = AppState()
        state.apply_server_message({"type": "connected"})
        self.assertNotEqual(state.view_state, IN_ROOM)
        with self.assertRaises(ValueError):
            state.apply_server_message(chat_payload())
        self.assertEqual(state.chat_messages, [])

    def test_invalid_fields_are_rejected_atomically(self) -> None:
        state = self.room_state()
        state.apply_server_message(chat_payload("관전자A", "첫 메시지", 1))
        bad_payloads = [
            {**chat_payload(), "text": ""},
            {**chat_payload(), "text": "x" * 201},
            {**chat_payload(), "text": "줄\n바꿈"},
            {**chat_payload(), "nickname": ""},
            {**chat_payload(), "nickname": "n" * 21},
            {**chat_payload(), "sent_at_unix_ms": -1},
            {**chat_payload(), "sent_at_unix_ms": "1725760000000"},
            {**chat_payload(), "sent_at_unix_ms": True},
            {k: v for k, v in chat_payload().items() if k != "sent_at_unix_ms"},
        ]
        for payload in bad_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    state.apply_server_message(payload)
        self.assertEqual(state.chat_messages, [ChatMessage("관전자A", "첫 메시지", 1)])

    def test_leaving_or_rejoining_clears_history(self) -> None:
        state = self.room_state()
        state.apply_server_message(chat_payload())
        state.apply_server_message({"type": "left_room", "room_id": "room_001"})
        self.assertEqual(state.chat_messages, [])

        state = self.room_state()
        state.apply_server_message(chat_payload())
        state.apply_server_message(
            {
                "type": "joined",
                "room_id": "room_002",
                "room_name": "다른 방",
                "your_role": "OBSERVER",
                "your_color": None,
                "board_size": 15,
                "win_length": 5,
            }
        )
        self.assertEqual(state.chat_messages, [])

        state = self.room_state()
        state.apply_server_message(chat_payload())
        state.reset_connection()
        self.assertEqual(state.chat_messages, [])

    def test_chat_error_codes_are_localized(self) -> None:
        state = self.room_state()
        for code, expected in (
            ("CHAT_NOT_AVAILABLE", "방에 입장한 뒤에"),
            ("CHAT_TEXT_INVALID", "1~200자"),
            ("CHAT_RATE_LIMITED", "너무 빨리"),
        ):
            with self.subTest(code=code):
                change = state.apply_server_message({"type": "error", "code": code, "message": "x"})
                self.assertIn(expected, change.message)


if __name__ == "__main__":
    unittest.main()
