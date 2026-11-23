"""Dynamic add/remove/restore and OpenAI-compatible provider checks (offline)."""

import copy
import json
import queue
import tempfile
import unittest
from pathlib import Path

import httpx

from backend.ai_manager import Engine
from backend.config import Config, DEFAULTS, endpoint
from backend.key_manager import Vault
from backend.model_manager import Models
from tests.test_providers import MemoryCredentials


class DynamicProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "settings.json"
        self.cfg = Config(self.path)

    def test_default_groq_and_add_remove_any_builtin(self):
        self.assertIn("groq", self.cfg.registry)
        self.assertNotIn("xai", self.cfg.registry)
        self.assertEqual(self.cfg.data["endpoints"]["groq"], "https://api.groq.com/openai/v1")
        self.cfg.remove_provider("google")
        self.assertNotIn("google", self.cfg.registry)
        self.assertNotIn("google", Config(self.path).registry)
        self.cfg.add_provider("google", "Google AI Studio")
        self.assertEqual(self.cfg.registry["google"]["name"], "Google AI Studio")
        self.assertIn("google", Config(self.path).registry)
        self.cfg.remove_provider("anthropic")
        self.assertNotIn("anthropic", self.cfg.registry)
        self.assertEqual(self.cfg.data["defaultModel"], "")
        self.assertFalse(any(m["provider"] == "anthropic" for m in self.cfg.data["models"]))
        self.assertNotEqual(self.cfg.data["defaultProvider"], "anthropic")
        self.cfg.add_provider("anthropic")
        self.assertIn("anthropic", self.cfg.registry)

    def test_custom_openai_cloud_and_local_persist(self):
        pid = self.cfg.add_provider("custom-cloud", "My AI", "https://example.org/api/v1")
        self.assertEqual(self.cfg.registry[pid]["protocol"], "openai")
        self.assertFalse(self.cfg.registry[pid]["local"])
        self.assertEqual(self.cfg.data["endpoints"][pid], "https://example.org/api/v1")
        mid = "some-custom-model"
        Models(self.cfg).save(pid, mid, "Custom Model")
        loaded = Config(self.path)
        self.assertIn(pid, loaded.registry)
        self.assertIn(mid, [r["id"] for r in Models(loaded).all()])
        self.cfg.remove_provider(pid)
        loaded = Config(self.path)
        self.assertNotIn(pid, loaded.registry)
        self.assertNotIn(pid, loaded.data["endpoints"])
        self.assertFalse(any(r["provider"] == pid for r in Models(loaded).all()))
        local = self.cfg.add_provider("custom-local", "My Local", "http://localhost:8080/v1")
        self.assertTrue(Config(self.path).registry[local]["local"])
        with self.assertRaises(ValueError):
            self.cfg.add_provider("custom-cloud", "Bad", "http://example.com/v1")
        with self.assertRaises(ValueError):
            self.cfg.add_provider("custom-local", "Bad", "http://10.0.0.10/v1")
        with self.assertRaises(ValueError):
            self.cfg.add_provider("custom-cloud", "Bad", "https://test@example.com/v1")

    def test_credentials_scoped_to_custom_endpoint(self):
        v = Vault(MemoryCredentials())
        pid = self.cfg.add_provider("custom-cloud", "Cloud", "https://example.com/v1")
        base = self.cfg.data["endpoints"][pid]
        v.save(pid, base, "secret-test")
        self.assertEqual(v.get(pid, base), "secret-test")
        self.assertIsNone(v.get(pid, "https://other.example.com/v1"))
        self.assertNotIn("secret-test", self.path.read_text())
        v.delete(pid, base)
        self.assertIsNone(v.get(pid, base))

    def test_upgrade_from_old_settings_without_registry(self):
        old = {k: copy.deepcopy(v) for k, v in DEFAULTS.items() if k != "providers"}
        old["endpoints"]["qwen"] = "https://qwen.example.com/compatible-mode/v1"
        old["models"].append({"provider": "xai", "id": "grok-example", "name": "X"})
        self.path.write_text(json.dumps(old))
        loaded = Config(self.path)
        self.assertIn("groq", loaded.registry)
        self.assertNotIn("xai", loaded.registry)
        self.assertEqual(loaded.data["endpoints"]["qwen"], old["endpoints"]["qwen"])
        self.assertFalse(any(m["provider"] == "xai" for m in loaded.data["models"]))
        self.assertEqual(loaded.warning, "")

    def test_no_providers_then_restore(self):
        for p in list(self.cfg.registry):
            self.cfg.remove_provider(p)
        self.assertEqual(self.cfg.data["providers"], [])
        self.assertEqual(self.cfg.data["defaultProvider"], "")
        self.assertEqual(Config(self.path).data["providers"], [])
        self.cfg.add_provider("groq")
        self.assertEqual(self.cfg.data["defaultProvider"], "groq")

    def test_custom_cloud_and_groq_real_protocol_mock(self):
        memory = MemoryCredentials()
        vault = Vault(memory)
        pid = self.cfg.add_provider("custom-cloud", "Test cloud", "https://test.example.com/v1")
        for provider in [pid, "groq"]:
            vault.save(provider, self.cfg.data["endpoints"][provider], "mock-secret")
            events = queue.Queue()

            def reply(request):
                self.assertTrue(request.url.path.endswith("/v1/models"))
                self.assertEqual(request.headers["Authorization"], "Bearer mock-secret")
                return httpx.Response(200, json={"data": [{"id": "mock-model"}]})

            engine = Engine(vault, events.put, httpx.MockTransport(reply))
            try:
                engine.start("catalog-test", provider, self.cfg.data)
                event = events.get(timeout=5)
                self.assertEqual(event["type"], "catalog", event)
                self.assertEqual(event["models"][0]["provider"], provider)
                self.assertEqual(event["models"][0]["id"], "mock-model")
            finally:
                engine.close()

    def test_custom_cloud_streaming(self):
        pid = self.cfg.add_provider("custom-cloud", "Testing", "https://example.org/v1")
        vault = Vault(MemoryCredentials())
        vault.save(pid, self.cfg.data["endpoints"][pid], "sample-key")
        events = queue.Queue()

        def reply(request):
            self.assertEqual(request.url.path, "/v1/chat/completions")
            self.assertEqual(request.headers["Authorization"], "Bearer sample-key")
            body = json.loads(request.content)
            self.assertEqual(body["model"], "a-chat-model")
            self.assertEqual(body["messages"][-1]["content"], "Hello")
            return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"Hi!"}}]}\n\ndata: [DONE]\n\n')

        engine = Engine(vault, events.put, httpx.MockTransport(reply))
        try:
            engine.start("chat-test", pid, self.cfg.data, "a-chat-model", [{"role":"user", "content":"Hello"}])
            self.assertEqual(events.get(timeout=5)["text"], "Hi!")
            self.assertEqual(events.get(timeout=5)["type"], "complete")
        finally:
            engine.close()


if __name__ == "__main__":
    unittest.main()
