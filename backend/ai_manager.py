"""A single network loop owns all HTTP clients and cancels tasks before shutdown."""

import asyncio
import threading

import httpx

from . import providers
from .config import LOCAL, PRESETS
from .key_manager import CredentialError


class Engine:
    def __init__(self, vault, notify, transport=None):
        self.vault = vault
        self.notify = notify
        self.transport = transport
        self.loop = asyncio.new_event_loop()
        self.tasks = {}
        self.worker = threading.Thread(target=self._run, name="multi-ai-network")
        self.worker.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.run_until_complete(self.loop.shutdown_default_executor())
            self.loop.close()

    def start(self, token, p, cfg, mid=None, messages=None):
        def schedule():
            task = self.loop.create_task(self._request(token, p, cfg, mid, messages))
            self.tasks[token] = task

            def finished(t):
                self.tasks.pop(token, None)
                if t.cancelled():
                    self.notify({"type": "stopped", "token": token, "provider": p})
                elif t.exception() is not None:
                    # A backend failure must release the UI even for an unknown error.
                    self.notify(
                        {
                            "type": "failed",
                            "token": token,
                            "provider": p,
                            "message": "The request could not be completed. Try again.",
                        }
                    )

            task.add_done_callback(finished)

        self.loop.call_soon_threadsafe(schedule)

    def cancel(self, token):
        def stop():
            if token in self.tasks:
                self.tasks[token].cancel()

        self.loop.call_soon_threadsafe(stop)

    async def _request(self, token, p, cfg, mid, messages):
        def send(kind, **fields):
            self.notify({"token": token, "provider": p, "type": kind, **fields})

        try:
            info = next((r for r in cfg.get("providers", []) if r["id"] == p), None)
            if info is None:
                # Backwards compatibility for calls that bypass the Bridge.
                info = ({"protocol": PRESETS[p]["protocol"], "local": PRESETS[p]["local"]}
                        if p in PRESETS else None)
            if info is None:
                raise providers.ProviderError("Provider has been removed. Add it again first.")
            protocol, local = info["protocol"], info["local"]
            base = cfg["endpoints"].get(p, "")
            if not base:
                raise providers.ProviderError(
                    "Set the API base URL in API Connections."
                )
            key = "" if local else await asyncio.to_thread(self.vault.get, p, base)
            if not local and not key:
                raise providers.ProviderError(
                    "Add an API key in API Connections first."
                )
            auth = providers.headers(p, key, protocol, local)
            async with httpx.AsyncClient(
                transport=self.transport,
                timeout=cfg["timeout"],
                trust_env=False,
                follow_redirects=False,
            ) as client:
                if mid is None:
                    rows = await providers.discover(client, p, base, auth, protocol)
                    send("catalog", models=rows)
                else:
                    received = False
                    async for chunk in providers.stream(
                        client, p, base, auth, mid, messages, cfg, protocol
                    ):
                        received = True
                        send("chunk", text=chunk)
                    if not received:
                        raise providers.ProviderError(
                            "The model returned no text. Check the model and output token limit."
                        )
                    send("complete")
            return
        except (providers.ProviderError, CredentialError) as e:
            message = str(e)
        except httpx.TimeoutException:
            message = "The request timed out. Please try again."
        except httpx.RequestError:
            message = (
                "Cannot connect to the local AI server. Start LM Studio or Ollama."
                if local
                else "Network connection unavailable. Check your connection and endpoint."
            )
        except (
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            AttributeError,
            httpx.InvalidURL,
        ):
            message = (
                "The provider returned an unexpected response. Check the API endpoint."
            )
        send("failed", message=message)

    def close(self):
        async def shutdown():
            tasks = list(self.tasks.values())
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        asyncio.run_coroutine_threadsafe(shutdown(), self.loop).result()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.worker.join()
