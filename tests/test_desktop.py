"""Exercise the real Qt window, WebChannel, network worker and clipboard offline."""

import json
import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QLineEdit, QMessageBox

from backend.config import Config
from backend.key_manager import Vault
from main import AppPage, Window
from tests.test_providers import MemoryCredentials


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/api/tags":
            page = {"models": [{"name": "fixture-ollama"}]}
        elif self.path == "/v1/models":
            page = {"data": [{"id": "fixture-lm"}]}
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(page).encode())

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.calls.append(body)
        prompt = body["messages"][-1]["content"]
        if prompt == "invalid key":
            self.send_error(401)
            return
        self.send_response(200)
        self.end_headers()
        ollama = self.path == "/api/chat"

        def emit(text, done=False):
            frame = (
                {"message": {"content": text}, "done": done}
                if ollama
                else {
                    "choices": [
                        {
                            "delta": {"content": text},
                            "finish_reason": "stop" if done else None,
                        }
                    ]
                }
            )
            self.wfile.write(
                (
                    ("" if ollama else "data: ")
                    + json.dumps(frame)
                    + ("\n" if ollama else "\n\n")
                ).encode()
            )
            self.wfile.flush()

        try:
            emit("Hello ")
            if prompt in ("stop me", "close me"):
                self.server.release.wait(8)
            else:
                time.sleep(0.12)
            emit(
                "**world**\n\n```python\nprint(42)\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n<script>window.badScript=true</script> [unsafe](javascript:alert(1))",
                True,
            )
        except (BrokenPipeError, ConnectionResetError):
            pass


class DesktopTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setApplicationName("MULTI-AI-Test")
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "settings.json"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        self.server.release = threading.Event()
        self.server.calls = []
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.release.set)
        cfg = Config(self.path)
        base = "http://127.0.0.1:" + str(self.server.server_port)
        cfg.update(
            endpoints=cfg.data["endpoints"] | {"lmstudio": base + "/v1", "ollama": base}
        )
        self.vault = Vault(MemoryCredentials())
        self.errors = []

        def console(page, level, message, line, source):
            if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
                self.errors.append((message, line))

        self.original_console = AppPage.javaScriptConsoleMessage
        AppPage.javaScriptConsoleMessage = console
        self.addCleanup(
            setattr, AppPage, "javaScriptConsoleMessage", self.original_console
        )
        self.open(cfg)

    def open(self, cfg):
        self.w = Window(cfg, self.vault)
        self.addCleanup(self.w.close)
        self.w.show()
        self.until(
            "typeof active !== 'undefined' && !!active && S.status.lmstudio?.state==='online' && S.status.ollama?.state==='online'"
        )

    def js(self, code):
        result = []
        self.w.page.runJavaScript(code, 0, lambda value: result.append(value))
        deadline = time.monotonic() + 5
        while not result and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(result, code)
        return result[0]

    def until(self, condition):
        deadline = time.monotonic() + 18
        while time.monotonic() < deadline:
            if self.js(condition):
                return
            QTest.qWait(30)
        diag = self.js(
            "JSON.stringify([document.readyState,location.href,typeof desktop,typeof S==='object'?S.status:null])"
        )
        self.fail(
            f"Timed out: {condition}. Page: {diag}. Console errors: {self.errors}"
        )

    def send(self, text):
        self.js(
            f'$("prompt").value={json.dumps(text)};$("prompt").dispatchEvent(new Event("input"));$("send").click()'
        )

    def test_window_conversation_and_restart(self):
        self.w.showMinimized()
        self.assertTrue(self.w.isMinimized())
        self.w.showMaximized()
        self.assertTrue(self.w.isMaximized())
        self.w.showNormal()
        self.assertFalse(self.w.isMaximized() or self.w.isMinimized())
        self.w.resize(640, 540)
        QTest.qWait(100)
        self.assertEqual(self.w.width(), 640)
        self.js('document.querySelector(".expand").click()')
        self.assertFalse(self.js('$("shell").classList.contains("collapsed")'))
        self.js('document.querySelector(".collapse").click()')
        self.assertTrue(self.js('$("shell").classList.contains("collapsed")'))
        self.assertTrue(self.js('$("send").disabled'))
        self.js(
            '$("pick").click();[...document.querySelectorAll(".choice")].find(b=>b.title==="fixture-lm").click()'
        )
        self.send("memory-only-canary")
        self.until("active.messages.at(-1)?.state==='complete'")
        self.assertTrue(
            self.js(
                '!!document.querySelector(".body strong") && !!document.querySelector(".body table") && !!document.querySelector(".hljs-built_in")'
            )
        )
        self.assertFalse(
            self.js(
                'Boolean(window.badScript || document.querySelector(".body script,.body [href^=javascript]"))'
            )
        )
        self.js('document.querySelector(".codebar button").click()')
        self.until("true")
        self.assertEqual(self.app.clipboard().text(), "print(42)\n")
        self.js(
            '$("pick").click();[...document.querySelectorAll(".choice")].find(b=>b.title==="fixture-ollama").click()'
        )
        self.send("second question")
        self.until(
            "active.messages.length===4 && active.messages.at(-1).state==='complete'"
        )
        call = self.server.calls[-1]
        self.assertEqual(call["model"], "fixture-ollama")
        self.assertEqual(call["messages"][1]["content"], "memory-only-canary")
        self.assertEqual(call["messages"][2]["role"], "assistant")
        self.js(
            'document.querySelector(".msg.user .actions button:last-child").click()'
        )
        self.send("edited question")
        self.until(
            "active.messages.length===2 && active.messages.at(-1).state==='complete'"
        )
        self.js(
            'document.querySelector(".msg.assistant .actions button:last-child").click()'
        )
        self.until("!active.job")
        self.assertEqual(len(self.server.calls), 4)
        self.send("invalid key")
        self.until("active.messages.at(-1)?.state==='failed'")
        self.assertIn(
            "Authentication",
            self.js('document.querySelector(".msg-state.error").textContent'),
        )
        self.js(
            'document.querySelector(".msg:last-child .actions button:last-child").click()'
        )
        self.until("!active.job")
        self.assertEqual(len(self.server.calls), 6)
        self.send("stop me")
        self.until("active.messages.at(-1)?.content==='Hello '")
        self.js('$("send").click()')
        self.until("active.messages.at(-1)?.state==='stopped'")
        self.js('$("new").click()')
        self.assertTrue(self.js("chats.length===2 && active.messages.length===0"))
        self.js('$("history").children[1].click()')
        self.assertTrue(self.js("active.messages.length===6"))
        self.send("close me")
        self.until("active.messages.at(-1)?.content==='Hello '")
        self.w.close()
        self.assertFalse(self.w.bridge.engine.worker.is_alive())
        self.assertNotIn("memory-only-canary", self.path.read_text())
        self.assertNotIn("edited question", self.path.read_text())
        self.open(Config(self.path))
        self.assertTrue(self.js("chats.length===1 && active.messages.length===0"))
        self.assertTrue(self.w.profile.isOffTheRecord())
        self.assertEqual(self.errors, [])

    def test_provider_registry_add_delete_restore_without_code_changes(self):
        self.js('document.querySelector("[data-page=connections]").click()')
        self.assertTrue(self.js('Boolean($("card-groq") && $("add-provider"))'))
        self.assertFalse(self.js('Boolean($("card-xai"))'))
        # User can remove Google Gemini without deleting files, then add it back.
        def confirm():
            dialog = self.app.activeModalWidget()
            if isinstance(dialog, QMessageBox):
                dialog.button(QMessageBox.StandardButton.Yes).click()
            else:
                QTimer.singleShot(20, confirm)

        QTimer.singleShot(30, confirm)
        self.js('$("card-google").querySelector(".remove-provider").click()')
        self.until('!S.providers.google')
        self.assertFalse(self.js('!!$("card-google")'))
        self.assertNotIn('"id": "google"', self.path.read_text())

        self.js('$("provider-template").value="google";$("provider-template").dispatchEvent(new Event("change"))')
        self.js('$("add-provider").querySelector("form").requestSubmit()')
        self.until('S.providers.google==="Google Gemini"')
        self.assertTrue(self.js('!!$("card-google")'))
        # Add arbitrary OpenAI-compatible API, then test catalog and model picker.
        base = "http://127.0.0.1:" + str(self.server.server_port) + "/v1"
        self.js('$("provider-template").value="custom-local";$("provider-template").dispatchEvent(new Event("change"))')
        self.js('$("provider-name").value="My Custom Local";$("provider-url").value=' + json.dumps(base))
        self.js('$("add-provider").querySelector("form").requestSubmit()')
        self.until('Object.values(S.providers).includes("My Custom Local")')
        pid = self.js('Object.keys(S.providers).find(p=>S.providers[p]==="My Custom Local")')
        self.assertTrue(pid.startswith("custom-"))
        self.until('S.status[' + json.dumps(pid) + ']?.state==="online"')
        self.assertTrue(self.js('S.catalog.some(m=>m.provider===' + json.dumps(pid) + ' && m.id==="fixture-lm")'))
        QTimer.singleShot(30, confirm)
        self.js('$("card-"+' + json.dumps(pid) + ').querySelector(".remove-provider").click()')
        self.until('!S.providers[' + json.dumps(pid) + ']')
        self.assertNotIn("My Custom Local", self.path.read_text())
        self.assertEqual(self.errors, [])

    def test_connections_settings_and_models(self):
        self.js('$("cloudQuick").click()')
        self.assertTrue(
            self.js('document.querySelectorAll("#panel .group").length===7')
        )

        def fill(value):
            def run():
                d = self.app.activeModalWidget()
                if not isinstance(d, QDialog):
                    QTimer.singleShot(30, run)
                    return
                f = d.findChild(QLineEdit)
                d.findChild(QCheckBox).setChecked(True)
                self.assertEqual(f.echoMode(), QLineEdit.EchoMode.Normal)
                f.setText(value)
                d.accept()

            QTimer.singleShot(30, run)

        fill("credential-test-only")
        self.js('document.querySelector("#card-anthropic .primary").click()')
        self.until("S.keys.anthropic")
        self.assertEqual(self.vault.get("anthropic", ""), "credential-test-only")
        self.assertNotIn(
            "credential-test-only", self.js("JSON.stringify(S)+document.body.innerHTML")
        )
        fill("updated-key")
        self.js('document.querySelector("#card-anthropic .primary").click()')
        self.until(
            'document.querySelector("#card-anthropic .primary").textContent==="Manage key"'
        )
        QTest.qWait(150)
        self.assertEqual(self.vault.get("anthropic", ""), "updated-key")

        def confirm():
            d = self.app.activeModalWidget()
            if isinstance(d, QMessageBox):
                d.button(QMessageBox.StandardButton.Yes).click()
            else:
                QTimer.singleShot(30, confirm)

        QTimer.singleShot(30, confirm)
        self.js('document.querySelector("#card-anthropic .subtle").click()')
        self.until("!S.keys.anthropic")
        self.js(
            'document.querySelector("[data-page=models]").click();$("new-provider").value="ollama";$("new-id").value="custom:tag";$("new-name").value="My model";document.querySelector("#add-model form").requestSubmit()'
        )
        self.until('S.catalog.some(m=>m.name==="My model")')
        self.js(
            'document.querySelector("[data-page=settings]").click();[...document.querySelectorAll(".tabs button")].find(b=>b.textContent==="AI settings").click()'
        )
        self.js(
            '$("default-provider").value="ollama";$("default-provider").dispatchEvent(new Event("change"));$("default-model").value="custom:tag";$("system").value="Test system prompt";$("tokens").value=128;document.querySelector("#panel form").requestSubmit()'
        )
        self.until('S.settings.tokens===128 && S.settings.defaultModel==="custom:tag"')
        self.js('$("new").click()')
        self.assertEqual(self.js("active.model.name"), "My model")
        self.assertNotIn("updated-key", self.path.read_text())
        self.assertEqual(self.errors, [])
