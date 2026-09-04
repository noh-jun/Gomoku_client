import json
from pathlib import Path
import tempfile
import unittest

from omok_client.client_settings import (
    ClientSettings,
    DEFAULT_SERVER_URL,
    load_client_settings,
    normalize_server_url,
    save_client_settings,
)


class ClientSettingsTests(unittest.TestCase):
    def test_save_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "client_settings.json"
            save_client_settings(ClientSettings("wss://example.com:8443"), path)
            self.assertEqual(
                load_client_settings(path), ClientSettings("wss://example.com:8443")
            )
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8"))["server_url"],
                "wss://example.com:8443",
            )

    def test_missing_or_invalid_file_uses_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "client_settings.json"
            self.assertEqual(load_client_settings(path).server_url, DEFAULT_SERVER_URL)
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(load_client_settings(path).server_url, DEFAULT_SERVER_URL)

    def test_server_url_accepts_base_websocket_address_only(self) -> None:
        self.assertEqual(
            normalize_server_url("  ws://192.168.1.75:8000/  "),
            "ws://192.168.1.75:8000",
        )
        for value in (
            "http://example.com",
            "ws://example.com/ws",
            "ws://example.com?token=secret",
            "ws://example.com:not-a-port",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_server_url(value)


if __name__ == "__main__":
    unittest.main()
