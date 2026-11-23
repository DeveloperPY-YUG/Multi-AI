"""Credentials live in the Windows vault, not in settings or WebChannel."""

import hashlib
import re
import sys

SERVICE = "MULTI-AI"
LEGACY_SERVICE = "MULTIAI"  # Existing users' old Windows vault entries only.


class CredentialError(ValueError):
    """User-safe credential error."""


class Vault:
    def __init__(self, backend=None):
        self.backend = backend
        if backend is None and sys.platform == "win32":
            from keyring.backends.Windows import WinVaultKeyring
            self.backend = WinVaultKeyring()

    def _account(self, p, base):
        if not isinstance(p, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", p):
            raise CredentialError("Choose a cloud provider.")
        if p in {"lmstudio", "ollama"}:
            raise CredentialError("Local connections do not need API keys.")
        if p in {"google", "anthropic", "groq", "xai"}:
            return p
        if not base:
            raise CredentialError("Set the provider base URL first.")
        return p + "-" + hashlib.sha256(base.encode()).hexdigest()

    def _invoke(self, method, service, account, *args):
        if self.backend is None:
            raise CredentialError("Windows Credential Manager is required to store cloud keys.")
        try:
            return getattr(self.backend, method)(service, account, *args)
        except Exception:
            raise CredentialError("Credential Manager is unavailable. Check your Windows account.") from None

    def get(self, p, base):
        account = self._account(p, base)
        value = self._invoke("get_password", SERVICE, account)
        if value:
            return value
        old = self._invoke("get_password", LEGACY_SERVICE, account)
        if old:
            try:
                # Copy before deleting to avoid losing credentials.
                self._invoke("set_password", SERVICE, account, old)
                self._invoke("delete_password", LEGACY_SERVICE, account)
            except CredentialError:
                pass
        return old

    def save(self, p, base, value):
        if (not isinstance(value, str) or not value.strip() or not value.strip().isascii()
            or any(ord(c) <= 32 or ord(c) == 127 for c in value.strip())):
            raise CredentialError("Enter a valid API key.")
        account = self._account(p, base)
        self._invoke("set_password", SERVICE, account, value.strip())
        # Saving a new key must not leave a stale key under the old app name.
        try:
            if self._invoke("get_password", LEGACY_SERVICE, account):
                self._invoke("delete_password", LEGACY_SERVICE, account)
        except CredentialError:
            pass

    def delete(self, p, base):
        account = self._account(p, base)
        for service in (SERVICE, LEGACY_SERVICE):
            if self._invoke("get_password", service, account):
                self._invoke("delete_password", service, account)
