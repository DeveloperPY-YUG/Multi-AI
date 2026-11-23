"""Validated provider profiles and non-secret preferences saved atomically."""

from __future__ import annotations

import copy
import ipaddress
import json
import math
import os
import re
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlsplit

# Compatibility constants also describe presets that users can add in the UI.
NAMES = {
    "groq": "Groq",
    "google": "Google Gemini",
    "anthropic": "Anthropic",
    "qwen": "Qwen",
    "xai": "xAI (Grok)",
    "lmstudio": "LM Studio",
    "ollama": "Ollama",
}
LOCAL = {"lmstudio", "ollama"}
BASES = {
    "groq": "https://api.groq.com/openai/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta",
    "anthropic": "https://api.anthropic.com/v1",
    "qwen": "",
    "xai": "https://api.x.ai/v1",
    "lmstudio": "http://127.0.0.1:1234/v1",
    "ollama": "http://127.0.0.1:11434",
}
PROTOCOLS = {"openai", "google", "anthropic", "ollama"}
PRESETS = {
    "groq": {"name": "Groq", "protocol": "openai", "local": False, "editable": False},
    "google": {"name": "Google Gemini", "protocol": "google", "local": False, "editable": False},
    "anthropic": {"name": "Anthropic", "protocol": "anthropic", "local": False, "editable": False},
    "qwen": {"name": "Qwen (Model Studio)", "protocol": "openai", "local": False, "editable": True},
    "xai": {"name": "xAI (Grok)", "protocol": "openai", "local": False, "editable": False},
    "lmstudio": {"name": "LM Studio", "protocol": "openai", "local": True, "editable": True},
    "ollama": {"name": "Ollama", "protocol": "ollama", "local": True, "editable": True},
}
ACTIVE_DEFAULTS = ("groq", "google", "anthropic", "qwen", "lmstudio", "ollama")


def preset(profile_id):
    return {"id": profile_id, **PRESETS[profile_id]}


DEFAULTS = {
    "scale": 100,
    "motion": True,
    "sidebar": "auto",
    "system": "You are a helpful assistant inside MULTI-AI, a desktop application made by YUG.",
    "temperature": None,
    "tokens": 4096,
    "timeout": 120,
    "defaultProvider": "anthropic",
    "defaultModel": "",
    "providers": [preset(p) for p in ACTIVE_DEFAULTS],
    "endpoints": dict(BASES),
    "hiddenModels": [],
    "models": [{"provider": "anthropic", "id": "claude-opus-4-6", "name": "Claude Opus 4.6"}],
}


def clean_text(value, maximum, label):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError(f"Enter a valid {label}.")
    return value.strip()


def provider_map(data):
    return {p["id"]: p for p in data["providers"]}


