import asyncio
import copy
import queue
import unittest

import httpx

from backend.ai_manager import Engine
from backend.config import DEFAULTS
from backend.key_manager import Vault
from tests.test_providers import MemoryCredentials


class EngineTests(unittest.TestCase):
    def run_error(self, handler, provider="lmstudio"):
        events = queue.Queue()
        engine = Engine(
            Vault(MemoryCredentials()), events.put, httpx.MockTransport(handler)
        )
        try:
            engine.start("test", provider, copy.deepcopy(DEFAULTS))
            message = events.get(timeout=5)
            self.assertEqual(message["type"], "failed")
            return message["message"]
        finally:
            engine.close()

    def test_timeout(self):
        def timeout(request):
            raise httpx.ReadTimeout("test timeout")

        self.assertIn("timed out", self.run_error(timeout))

    def test_offline_local(self):
        def offline(request):
            raise httpx.ConnectError("test connection refused")

        self.assertIn("Start LM Studio or Ollama", self.run_error(offline))

    def test_discovery_unavailable(self):
        self.assertIn("manually", self.run_error(lambda request: httpx.Response(405)))

    def test_no_cloud_key(self):
        self.assertIn(
            "Add an API key",
            self.run_error(lambda request: self.fail("Unexpected network call"), "xai"),
        )

    def test_cancel_while_waiting_for_headers(self):
        entered, events = queue.Queue(), queue.Queue()

        async def wait_for_response(request):
            entered.put(True)
            await asyncio.Event().wait()

        engine = Engine(
            Vault(MemoryCredentials()),
            events.put,
            httpx.MockTransport(wait_for_response),
        )
        try:
            engine.start("test", "ollama", copy.deepcopy(DEFAULTS))
            self.assertTrue(entered.get(timeout=5))
            engine.cancel("test")
            self.assertEqual(events.get(timeout=5)["type"], "stopped")
        finally:
            engine.close()
