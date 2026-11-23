"""Provider-specific discovery, request formatting and incremental response parsing."""

from __future__ import annotations

import json
from urllib.parse import quote

import httpx

from .config import LOCAL, model_entry


class ProviderError(Exception):
    pass


def headers(p, key, protocol=None, local=None):
    protocol = protocol or p
    local = (p in LOCAL) if local is None else local
    if protocol == "google":
        return {"x-goog-api-key": key}
    if protocol == "anthropic":
        return {"x-api-key": key, "anthropic-version": "2023-06-01"}
    return {} if local else {"Authorization": "Bearer " + key}


def error_message(status, detail="", discovery=False):
    detail = str(detail).lower()
    if (
        status in (401, 403)
        or "invalid_api_key" in detail
        or "api_key_invalid" in detail
        or "api key not valid" in detail
        or "authentication_error" in detail
    ):
        return (
            "Authentication failed. Please check your API key and access permissions."
        )
    if status == 429 or "rate_limit" in detail:
        return "Rate limit reached. Please try again later."
    if discovery and status in (404, 405, 501):
        return "Model discovery is unavailable. Check the base URL or add a model ID manually."
    if status == 404 or (
        "model" in detail
        and any(s in detail for s in ("not found", "does not exist", "model_not_found"))
    ):
        return "This model is unavailable. Check the model ID."
    if status == 402:
        return "Check the available credit on your provider account."
    if status in (408, 504):
        return "The request timed out. Please try again."
    if status >= 500 or "overloaded" in detail:
        return "The provider is temporarily unavailable. Please try again."
    return "The provider rejected the request. Check the endpoint, model ID, token limit and sampling settings."


async def check(response: httpx.Response, discovery=False):
    if not response.is_success:
        raw = await response.aread()
        raise ProviderError(error_message(response.status_code, raw[:8192], discovery))


async def discover(client: httpx.AsyncClient, p, base, auth, protocol=None):
    protocol = protocol or p
    path = "/api/tags" if protocol == "ollama" else "/models"
    params, seen, result = {}, set(), {}
    while True:
        response = await client.get(base + path, headers=auth, params=params)
        await check(response, discovery=True)
        page = response.json()
        field = "models" if protocol in {"google", "ollama"} else "data"
        entries = page.get(field)
        if not isinstance(entries, list):
            raise ProviderError("Unexpected model list. Check the API base URL.")
        for item in entries:
            if protocol == "google" and "generateContent" not in item.get(
                "supportedGenerationMethods", []
            ):
                continue
            mid = item.get("name" if protocol in {"google", "ollama"} else "id")
            if mid:
                entry = model_entry(
                    p, mid, item.get("displayName") or item.get("display_name") or "", {p: True}
                )
                result[entry["id"]] = entry
        token = (
            page.get("nextPageToken")
            if protocol == "google"
            else page.get("last_id")
            if protocol == "anthropic" and page.get("has_more")
            else None
        )
        if not token:
            return list(result.values())
        if token in seen:
            raise ProviderError("The provider repeated a page of models.")
        seen.add(token)
        params = {"pageToken" if protocol == "google" else "after_id": token}


def request_body(p, mid, messages, cfg, protocol=None):
    protocol = protocol or p
    system = cfg["system"]
    history = [m for m in messages if m["role"] != "system"]
    system = "\n\n".join(
        filter(
            None, [system, *(m["content"] for m in messages if m["role"] == "system")]
        )
    )
    temperature = (
        {} if cfg["temperature"] is None else {"temperature": cfg["temperature"]}
    )
    if protocol == "google":
        body = {
            "contents": [
                {
                    "role": "model" if m["role"] == "assistant" else "user",
                    "parts": [{"text": m["content"]}],
                }
                for m in history
            ],
            "generationConfig": {"maxOutputTokens": cfg["tokens"], **temperature},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        return "/models/" + quote(mid, safe="") + ":streamGenerateContent?alt=sse", body
    if protocol == "anthropic":
        body = {
            "model": mid,
            "messages": history,
            "stream": True,
            "max_tokens": cfg["tokens"],
        }
        if system:
            body["system"] = system
        # Sampling overrides are unsupported on newer Claude models.
        if mid.startswith(
            (
                "claude-3",
                "claude-opus-4-6",
                "claude-sonnet-4-6",
                "claude-sonnet-4-5",
                "claude-haiku-4-5",
                "claude-opus-4-5",
            )
        ):
            body.update(temperature)
        return "/messages", body
    normalized = ([{"role": "system", "content": system}] if system else []) + history
    body = {"model": mid, "messages": normalized, "stream": True}
    if protocol == "ollama":
        body["options"] = {"num_predict": cfg["tokens"], **temperature}
        return "/api/chat", body
    return "/chat/completions", body | {"max_tokens": cfg["tokens"], **temperature}


async def payloads(response, ndjson):
    lines = []
    async for line in response.aiter_lines():
        if ndjson:
            if line.strip():
                yield line
        elif line.startswith("data:"):
            lines.append(line[5:].removeprefix(" "))
        elif not line and lines:
            yield "\n".join(lines)
            lines.clear()
    if lines:
        yield "\n".join(lines)


async def stream(client: httpx.AsyncClient, p, base, auth, mid, messages, cfg, protocol=None):
    protocol = protocol or p
    path, body = request_body(p, mid, messages, cfg, protocol)
    done = False
    async with client.stream("POST", base + path, headers=auth, json=body) as response:
        await check(response)
        async for raw in payloads(response, protocol == "ollama"):
            if raw == "[DONE]":
                done = True
                break
            item = json.loads(raw)
            if item.get("error"):
                err = item["error"]
                code = err.get("code", 400) if isinstance(err, dict) else 400
                raise ProviderError(
                    error_message(code if isinstance(code, int) else 400, err)
                )
            if protocol == "google":
                choices = item.get("candidates") or [{}]
                c = choices[0]
                reason = c.get("finishReason")
                if item.get("promptFeedback", {}).get("blockReason") or reason in {
                    "SAFETY",
                    "BLOCKLIST",
                    "PROHIBITED_CONTENT",
                    "RECITATION",
                }:
                    raise ProviderError("The provider blocked this response.")
                chunk = "".join(
                    s.get("text", "")
                    for s in c.get("content", {}).get("parts", [])
                    if not s.get("thought")
                )
                done |= bool(reason)
            elif protocol == "anthropic":
                delta = item.get("delta", {})
                chunk = (
                    delta.get("text", "") if delta.get("type") == "text_delta" else ""
                )
                done |= item.get("type") == "message_stop"
            elif protocol == "ollama":
                chunk = item.get("message", {}).get("content", "")
                done |= bool(item.get("done"))
            else:
                c = (item.get("choices") or [{}])[0]
                chunk = c.get("delta", {}).get("content") or ""
                done |= bool(c.get("finish_reason"))
            if chunk:
                yield chunk
        if not done:
            raise ProviderError(
                "The response ended unexpectedly. Retry to generate it again."
            )
