import json
import tempfile
import unittest
from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone
from unittest import mock

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root))

import scripts.auth_manager as auth_manager


class DummyClient:
    def __init__(self):
        self.navigated = []
        self.evaluated = []
        self.restored = False

    def navigate(self, url: str, wait_until=None):
        self.navigated.append(url)

    def wait_for(self, timeout: int = 30):
        return True

    def evaluate(self, script: str):
        self.evaluated.append(script)
        return "token-xyz"

    def get_cookies(self, urls=None):
        return [
            {"name": "SID", "value": "abc"},
            {"name": "HSID", "value": "def"},
        ]

    def set_storage_state(self, state):
        self.restored = True
        return True


class DummyClientNoToken:
    def __init__(self):
        self.evaluated = []

    def evaluate(self, script: str):
        self.evaluated.append(script)
        return None

    def get_cookies(self, urls=None):
        return []


class FakeResponse:
    def __init__(self, body: str, url: str = "https://notebooklm.google.com/"):
        self._body = body.encode("utf-8")
        self._url = url
        self.status = 200

    def read(self):
        return self._body

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class NotebookLMCredentialsTests(unittest.TestCase):
    def test_get_notebooklm_credentials_uses_env_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            auth_dir = data_dir / "auth"
            auth_dir.mkdir(parents=True, exist_ok=True)
            google_file = auth_dir / "google.json"
            google_file.write_text(json.dumps({"cookies": [], "origins": []}))

            services = {
                "google": {
                    "file": google_file,
                    "login_url": "https://notebooklm.google.com",
                    "success_indicators": ["notebooklm"],
                }
            }

            with mock.patch.object(auth_manager, "DATA_DIR", data_dir), \
                mock.patch.object(auth_manager, "AUTH_DIR", auth_dir), \
                mock.patch.object(auth_manager.AuthManager, "SERVICES", services), \
                mock.patch.object(auth_manager.AuthManager, "setup", return_value=False), \
                mock.patch.dict(
                    auth_manager.os.environ,
                    {"NOTEBOOKLM_AUTH_TOKEN": "env-token", "NOTEBOOKLM_COOKIES": "SID=env"},
                    clear=False,
                ):
                auth = auth_manager.AuthManager()
                result = auth.get_notebooklm_credentials(client=DummyClientNoToken())

            self.assertEqual(result["auth_token"], "env-token")
            self.assertEqual(result["cookies"], "SID=env")

            saved = json.loads(google_file.read_text())
            self.assertEqual(saved["notebooklm_auth_token"], "env-token")
            self.assertEqual(saved["notebooklm_cookies"], "SID=env")

    def test_get_notebooklm_credentials_uses_cached_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            auth_dir = data_dir / "auth"
            auth_dir.mkdir(parents=True, exist_ok=True)
            google_file = auth_dir / "google.json"
            google_file.write_text(
                json.dumps(
                    {
                        "notebooklm_auth_token": "cached-token",
                        "notebooklm_cookies": "SID=abc",
                    }
                )
            )

            services = {
                "google": {
                    "file": google_file,
                    "login_url": "https://notebooklm.google.com",
                    "success_indicators": ["notebooklm"],
                }
            }

            with mock.patch.object(auth_manager, "DATA_DIR", data_dir), \
                mock.patch.object(auth_manager, "AUTH_DIR", auth_dir), \
                mock.patch.object(auth_manager.AuthManager, "SERVICES", services):
                auth = auth_manager.AuthManager()
                result = auth.get_notebooklm_credentials(client=None)

            self.assertEqual(result["auth_token"], "cached-token")
            self.assertEqual(result["cookies"], "SID=abc")

    def test_get_notebooklm_credentials_persists_to_google_auth(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            auth_dir = data_dir / "auth"
            auth_dir.mkdir(parents=True, exist_ok=True)
            google_file = auth_dir / "google.json"
            google_file.write_text(json.dumps({"cookies": [], "origins": []}))

            services = {
                "google": {
                    "file": google_file,
                    "login_url": "https://notebooklm.google.com",
                    "success_indicators": ["notebooklm"]
                }
            }

            with mock.patch.object(auth_manager, "DATA_DIR", data_dir), \
                mock.patch.object(auth_manager, "AUTH_DIR", auth_dir), \
                mock.patch.object(auth_manager.AuthManager, "SERVICES", services):
                auth = auth_manager.AuthManager()
                client = DummyClient()
                result = auth.get_notebooklm_credentials(client=client)

            self.assertEqual(result["auth_token"], "token-xyz")
            self.assertEqual(result["cookies"], "SID=abc; HSID=def")

            saved = json.loads(google_file.read_text())
            self.assertEqual(saved["notebooklm_auth_token"], "token-xyz")
            self.assertEqual(saved["notebooklm_cookies"], "SID=abc; HSID=def")
            self.assertTrue(saved["notebooklm_updated_at"].endswith("+00:00"))

    def test_get_notebooklm_credentials_calls_setup_on_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            auth_dir = data_dir / "auth"
            auth_dir.mkdir(parents=True, exist_ok=True)
            google_file = auth_dir / "google.json"
            google_file.write_text(json.dumps({"cookies": [], "origins": []}))

            services = {
                "google": {
                    "file": google_file,
                    "login_url": "https://notebooklm.google.com",
                    "success_indicators": ["notebooklm"],
                }
            }

            def fake_setup(service="google"):
                google_file.write_text(
                    json.dumps(
                        {
                            "notebooklm_auth_token": "new-token",
                            "notebooklm_cookies": "SID=new",
                        }
                    )
                )
                return True

            with mock.patch.object(auth_manager, "DATA_DIR", data_dir), \
                mock.patch.object(auth_manager, "AUTH_DIR", auth_dir), \
                mock.patch.object(auth_manager.AuthManager, "SERVICES", services), \
                mock.patch.object(auth_manager.AuthManager, "setup", side_effect=fake_setup) as setup:
                auth = auth_manager.AuthManager()
                client = DummyClientNoToken()
                result = auth.get_notebooklm_credentials(client=client)

            self.assertEqual(result["auth_token"], "new-token")
            self.assertEqual(result["cookies"], "SID=new")
            self.assertTrue(setup.called)


class NotebookLMHttpFallbackTests(unittest.TestCase):
    def test_extracts_token_from_html(self):
        html = '...\"SNlM0e\":\"token-123\"...'
        token = auth_manager.AuthManager._extract_notebooklm_token_from_html(html)
        self.assertEqual(token, "token-123")

    def test_stale_credentials_trigger_refresh(self):
        stale_time = (datetime.now(timezone.utc) - timedelta(days=11)).isoformat()
        payload = {
            "notebooklm_auth_token": "cached-token",
            "notebooklm_cookies": "SID=cached",
            "notebooklm_updated_at": stale_time,
            "cookies": [
                {"name": "SID", "value": "abc", "domain": ".google.com"},
            ],
        }

        def fake_urlopen(request, timeout=10):
            return FakeResponse('\"SNlM0e\":\"fresh-token\"')

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            auth_dir = data_dir / "auth"
            auth_dir.mkdir(parents=True, exist_ok=True)
            google_file = auth_dir / "google.json"
            google_file.write_text(json.dumps(payload))

            services = {
                "google": {
                    "file": google_file,
                    "login_url": "https://notebooklm.google.com",
                    "success_indicators": ["notebooklm"],
                }
            }

            with mock.patch.object(auth_manager, "DATA_DIR", data_dir), \
                mock.patch.object(auth_manager, "AUTH_DIR", auth_dir), \
                mock.patch.object(auth_manager.AuthManager, "SERVICES", services), \
                mock.patch.object(auth_manager, "urlopen", side_effect=fake_urlopen, create=True):
                auth = auth_manager.AuthManager()
                result = auth.get_notebooklm_credentials(client=DummyClientNoToken())

        self.assertEqual(result["auth_token"], "fresh-token")

    def test_refresh_failure_returns_cached(self):
        stale_time = (datetime.now(timezone.utc) - timedelta(days=11)).isoformat()
        payload = {
            "notebooklm_auth_token": "cached-token",
            "notebooklm_cookies": "SID=cached",
            "notebooklm_updated_at": stale_time,
            "cookies": [
                {"name": "SID", "value": "abc", "domain": ".google.com"},
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            auth_dir = data_dir / "auth"
            auth_dir.mkdir(parents=True, exist_ok=True)
            google_file = auth_dir / "google.json"
            google_file.write_text(json.dumps(payload))

            services = {
                "google": {
                    "file": google_file,
                    "login_url": "https://notebooklm.google.com",
                    "success_indicators": ["notebooklm"],
                }
            }

            with mock.patch.object(auth_manager, "DATA_DIR", data_dir), \
                mock.patch.object(auth_manager, "AUTH_DIR", auth_dir), \
                mock.patch.object(auth_manager.AuthManager, "SERVICES", services), \
                mock.patch.object(auth_manager, "urlopen", side_effect=Exception("boom"), create=True), \
                mock.patch.object(auth_manager.AuthManager, "_extract_notebooklm_credentials", return_value=None), \
                mock.patch.object(auth_manager.AuthManager, "setup", return_value=False):
                auth = auth_manager.AuthManager()
                result = auth.get_notebooklm_credentials(client=DummyClientNoToken())

        self.assertEqual(result["auth_token"], "cached-token")
        self.assertEqual(result["cookies"], "SID=cached")


if __name__ == "__main__":
    unittest.main()
