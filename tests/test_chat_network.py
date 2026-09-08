import json
import unittest

from omok_client.network import NetworkClient


class ChatNetworkTests(unittest.TestCase):
    def make_client(self) -> tuple[NetworkClient, list[dict[str, object]]]:
        client = object.__new__(NetworkClient)
        sent: list[dict[str, object]] = []
        client._submit_send = lambda raw: sent.append(json.loads(raw))  # type: ignore[method-assign]
        return client, sent

    def test_chat_matches_server_contract(self) -> None:
        client, sent = self.make_client()
        client.send_chat("  안녕하세요  ")
        self.assertEqual(sent, [{"type": "chat", "text": "안녕하세요"}])

    def test_chat_rejects_invalid_text_before_sending(self) -> None:
        client, sent = self.make_client()
        for value in ("", "   ", "줄\n바꿈", "x" * 201):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    client.send_chat(value)
        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()
