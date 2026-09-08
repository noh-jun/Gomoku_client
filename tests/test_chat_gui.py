from pathlib import Path
import tempfile
import tkinter as tk
import unittest

from omok_client.gui import OmokApp
from omok_client.network import NetworkEvent
from omok_client.state import IN_ROOM, LOBBY


class ChatGuiTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.root.withdraw()
        self.temp_directory = tempfile.TemporaryDirectory()
        settings_path = Path(self.temp_directory.name) / "client_settings.json"
        self.app = OmokApp(self.root, settings_path=settings_path)
        self.root.update_idletasks()

    def tearDown(self) -> None:
        if hasattr(self, "app"):
            self.app._on_close()
        if hasattr(self, "temp_directory"):
            self.temp_directory.cleanup()

    def enter_room(self) -> None:
        self.app.network.request_room_list = lambda: None
        self.app._handle_network_event(NetworkEvent("connected", message="Connected."))
        self.app._handle_network_event(NetworkEvent("message", payload={"type": "connected"}))
        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={
                    "type": "joined",
                    "room_id": "room_001",
                    "room_name": "친선 대국",
                    "your_role": "OBSERVER",
                    "your_color": None,
                    "board_size": 15,
                    "win_length": 5,
                },
            )
        )
        self.assertEqual(self.app.state.view_state, IN_ROOM)

    def chat(self, nickname: str, text: str, sent_at_unix_ms: int) -> None:
        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={
                    "type": "chat_message",
                    "nickname": nickname,
                    "text": text,
                    "sent_at_unix_ms": sent_at_unix_ms,
                },
            )
        )

    def test_composer_is_disabled_outside_a_room_and_enabled_inside(self) -> None:
        self.assertEqual(str(self.app.chat_panel.entry["state"]), "disabled")
        self.enter_room()
        self.assertEqual(str(self.app.chat_panel.entry["state"]), "normal")
        self.assertEqual(str(self.app.chat_panel.send_button["state"]), "normal")

    def test_server_echo_renders_and_room_exit_clears(self) -> None:
        self.enter_room()
        self.chat("관전자A", "심심하다", 1_725_760_000_000)
        self.chat("관전자B", "나도", 1_725_760_005_000)
        self.assertEqual(self.app.chat_panel.message_count(), 2)
        log = self.app.chat_panel.log.get("1.0", "end")
        self.assertIn("관전자A: 심심하다", log)
        self.assertIn("관전자B: 나도", log)
        self.assertNotIn("심심하다", self.app.message_var.get())

        self.app._handle_network_event(
            NetworkEvent("message", payload={"type": "left_room", "room_id": "room_001"})
        )
        self.assertEqual(self.app.state.view_state, LOBBY)
        self.assertEqual(self.app.chat_panel.message_count(), 0)
        self.assertEqual(self.app.chat_panel.log.get("1.0", "end").strip(), "")
        self.assertEqual(str(self.app.chat_panel.entry["state"]), "disabled")

    def test_submit_sends_normalized_text_and_only_clears_on_success(self) -> None:
        self.enter_room()
        sent: list[str] = []
        self.app.network.send_chat = lambda text: sent.append(text)  # type: ignore[method-assign]

        self.app.chat_panel.entry_var.set("   한 수 부탁합니다  ")
        self.app.chat_panel._submit()
        self.assertEqual(sent, ["한 수 부탁합니다"])
        self.assertEqual(self.app.chat_panel.entry_var.get(), "")
        self.assertEqual(self.app.chat_panel.message_count(), 0)

        self.app.chat_panel.entry_var.set("   ")
        self.app.chat_panel._submit()
        self.assertEqual(sent, ["한 수 부탁합니다"])
        self.assertEqual(self.app.chat_panel.entry_var.get(), "   ")
        self.assertIn("1~200자", self.app.message_var.get())

    def test_chat_message_outside_room_is_rejected_without_crashing(self) -> None:
        self.app.network.request_room_list = lambda: None
        self.app._handle_network_event(NetworkEvent("connected", message="Connected."))
        self.app._handle_network_event(NetworkEvent("message", payload={"type": "connected"}))
        self.chat("누군가", "방 밖 메시지", 1_725_760_000_000)
        self.assertEqual(self.app.chat_panel.message_count(), 0)
        self.assertIn("Invalid server message", self.app.message_var.get())


if __name__ == "__main__":
    unittest.main()
