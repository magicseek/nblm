import json
import os
import socket
import threading
import time
import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

from scripts import agent_browser_client as abc
from scripts.agent_browser_client import AgentBrowserClient


class SocketPairDaemon(threading.Thread):
    def __init__(self, server_socket: socket.socket):
        super().__init__(daemon=True)
        self.server_socket = server_socket
        self.received_close = threading.Event()

    def run(self):
        try:
            self.server_socket.settimeout(1)
            data = b""
            while b"\n" not in data:
                chunk = self.server_socket.recv(4096)
                if not chunk:
                    return
                data += chunk

            message = json.loads(data.decode().strip())
            if message.get("action") == "close":
                self.received_close.set()
            response = {
                "id": message.get("id", "1"),
                "success": True,
                "data": {}
            }
            self.server_socket.sendall((json.dumps(response) + "\n").encode())
        finally:
            self.server_socket.close()


class AgentBrowserClientShutdownTests(unittest.TestCase):
    def setUp(self):
        self.socket_dir = Path(tempfile.gettempdir())
        self.old_socket_dir = abc.AGENT_BROWSER_SOCKET_DIR
        abc.AGENT_BROWSER_SOCKET_DIR = self.socket_dir

    def tearDown(self):
        abc.AGENT_BROWSER_SOCKET_DIR = self.old_socket_dir
        # No temporary directory to clean up; socket cleanup handled per test.
        pass

    def test_shutdown_sends_close_and_removes_socket(self):
        session_id = f"shutdown-{os.getpid()}"
        client_socket, server_socket = socket.socketpair()
        daemon = SocketPairDaemon(server_socket)
        daemon.start()

        client = AgentBrowserClient(session_id=session_id)
        dummy_socket_path = self.socket_dir / f"agent-browser-{session_id}.sock"
        dummy_socket_path.touch()

        with mock.patch.object(client, "_daemon_is_running", return_value=True), \
            mock.patch.object(client, "_connect_socket", return_value=client_socket), \
            mock.patch.object(client, "_await_socket_gone", return_value=True):
            result = client.shutdown(timeout=2)

        self.assertTrue(result)
        self.assertTrue(daemon.received_close.is_set())
        daemon.join(timeout=1)
        self.assertFalse(daemon.is_alive())

        if dummy_socket_path.exists():
            dummy_socket_path.unlink()

    def test_shutdown_when_no_daemon_returns_false(self):
        session_id = f"missing-{os.getpid()}"
        client = AgentBrowserClient(session_id=session_id)
        with mock.patch.object(client, "_daemon_is_running", return_value=False):
            self.assertFalse(client.shutdown(timeout=0.1))


class AgentBrowserClientAuthTests(unittest.TestCase):
    def test_check_auth_detects_login_fields(self):
        snapshot = 'textbox "Email or phone" [ref=e1]'
        client = AgentBrowserClient(session_id="test")
        self.assertTrue(client.check_auth(snapshot))

    def test_check_auth_ignores_login_in_content(self):
        snapshot = 'text: "keeps cookies and login state"'
        client = AgentBrowserClient(session_id="test")
        self.assertFalse(client.check_auth(snapshot))


class AgentBrowserClientEvaluateTests(unittest.TestCase):
    def test_evaluate_sends_script(self):
        client = AgentBrowserClient(session_id="test")
        with mock.patch.object(client, "_send_command", return_value={"result": "value"}) as send:
            result = client.evaluate("return 1")
        self.assertEqual(result, "value")
        send.assert_called_once_with("evaluate", {"script": "return 1"})

    def test_get_cookies_uses_urls(self):
        client = AgentBrowserClient(session_id="test")
        with mock.patch.object(client, "_send_command", return_value={"cookies": [{"name": "SID"}]}) as send:
            cookies = client.get_cookies("https://notebooklm.google.com")
        self.assertEqual(cookies, [{"name": "SID"}])
        send.assert_called_once_with("cookies_get", {"urls": ["https://notebooklm.google.com"]})


if __name__ == "__main__":
    unittest.main()
