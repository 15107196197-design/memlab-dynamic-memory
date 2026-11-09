"""Runtime: the object a stage receives as ``ctx``.

S1 wires the minimum: a validated config, the instrumented model clients, the
legacy method adapters behind the registry, and a manifest built from the same
identity.  Later sessions add cache, trace, budget and memory store to this object;
stages must keep taking them from ``ctx`` rather than reading ``os.environ``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from . import config as lab_config
from . import legacy
from .llm import EmbeddingClient, LLMClient
from .manifest import RunManifest, build_manifest
from .registry import build


class Runtime:
    """Binds one run configuration to model clients and implementations."""

    def __init__(self, config: lab_config.RunConfig | Mapping[str, Any], *,
                 llm: LLMClient | None = None,
                 embedding: EmbeddingClient | None = None,
                 prompts: Mapping[str, str] | None = None):
        if isinstance(config, lab_config.RunConfig):
            self.config = config
        else:
            self.config = lab_config.RunConfig.from_dict(config)
        environment = self.config.get("environment", {}) or {}
        self.llm = llm or LLMClient.from_environment(environment.get("llm") or {})
        self.embedding = embedding or EmbeddingClient.from_environment(environment.get("embedding") or {})
        self.prompts = dict(legacy.PROMPTS if prompts is None else prompts)

    @classmethod
    def load(cls, path: str | Path, **kwargs) -> "Runtime":
        return cls(lab_config.RunConfig.load(path), **kwargs)

    @property
    def method(self) -> str:
        return self.config.method

    def adapter(self, method: str | None = None):
        """Instantiate the configured (or requested) method adapter."""
        if method is None:
            return build(legacy.AXIS, self.config.method, self.config.method_params)
        return build(legacy.AXIS, method)

    def answer(self, sample_id: str, question: str, *, method: str | None = None,
               k: int | None = None, as_of: str | None = None,
               expand: int | None = None) -> dict[str, Any]:
        """Answer one question; the returned dict is the legacy pipeline output."""
        kwargs: dict[str, Any] = {}
        if k is not None:
            kwargs["k"] = k
        if as_of is not None:
            kwargs["as_of"] = as_of
        if expand is not None:
            kwargs["expand"] = expand
        return self.adapter(method).answer(sample_id, question, **kwargs)

    def manifest(self, *, run_id: str | None = None, created_at=None,
                 status: str = "created") -> RunManifest:
        """Manifest for this configuration and prompt set."""
        return build_manifest(self.config, prompts=self.prompts, run_id=run_id,
                              created_at=created_at, status=status)

    def usage(self) -> dict[str, Any]:
        """Token/latency totals for this runtime (both clients)."""
        return {"llm": self.llm.usage(), "embedding": self.embedding.usage()}
