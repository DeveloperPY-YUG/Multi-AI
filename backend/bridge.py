"""The only registered WebChannel object. Key editing stays in native widgets."""

import json
import uuid

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from .ai_manager import Engine
from .config import endpoint, preferences
from .model_manager import Models


class Delivery(QObject):
    # Qt's queued QString delivery is reliable across the network worker and
    # GUI threads, including on Windows runners without a nested event loop.
    arrived = Signal(str)

    def __init__(self, receive, parent):
        super().__init__(parent)
        self.receive = receive
        self.arrived.connect(self.deliver, Qt.ConnectionType.QueuedConnection)

    @Slot(str)
    def deliver(self, message):
        self.receive(json.loads(message))


class Bridge(QObject):
    event = Signal(str)

    def __init__(self, window, config, vault, transport=None):
        super().__init__(window)
        self.window, self.config, self.vault = window, config, vault
        self.models = Models(config)
        self.jobs = {}
        self.probes = {}
        self.status = {}
        self.keys = {}
        self.closed = False
        self.delivery = Delivery(self._receive, self)
        self.engine = Engine(
            vault, lambda message: self.delivery.arrived.emit(json.dumps(message)), transport
        )
        for p, profile in self.config.registry.items():
            if not profile["local"]:
                self._key_status(p)

    def _key_status(self, p):
        try:
            base = self.config.data["endpoints"].get(p, "")
            self.keys[p] = bool(base and self.vault.get(p, base))
        except ValueError:
            self.keys[p] = False

    def _emit(self, kind, **fields):
        self.event.emit(json.dumps({"type": kind, **fields}))

    def _state(self):
        self._emit(
            "state",
            settings=self.config.data,
            catalog=self.models.all(),
            status=self.status,
            keys=self.keys,
            providers={p["id"]: p["name"] for p in self.config.data["providers"]},
            providerInfo=self.config.registry,
        )

    @Slot()
    def ready(self):
        self._state()
        if self.config.warning:
            self._emit("notice", message=self.config.warning)
        for p, profile in self.config.registry.items():
            if profile["local"]:
                self.probe(p)

    def _invalidate(self, p):
        for token, provider in list(self.jobs.items()):
            if provider == p:
                del self.jobs[token]
                self.engine.cancel(token)
                self._emit("stopped", token=token, provider=p)
        self.status.pop(p, None)
        self.models.discovered.pop(p, None)
        token = self.probes.pop(p, None)
        if token:
            self.engine.cancel(token)

    @Slot(str)
    def probe(self, p):
        if p not in self.config.registry or p in self.probes or self.closed:
            return
        token = uuid.uuid4().hex
        self.probes[p] = token
        self.status[p] = {"state": "checking", "message": "Checking connection…"}
        self._state()
        self.engine.start(token, p, self.config.data)

    def _receive(self, msg):
        if self.closed:
            return
        token, kind, p = msg["token"], msg["type"], msg["provider"]
        if token == self.probes.get(p):
            self.probes.pop(p)
            if kind == "catalog":
                self.models.discovered[p] = msg["models"]
                self.status[p] = {
                    "state": "online",
                    "message": f"{len(msg['models'])} models found",
                }
            else:
                self.models.discovered.pop(p, None)
                self.status[p] = {
                    "state": "error",
                    "message": msg.get("message", "Check cancelled."),
                }
            self._state()
        elif token in self.jobs:
            if kind != "chunk":
                self.jobs.pop(token)
            if kind == "complete" and p not in self.probes:
                self.status[p] = {"state": "online", "message": "Generation succeeded."}
                self._state()
            self.event.emit(json.dumps(msg))

    @Slot(str, str)
    def generate(self, token, payload):
        if self.closed or token in self.jobs:
            return
        try:
            args = json.loads(payload)
            p, mid, messages = args["provider"], args["id"], args["messages"]
            if not any((m["provider"], m["id"]) == (p, mid) for m in self.models.all()):
                raise ValueError("Select an available or saved model first.")
            if (
                not isinstance(messages, list)
                or not messages
                or messages[-1]["role"] != "user"
                or not all(
                    isinstance(m, dict)
                    and set(m) == {"role", "content"}
                    and m["role"] in {"user", "assistant", "system"}
                    and isinstance(m["content"], str)
                    and m["content"].strip()
                    for m in messages
                )
            ):
                raise ValueError("Enter a message before sending.")
            self.jobs[token] = p
            self.engine.start(token, p, self.config.data, mid, messages)
        except (KeyError, TypeError, ValueError) as e:
            self._emit(
                "failed",
                token=token,
                message=str(e) if type(e) is ValueError else "Invalid chat request.",
            )

    @Slot(str)
    def stop(self, token):
        if token in self.jobs:
            self.engine.cancel(token)

    @Slot(str, str)
    def saveEndpoint(self, p, url):
        try:
            profile = self.config.registry.get(p)
            if not profile:
                raise ValueError("This provider has been removed.")
            value = endpoint(p, url, profile)
            if self.config.data["endpoints"][p] == value:
                self._emit("notice", message="Endpoint saved.")
                return
            self.config.update(endpoints=self.config.data["endpoints"] | {p: value})
            self._invalidate(p)
            if not profile["local"]:
                self._key_status(p)
            self._state()
            self._emit("notice", message="Endpoint saved.")
            if profile["local"]:
                self.probe(p)
        except (ValueError, OSError) as e:
            self._error(e)

    def _error(self, e):
        self._emit(
            "notice",
            message=str(e)
            if isinstance(e, ValueError)
            else "Could not save preferences.",
        )

    @Slot(str, str, str)
    def saveModel(self, p, mid, name):
        try:
            self.models.save(p, mid, name)
            self._state()
            row = self.config.data["models"][-1]
            known = self.models.discovered.get(p)
            if known is None:
                note = "Manual model saved. Test & refresh to check its availability."
            elif any(m["id"] == row["id"] for m in known):
                note = "Model saved and verified in the provider catalog."
            else:
                note = "Manual model saved. This ID was absent from the last provider catalog."
            self._emit("modelSaved", provider=p, message=note)
        except (ValueError, OSError) as e:
            self._error(e)

    @Slot(str, str)
    def removeModel(self, p, mid):
        try:
            self.models.remove(p, mid)
            self._state()
        except (ValueError, OSError) as e:
            self._error(e)

    @Slot(str, str)
    def restoreModel(self, p, mid):
        try:
            self.models.restore(p, mid)
            self._state()
        except (ValueError, OSError) as e:
            self._error(e)

    @Slot(str)
    def savePreferences(self, raw):
        try:
            values = preferences(json.loads(raw))
            p, mid = values["defaultProvider"], values["defaultModel"]
            if p not in self.config.registry and (p or self.config.registry):
                raise ValueError("Choose an installed default provider.")
            if mid:
                model = next(
                    (
                        m
                        for m in self.models.all()
                        if (m["provider"], m["id"]) == (p, mid)
                    ),
                    None,
                )
                if model is None:
                    raise ValueError("Select a listed default model.")
                if not model["saved"]:
                    values["models"] = self.config.data["models"] + [
                        {k: model[k] for k in ("provider", "id", "name")}
                    ]
            self.config.update(**values)
            self.window.set_zoom(values["scale"] / 100)
            self._state()
            self._emit("preferencesSaved")
        except (KeyError, TypeError, ValueError, OSError) as e:
            self._error(e)

    @Slot(str, str, str)
    def addProvider(self, selected, name, base):
        """Profiles are registered at runtime; no source edits or restarts required."""
        try:
            pid = self.config.add_provider(selected, name, base)
            profile = self.config.registry[pid]
            if not profile["local"]:
                self._key_status(pid)
            self._state()
            self._emit("providerAdded", provider=pid, message=profile["name"] + " added.")
            if profile["local"]:
                self.probe(pid)
        except (ValueError, OSError) as e:
            self._error(e)

    @Slot(str)
    def removeProvider(self, p):
        profile = self.config.registry.get(p)
        if not profile:
            self._emit("notice", message="Provider not found.")
            return
        question = (
            f"Remove {profile['name']}?\n\n"
            "Its saved models and API key will be deleted. "
            "You can add this provider again at any time."
        )
        if QMessageBox.question(self.window, "Remove provider", question) != QMessageBox.StandardButton.Yes:
            return
        try:
            base = self.config.data["endpoints"].get(p, "")
            if not profile["local"] and base:
                self.vault.delete(p, base)
            self._invalidate(p)
            self.config.remove_provider(p)
            self.keys.pop(p, None)
            self.status.pop(p, None)
            self._state()
            self._emit("notice", message=profile["name"] + " removed.")
        except (ValueError, OSError) as e:
            self._error(e)

    @Slot(str)
    def editKey(self, p):
        profile = self.config.registry.get(p)
        if not profile or profile["local"]:
            return
        base = self.config.data["endpoints"].get(p, "")
        if not base:
            self._emit("notice", message="Set the API base URL first.")
            return
        try:
            old = self.vault.get(p, base) or ""
        except ValueError as e:
            self._error(e)
            return
        dialog = QDialog(self.window)
        dialog.setWindowTitle(profile["name"] + " API key")
        dialog.setMinimumWidth(380)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("API key for " + profile["name"]))
        location = QLabel(base)
        location.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(location)
        field = QLineEdit(dialog)
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setText(old)
        layout.addWidget(field)
        show = QCheckBox("Show key")
        show.toggled.connect(
            lambda checked: field.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        layout.addWidget(show)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.vault.save(p, base, field.text())
                self._invalidate(p)
                self._key_status(p)
                self._state()
                self._emit("notice", message="API key saved.")
            except ValueError as e:
                self._error(e)
        field.clear()
        dialog.deleteLater()

    @Slot(str)
    def deleteKey(self, p):
        profile = self.config.registry.get(p)
        if not profile or profile["local"]:
            return
        if (
            QMessageBox.question(
                self.window,
                "Remove API key",
                f"Remove the saved {profile['name']} key for this endpoint?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self.vault.delete(p, self.config.data["endpoints"][p])
            self._invalidate(p)
            self._key_status(p)
            self._state()
            self._emit("notice", message="API key removed.")
        except ValueError as e:
            self._error(e)

    @Slot(str)
    def copyText(self, value):
        QApplication.clipboard().setText(value)

    def close(self):
        self.closed = True
        self.engine.close()
