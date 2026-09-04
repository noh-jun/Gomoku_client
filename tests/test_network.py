import json
import unittest

from omok_client.network import NetworkClient, build_websocket_uri


class NetworkLobbyCommandTests(unittest.TestCase):
    def test_server_uri_has_no_room_id(self) -> None:
        self.assertEqual(
            build_websocket_uri("ws://192.168.1.75:8000/"),
            "ws://192.168.1.75:8000/ws",
        )
        with self.assertRaises(ValueError):
            build_websocket_uri("http://192.168.1.75:8000")

    def test_lobby_commands_match_server_contract(self) -> None:
        client = object.__new__(NetworkClient)
        sent: list[dict[str, object]] = []
        client._submit_send = lambda raw: sent.append(json.loads(raw))  # type: ignore[method-assign]

        client.request_room_list()
        client.create_room("친선 대국")
        client.join_room("room_001")
        client.leave_room()

        self.assertEqual(
            sent,
            [
                {"type": "get_room_list"},
                {"type": "create_room", "room_name": "친선 대국"},
                {"type": "join_room", "room_id": "room_001"},
                {"type": "leave_room"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
