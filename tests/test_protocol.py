import unittest

from omok_client.protocol import ClientProtocolError, decode_server_message, encode_message


class ProtocolTests(unittest.TestCase):
    def test_round_trip_message(self) -> None:
        raw = encode_message("move", x=4, y=5)
        self.assertEqual(decode_server_message(raw), {"type": "move", "x": 4, "y": 5})

    def test_invalid_json_or_shape(self) -> None:
        with self.assertRaises(ClientProtocolError):
            decode_server_message("not json")
        with self.assertRaises(ClientProtocolError):
            decode_server_message("[]")


if __name__ == "__main__":
    unittest.main()
