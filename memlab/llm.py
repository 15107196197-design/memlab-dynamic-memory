"""Instrumented wrappers around :mod:`memwb.llm`.

The legacy client stays the single source of truth for request bodies, determinism
options and error handling.  These wrappers add only what experiments need:

* ``fingerprint()`` - a stable model identity for manifests and cache keys;
* a per-call record with latency and token usage, read from the Ollama response
  without touching ``memwb.llm``.

Generation behaviour is unchanged: the wrapper calls ``memwb.llm.generate`` with
the same arguments and passes its return value through untouched.  Token counts are
captured by delegating through a thin recording proxy over ``memwb.llm.post`` while
one call is in flight; if the underlying client is mocked, the counts are simply
``None`` instead of being invented.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from memwb import config as legacy_config
from memwb import llm as legacy_llm

from . import config as lab_config

_CAPTURE_LOCK = threading.Lock()


@dataclass(frozen=True)
class CallRecord:
    """One model call, as written to a trace or a run manifest."""

    kind: str  # "generate" | "embed"
    model: str
    latency_ms: float
    prompt_chars: int | None = None
    response_chars: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    items: int | None = None  # number of texts for an embedding call
    retries: int = 0
    error: str | None = None


def _block(provider: str | None, model: str | None, temperature: float | None,
           context: int | None, options: Mapping[str, Any] | None, digest: str | None) -> dict[str, Any]:
    return {
        "provider": provider or "ollama",
        "model": model or legacy_config.answer_model(),
        "temperature": temperature,
        "context": context,
        "options": dict(options or {}),
        "digest": digest,
    }


def fingerprint_environment(environment: Mapping[str, Any] | None) -> str:
    """Model identity of an ``environment`` block, for the run manifest."""
    env = environment or {}
    llm_block = env.get("llm") if isinstance(env.get("llm"), Mapping) else {}
    embedding_block = env.get("embedding") if isinstance(env.get("embedding"), Mapping) else {}
    return lab_config.digest({
        "llm": _block(llm_block.get("provider"), llm_block.get("model"), llm_block.get("temperature"),
                      llm_block.get("context"), llm_block.get("options"), llm_block.get("digest")),
        "embedding": {
            "provider": embedding_block.get("provider") or "ollama",
            "model": embedding_block.get("model") or legacy_config.embed_model(),
            "options": dict(embedding_block.get("options") or {}),
            "digest": embedding_block.get("digest"),
        },
    })


def _size(value: Any) -> int | None:
    if isinstance(value, str):
        return len(value)
    if value is None:
        return None
    try:
        return len(lab_config.canonical_json(value))
    except TypeError:
        return None


@contextmanager
def _recording_post(usage: dict[str, int]):
    """Temporarily proxy ``memwb.llm.post`` to read token counts from the response."""
    original = legacy_llm.post

    def post(path, body, timeout=900, base=None):
        payload = original(path, body, timeout=timeout, base=base)
        if isinstance(payload, Mapping):
            usage["calls"] += 1
            for source, target in (("prompt_eval_count", "tokens_in"), ("eval_count", "tokens_out")):
                value = payload.get(source)
                if isinstance(value, int) and not isinstance(value, bool):
                    usage[target] = usage.get(target, 0) + value
        return payload

    with _CAPTURE_LOCK:
        legacy_llm.post = post
        try:
            yield
        finally:
            legacy_llm.post = original


class LLMClient:
    """Chat client with fingerprinting and per-call accounting."""

    def __init__(self, model: str | None = None, *, provider: str = "ollama", temperature: float = 0.0,
                 context: int | None = None, options: Mapping[str, Any] | None = None,
                 digest: str | None = None):
        self.model = model
        self.provider = provider
        self.temperature = temperature
        self.context = context
        self.options = dict(options or {})
        self.digest = digest
        self.calls: list[CallRecord] = []

    @classmethod
    def from_environment(cls, environment: Mapping[str, Any] | None) -> "LLMClient":
        block = environment or {}
        return cls(
            model=block.get("model"),
            provider=block.get("provider", "ollama"),
            temperature=block.get("temperature", 0.0),
            context=block.get("context"),
            options=block.get("options"),
            digest=block.get("digest"),
        )

    @property
    def effective_model(self) -> str:
        return self.model or legacy_config.answer_model()

    def fingerprint(self) -> str:
        return lab_config.digest({"llm": _block(
            self.provider, self.effective_model, self.temperature, self.context, self.options, self.digest,
        )})

    def generate(self, prompt: str, json_mode: bool = False, max_tokens: int | None = None):
        """Same contract as ``memwb.llm.generate``, plus a recorded call."""
        started = time.perf_counter()
        usage: dict[str, int] = {"calls": 0}
        text: Any = None
        error: str | None = None
        try:
            with _recording_post(usage):
                text = legacy_llm.generate(
                    prompt, json_mode=json_mode, model=self.model, max_tokens=max_tokens,
                    temperature=self.temperature, num_ctx=self.context, options=self.options,
                )
            return text
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self.calls.append(CallRecord(
                kind="generate",
                model=self.effective_model,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                prompt_chars=len(prompt),
                response_chars=_size(text),
                tokens_in=usage.get("tokens_in"),
                tokens_out=usage.get("tokens_out"),
                retries=0,
                error=error,
            ))

    def usage(self) -> dict[str, Any]:
        return _summarize(self.calls)


class EmbeddingClient:
    """Embedding client with fingerprinting and per-call accounting."""

    def __init__(self, model: str | None = None, *, provider: str = "ollama",
                 options: Mapping[str, Any] | None = None, digest: str | None = None):
        self.model = model
        self.provider = provider
        self.options = dict(options or {})
        self.digest = digest
        self.calls: list[CallRecord] = []

    @classmethod
    def from_environment(cls, environment: Mapping[str, Any] | None) -> "EmbeddingClient":
        block = environment or {}
        return cls(
            model=block.get("model"),
            provider=block.get("provider", "ollama"),
            options=block.get("options"),
            digest=block.get("digest"),
        )

    @property
    def effective_model(self) -> str:
        return self.model or legacy_config.embed_model()

    def fingerprint(self) -> str:
        return lab_config.digest({"embedding": {
            "provider": self.provider,
            "model": self.effective_model,
            "options": self.options,
            "digest": self.digest,
        }})

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        started = time.perf_counter()
        error: str | None = None
        vectors: list[list[float]] | None = None
        try:
            vectors = legacy_llm.embed(list(texts))
            return vectors
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self.calls.append(CallRecord(
                kind="embed",
                model=self.effective_model,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                prompt_chars=sum(len(text) for text in texts),
                response_chars=None,
                items=len(texts),
                error=error,
            ))

    def usage(self) -> dict[str, Any]:
        return _summarize(self.calls)


def _summarize(calls: Sequence[CallRecord]) -> dict[str, Any]:
    known_in = [c.tokens_in for c in calls if c.tokens_in is not None]
    known_out = [c.tokens_out for c in calls if c.tokens_out is not None]
    latencies = [c.latency_ms for c in calls]
    return {
        "calls": len(calls),
        "errors": sum(1 for c in calls if c.error),
        "tokens_in": sum(known_in) if known_in else None,
        "tokens_out": sum(known_out) if known_out else None,
        "tokens_known_calls": len(known_in),
        "latency_ms": round(sum(latencies), 3) if latencies else 0.0,
        "latency_mean_ms": round(sum(latencies) / len(latencies), 3) if latencies else None,
        "items": sum(c.items or 0 for c in calls),
    }
