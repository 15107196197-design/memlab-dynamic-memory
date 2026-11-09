"""Model provider adapters: Ollama and OpenAI-compatible HTTP.

The memlab client layer stays standard-library only.  ``LLMClient`` keeps using
``memwb.llm`` for Ollama (so B0 generation behaviour is untouched), and routes
other providers here.  Keys are read from environment variables only; they are
never stored in configs, manifests or fingerprints.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Mapping, Sequence


class ProviderError(RuntimeError):
    """A provider is misconfigured or returned an unusable response."""


DEFAULT_BASE_URLS = {
    "deepseek": "https://api.deepseek.com/v1",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
}
DEFAULT_KEY_ENVS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "dashscope": "DASHSCOPE_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def _provider(environment: Mapping[str, Any]) -> str:
    return str(environment.get("provider") or "ollama").strip().lower()


def _base_url(environment: Mapping[str, Any], provider: str) -> str:
    url = str(environment.get("base_url") or "").strip()
    if not url:
        url = DEFAULT_BASE_URLS.get(provider, "")
    if not url:
        raise ProviderError(
            f"provider={provider!r} needs environment.llm.base_url (e.g. https://api.deepseek.com/v1)"
        )
    return url.rstrip("/")


def _key_env(environment: Mapping[str, Any], provider: str) -> str:
    return str(environment.get("api_key_env") or DEFAULT_KEY_ENVS.get(provider, "OPENAI_API_KEY")).strip()


def api_key(environment: Mapping[str, Any], provider: str | None = None) -> str:
    provider = provider or _provider(environment)
    name = _key_env(environment, provider)
    value = os.environ.get(name)
    if not value:
        raise ProviderError(
            f"provider={provider!r} requires environment variable {name}; "
            "set it in the shell, never in the run config"
        )
    return value


def _request_json(url: str, body: Mapping[str, Any] | None, headers: Mapping[str, str],
                  timeout: float = 120.0) -> dict[str, Any]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers=dict(headers),
                                     method="POST" if data is not None else "GET")
    last: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
                if not isinstance(payload, dict):
                    raise ProviderError(f"provider returned non-object JSON from {url}")
                return payload
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                last = ProviderError(f"provider HTTP {exc.code}: {detail}")
                time.sleep(1.0 + attempt)
                continue
            raise ProviderError(f"provider HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last = ProviderError(f"provider connection failed: {exc}")
            if attempt < 2:
                time.sleep(1.0 + attempt)
                continue
            raise last from exc
    raise last or ProviderError("provider request failed")


def _content(payload: Mapping[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError(f"provider response has no choices[0].message.content: {payload}") from exc
    if isinstance(content, list):
        content = "".join(str(part.get("text", "")) if isinstance(part, Mapping) else str(part)
                          for part in content)
    if not isinstance(content, str):
        raise ProviderError(f"provider content is not text: {type(content).__name__}")
    return content


def _parse_json(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise ProviderError("provider returned invalid JSON") from None


def chat(environment: Mapping[str, Any], prompt: str, *, json_mode: bool = False,
         max_tokens: int | None = None, timeout: float | None = None) -> tuple[Any, dict[str, int]]:
    """Call an OpenAI-compatible chat endpoint; returns (content, usage)."""
    provider = _provider(environment)
    if provider not in ("openai_compatible", "openai", "deepseek", "dashscope", "qwen", "openrouter"):
        raise ProviderError(f"unsupported API provider: {provider!r}")
    base = _base_url(environment, provider)
    key = api_key(environment, provider)
    model = str(environment.get("model") or "").strip()
    if not model:
        raise ProviderError("environment.llm.model is required")
    temperature = environment.get("temperature", 0.0)
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": float(temperature if temperature is not None else 0.0),
        "stream": False,
    }
    if max_tokens:
        body["max_tokens"] = int(max_tokens)
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    try:
        payload = _request_json(f"{base}/chat/completions", body, headers,
                                timeout=float(timeout or environment.get("timeout") or 120))
    except ProviderError as exc:
        # Some OpenAI-compatible servers reject response_format; retry once without it.
        if json_mode and "response_format" in str(exc).lower():
            body.pop("response_format", None)
            payload = _request_json(f"{base}/chat/completions", body, headers,
                                    timeout=float(timeout or environment.get("timeout") or 120))
        else:
            raise
    text = _content(payload)
    usage_raw = payload.get("usage") if isinstance(payload.get("usage"), Mapping) else {}
    usage = {
        "tokens_in": int(usage_raw.get("prompt_tokens", usage_raw.get("input_tokens", 0)) or 0),
        "tokens_out": int(usage_raw.get("completion_tokens", usage_raw.get("output_tokens", 0)) or 0),
    }
    return (_parse_json(text) if json_mode else text), usage


def embed(environment: Mapping[str, Any], texts: Sequence[str], *, timeout: float | None = None) -> tuple[list[list[float]], dict[str, int]]:
    provider = _provider(environment)
    if provider not in ("openai_compatible", "openai", "deepseek", "dashscope", "qwen", "openrouter"):
        raise ProviderError(f"unsupported API embedding provider: {provider!r}")
    base = _base_url(environment, provider)
    key = api_key(environment, provider)
    model = str(environment.get("model") or "").strip()
    if not model:
        raise ProviderError("environment.embedding.model is required")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    payload = _request_json(f"{base}/embeddings", {"model": model, "input": list(texts)}, headers,
                            timeout=float(timeout or environment.get("timeout") or 120))
    try:
        vectors = [list(map(float, item["embedding"])) for item in payload["data"]]
    except (KeyError, TypeError, ValueError) as exc:
        raise ProviderError("provider embedding response has no data[].embedding") from exc
    usage_raw = payload.get("usage") if isinstance(payload.get("usage"), Mapping) else {}
    usage = {"tokens_in": int(usage_raw.get("prompt_tokens", 0) or 0), "tokens_out": 0}
    return vectors, usage


def preflight(environment: Mapping[str, Any], *, timeout: float = 8.0) -> dict[str, Any]:
    """Cheap configuration/endpoint check; does not generate tokens when avoidable."""
    provider = _provider(environment)
    model = str(environment.get("model") or "").strip()
    result: dict[str, Any] = {"provider": provider, "model": model}
    if provider == "ollama":
        from memwb import config as legacy_config

        base = str(environment.get("base_url") or legacy_config.ollama_url()).rstrip("/")
        try:
            payload = _request_json(f"{base}/api/tags", None, {}, timeout=timeout)
        except ProviderError as exc:
            raise ProviderError(f"Ollama is not reachable at {base}: {exc}") from exc
        names = [str(item.get("name", "")) for item in payload.get("models", [])]
        if model and not any(name == model or name.startswith(model + ":") for name in names):
            raise ProviderError(
                f"Ollama is up at {base}, but model {model!r} is not pulled; "
                f"run: ollama pull {model}"
            )
        result.update({"base_url": base, "models": names[:10], "ready": True})
        return result
    base = _base_url(environment, provider)
    key = api_key(environment, provider)
    result.update({"base_url": base, "api_key_env": _key_env(environment, provider), "has_key": bool(key)})
    headers = {"Authorization": f"Bearer {key}"}
    try:
        payload = _request_json(f"{base}/models", None, headers, timeout=timeout)
        result["models_endpoint"] = "ok"
        result["models"] = [str(item.get("id")) for item in payload.get("data", [])][:10]
    except ProviderError as exc:
        # Some compatible servers do not expose /models; a valid key/base URL is
        # still useful, so report the limitation instead of pretending a model run.
        result["models_endpoint"] = f"unavailable: {str(exc)[:200]}"
    result["ready"] = bool(key and base and model)
    return result
