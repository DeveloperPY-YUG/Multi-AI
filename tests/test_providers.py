import copy
import json
import tempfile
import unittest
from pathlib import Path

import httpx

from backend.config import BASES, DEFAULTS, Config, endpoint, model_entry
from backend.key_manager import Vault
from backend.model_manager import Models
from backend.providers import ProviderError, discover, headers, stream


class MemoryCredentials:
    """Test double for the OS credential backend."""

    def __init__(self):
        self.rows = {}

    def get_password(self, service, name):
        return self.rows.get((service, name))

    def set_password(self, service, name, value):
        self.rows[service, name] = value

    def delete_password(self, service, name):
        del self.rows[service, name]


class StorageTests(unittest.TestCase):
    def test_address_validation(self):
        for address in (
            "http://192.168.1.4",
            "http://localhost.example",
            "ftp://127.0.0.1",
            "http://name@localhost",
            "http://localhost?key=bad",
            "http://localhost:99999",
        ):
            with self.subTest(address=address), self.assertRaises(ValueError):
                endpoint("ollama", address)
        self.assertEqual(
            endpoint("ollama", "http://[::1]:11434/"), "http://[::1]:11434"
        )
        with self.assertRaises(ValueError):
            endpoint("qwen", "http://example.com")
        self.assertEqual(
            endpoint("qwen", "https://example.com/api/v1"), "https://example.com/api/v1"
        )

    def test_vault_scope_update_and_delete(self):
        v = Vault(MemoryCredentials())
        v.save("qwen", "https://a.example/v1", "temporary-test-key")
        self.assertIsNone(v.get("qwen", "https://b.example/v1"))
        v.save("qwen", "https://a.example/v1", "replacement")
        self.assertEqual(v.get("qwen", "https://a.example/v1"), "replacement")
        v.delete("qwen", "https://a.example/v1")
        self.assertIsNone(v.get("qwen", "https://a.example/v1"))

    def test_models_roundtrip_and_remove(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "settings.json"
            mm = Models(Config(path))
            mm.save("google", "models/example", "A")
            mm.save("google", "example", "B")
            mm = Models(Config(path))
            mm.discovered["google"] = [
                model_entry("google", "example", "Provider name")
            ]
            (row,) = [m for m in mm.all() if m["provider"] == "google"]
            self.assertTrue(row["saved"] and row["discovered"])
            self.assertEqual(row["name"], "B")
            mm.remove("google", "example")
            self.assertFalse(any(m["provider"] == "google" for m in mm.all()))
            self.assertIn(["google", "example"], Config(path).data["hiddenModels"])
            mm.restore("google", "example")
            restored = next(m for m in mm.all() if m["provider"] == "google")
            self.assertEqual(restored["name"], "B")
            self.assertTrue(restored["saved"])


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_stream_formats(self):
        cfg = copy.deepcopy(DEFAULTS)
        for p in BASES:
            with self.subTest(provider=p):

                def reply(req, p=p):
                    body = json.loads(req.content)
                    if p == "google":
                        self.assertIn(":streamGenerateContent", req.url.path)
                        self.assertEqual(req.headers["x-goog-api-key"], "test")
                        self.assertEqual(body["contents"][1]["role"], "model")
                        self.assertEqual(
                            body["systemInstruction"]["parts"][0]["text"], cfg["system"]
                        )
                        frames = [
                            {
                                "candidates": [
                                    {
                                        "content": {
                                            "parts": [
                                                {"text": "hidden", "thought": True},
                                                {"text": "OK"},
                                            ]
                                        },
                                        "finishReason": "STOP",
                                    }
                                ]
                            }
                        ]
                    elif p == "anthropic":
                        self.assertEqual(req.headers["x-api-key"], "test")
                        self.assertTrue(req.url.path.endswith("/messages"))
                        self.assertEqual(body["system"], cfg["system"])
                        frames = [
                            {
                                "type": "content_block_delta",
                                "delta": {"type": "text_delta", "text": "OK"},
                            },
                            {"type": "message_stop"},
                        ]
                    elif p == "ollama":
                        self.assertTrue(req.url.path.endswith("/api/chat"))
                        self.assertEqual(body["options"]["num_predict"], cfg["tokens"])
                        self.assertNotIn("authorization", req.headers)
                        return httpx.Response(
                            200,
                            text='{"message":{"content":"OK"},"done":false}\n{"done":true}\n',
                        )
                    else:
                        self.assertTrue(req.url.path.endswith("/chat/completions"))
                        self.assertEqual(body["messages"][0]["role"], "system")
                        if p != "lmstudio":
                            self.assertEqual(
                                req.headers["authorization"], "Bearer test"
                            )
                        frames = [{"choices": [{"delta": {"content": "OK"}}]}, "[DONE]"]
                    return httpx.Response(
                        200,
                        text="".join(
                            "data: "
                            + (f if isinstance(f, str) else json.dumps(f))
                            + "\n\n"
                            for f in frames
                        ),
                    )

                msgs = [
                    {"role": "user", "content": "one"},
                    {"role": "assistant", "content": "two"},
                    {"role": "user", "content": "three"},
                ]
                async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as c:
                    parts = [
                        s
                        async for s in stream(
                            c,
                            p,
                            BASES[p] or "https://example.org/v1",
                            headers(p, "test"),
                            "example",
                            msgs,
                            cfg,
                        )
                    ]
                self.assertEqual("".join(parts), "OK")

    async def test_discovery_pagination_and_filter(self):
        for p in BASES:

            def reply(req, p=p):
                if p == "google":
                    n = "2" if "pageToken" in req.url.params else "1"
                    page = {
                        "models": [
                            {
                                "name": "models/chat" + n,
                                "supportedGenerationMethods": ["generateContent"],
                            },
                            {"name": "models/embed"},
                        ]
                    }
                    if n == "1":
                        page["nextPageToken"] = "next"
                elif p == "anthropic":
                    later = "after_id" in req.url.params
                    page = {
                        "data": [{"id": "chat2" if later else "chat1"}],
                        "has_more": not later,
                        "last_id": "chat1",
                    }
                elif p == "ollama":
                    page = {"models": [{"name": "chat1"}]}
                else:
                    page = {"data": [{"id": "chat1"}]}
                return httpx.Response(200, json=page)

            async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as c:
                result = await discover(c, p, BASES[p] or "https://example.org", {})
                self.assertEqual(
                    [r["id"] for r in result],
                    ["chat1", "chat2"] if p in {"google", "anthropic"} else ["chat1"],
                )

    async def test_errors_and_truncation(self):
        for response, expected in [
            (httpx.Response(401), "Authentication"),
            (httpx.Response(429), "Rate limit"),
            (httpx.Response(404), "unavailable"),
            (
                httpx.Response(
                    200, text='data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
                ),
                "ended unexpectedly",
            ),
            (
                httpx.Response(400, json={"message": "API key not valid"}),
                "Authentication",
            ),
        ]:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(lambda req, response=response: response)
            ) as c:
                with self.assertRaisesRegex(ProviderError, expected):
                    _ = [
                        v
                        async for v in stream(
                            c,
                            "lmstudio",
                            BASES["lmstudio"],
                            {},
                            "example",
                            [],
                            DEFAULTS,
                        )
                    ]