def validate_profile(profile):
    if not isinstance(profile, dict):
        raise ValueError("Invalid provider profile.")
    pid = profile.get("id")
    if not isinstance(pid, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", pid):
        raise ValueError("Invalid provider identifier.")
    name = clean_text(profile.get("name"), 80, "provider name")
    protocol = profile.get("protocol")
    local = profile.get("local")
    editable = profile.get("editable")
    if protocol not in PROTOCOLS or type(local) is not bool or type(editable) is not bool:
        raise ValueError("Unsupported provider configuration.")
    if local and protocol not in {"openai", "ollama"}:
        raise ValueError("Local connections must use OpenAI-compatible or Ollama APIs.")
    if protocol == "ollama" and not local:
        raise ValueError("Ollama needs a local connection.")
    if protocol in {"google", "anthropic"} and pid not in {"google", "anthropic"}:
        raise ValueError("Use the corresponding official preset for this API.")
    if pid in PRESETS:
        original = PRESETS[pid]
        if (protocol, local, editable) != (
            original["protocol"], original["local"], original["editable"]
        ):
            raise ValueError("The selected preset cannot change its API format.")
    return {"id": pid, "name": name, "protocol": protocol, "local": local, "editable": editable}


def model_entry(provider, identifier, name="", allowed=None):
    if provider not in (NAMES if allowed is None else allowed):
        raise ValueError("Choose an installed provider.")
    identifier = clean_text(identifier, 512, "model ID")
    if provider == "google":
        identifier = clean_text(identifier.removeprefix("models/"), 512, "Gemini model ID")
    return {"provider": provider, "id": identifier, "name": clean_text(name or identifier, 512, "model name")}


def endpoint(provider, value, profile=None):
    # Legacy two-argument validation is supported by the original test suite.
    if profile is None:
        if provider not in LOCAL | {"qwen"}:
            raise ValueError("This service has a fixed endpoint.")
        profile = preset(provider)
    if not profile["editable"]:
        raise ValueError("This service has a fixed endpoint.")
    value = clean_text(value, 2048, "base URL").rstrip("/")
    try:
        u = urlsplit(value)
        port = u.port
    except ValueError:
        raise ValueError("Enter a valid host and port.") from None
    if (
        not u.hostname or u.username is not None or u.password is not None
        or u.query or u.fragment or port == 0
        or any(c.isspace() or c in "\\%?#" for c in value)
        or any(x in {".", ".."} for x in u.path.split("/"))
        or (u.netloc.count(":") > 1 and not u.netloc.startswith("["))
    ):
        raise ValueError("Enter a base URL without credentials, query parameters or fragments.")
    if profile["local"]:
        try:
            loopback = ipaddress.ip_address(u.hostname).is_loopback
        except ValueError:
            loopback = u.hostname.lower() == "localhost"
        if not loopback or u.scheme not in {"http", "https"}:
            raise ValueError("Use localhost or a loopback IP for a local server.")
    elif u.scheme != "https":
        raise ValueError("Cloud APIs require an HTTPS base URL.")
    return value


def preferences(data):
    out = {}
    for key, low, high in [("scale", 80, 125), ("tokens", 1, 131072), ("timeout", 5, 1800)]:
        n = data[key]
        if type(n) is not int or not low <= n <= high:
            raise ValueError(f"{key.capitalize()} must be between {low} and {high}.")
        out[key] = n
    t = data["temperature"]
    if t is not None and (type(t) not in (int, float) or not math.isfinite(t) or not 0 <= t <= 1):
        raise ValueError("Temperature must be between 0 and 1 or left blank.")
    if (
        data["sidebar"] not in ("auto", "expanded", "collapsed")
        or type(data["motion"]) is not bool
        or not isinstance(data["defaultProvider"], str)
        or not isinstance(data["defaultModel"], str)
        or len(data["defaultModel"]) > 512
        or not isinstance(data["system"], str)
        or len(data["system"]) > 32000
    ):
        raise ValueError("Check the selected settings.")
    return out | {k: data[k] for k in ("temperature", "sidebar", "motion", "system", "defaultProvider", "defaultModel")}


class Config:
    def __init__(self, path: Path):
        self.path = path
        self.data = copy.deepcopy(DEFAULTS)
        self.warning = ""
        if path.exists():
            try:
                src = json.loads(path.read_text(encoding="utf-8"))
                cfg = self.data | preferences(self.data | src)
                rows = src.get("providers", cfg["providers"])
                if not isinstance(rows, list) or len(rows) > 100:
                    raise ValueError("Too many providers.")
                profiles = [validate_profile(p) for p in rows]
                if len({p["id"] for p in profiles}) != len(profiles):
                    raise ValueError("Duplicate providers.")
                profiles_by_id = {p["id"]: p for p in profiles}
                src_endpoints = src.get("endpoints", {})
                if not isinstance(src_endpoints, dict):
                    raise ValueError("Invalid endpoints.")
                bases = {}
                for p in profiles:
                    pid = p["id"]
                    default_base = BASES.get(pid, "")
                    value = src_endpoints.get(pid, default_base)
                    if not p["editable"]:
                        value = default_base
                    elif value:
                        value = endpoint(pid, value, p)
                    bases[pid] = value
                cfg["providers"] = profiles
                cfg["endpoints"] = bases
                hidden = src.get("hiddenModels", [])
                if not isinstance(hidden, list) or len(hidden) > 10000:
                    raise ValueError("Invalid hidden models")
                cfg["hiddenModels"] = [x for x in hidden if isinstance(x, list) and len(x) == 2 and all(isinstance(v, str) and len(v) <= 512 for v in x) and x[0] in profiles_by_id]
                cfg["models"] = [
                    model_entry(m["provider"], m["id"], m.get("name", ""), profiles_by_id)
                    for m in src.get("models", cfg["models"])
                    if isinstance(m, dict) and m.get("provider") in profiles_by_id
                ]
                if cfg["defaultProvider"] not in profiles_by_id:
                    cfg["defaultProvider"] = profiles[0]["id"] if profiles else ""
                    cfg["defaultModel"] = ""
                if cfg["system"] == "You are a helpful assistant inside MULTIAI, a desktop application made by YUG.":
                    cfg["system"] = DEFAULTS["system"]
                self.data = cfg
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                self.warning = "Saved preferences could not be read. Defaults are active."

    @property
    def registry(self):
        return provider_map(self.data)

    def add_provider(self, preset_id, label="", base=""):
        if len(self.data["providers"]) >= 100:
            raise ValueError("Maximum of 100 provider connections.")
        if preset_id in PRESETS:
            profile = preset(preset_id)
            pid = profile["id"]
            if pid in self.registry:
                raise ValueError("That provider is already added.")
            if label.strip():
                profile["name"] = clean_text(label, 80, "provider name")
            address = BASES[pid]
            if profile["editable"] and base.strip():
                address = endpoint(pid, base, profile)
        elif preset_id in {"custom-cloud", "custom-local"}:
            pid = "custom-" + uuid.uuid4().hex[:12]
            profile = validate_profile({
                "id": pid,
                "name": label,
                "protocol": "openai",
                "local": preset_id == "custom-local",
                "editable": True,
            })
            address = endpoint(pid, base, profile)
        else:
            raise ValueError("Choose a supported provider type.")
        updated = self.data["providers"] + [profile]
        self.update(
            providers=updated,
            endpoints=self.data["endpoints"] | {pid: address},
            defaultProvider=self.data["defaultProvider"] or pid,
        )
        return pid

    def remove_provider(self, pid):
        if pid not in self.registry:
            raise ValueError("Provider not found.")
        profiles = [p for p in self.data["providers"] if p["id"] != pid]
        endpoints = {k: v for k, v in self.data["endpoints"].items() if k != pid}
        models = [m for m in self.data["models"] if m["provider"] != pid]
        hidden = [x for x in self.data["hiddenModels"] if x[0] != pid]
        default_p = self.data["defaultProvider"]
        default_m = self.data["defaultModel"]
        if default_p == pid:
            default_p = profiles[0]["id"] if profiles else ""
            default_m = ""
        self.update(
            providers=profiles, endpoints=endpoints, models=models, hiddenModels=hidden,
            defaultProvider=default_p, defaultModel=default_m,
        )

    def update(self, **fields):
        data = self.data | fields
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=self.path.parent, delete=False, encoding="utf-8") as f:
            temp = Path(f.name)
        try:
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp, self.path)
            self.data = data
        finally:
            temp.unlink(missing_ok=True)
