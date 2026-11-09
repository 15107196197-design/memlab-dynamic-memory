"""Runtime: the object a stage receives as ``ctx``.

S1 wired the config, model clients, legacy adapters and manifest.  S3 adds the
content-addressed artifact cache and the memory store, so W/S/R stages can take
everything from ``ctx`` instead of reading module globals or ``os.environ``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from . import config as lab_config
from . import legacy
from .cache import ArtifactCache
from .llm import EmbeddingClient, LLMClient
from .manifest import RunManifest, build_manifest
from .registry import build


class Runtime:
    """Binds one run configuration to model clients and implementations."""

    def __init__(self, config: lab_config.RunConfig | Mapping[str, Any], *,
                 llm: LLMClient | None = None,
                 embedding: EmbeddingClient | None = None,
                 prompts: Mapping[str, str] | None = None,
                 cache: ArtifactCache | None = None,
                 store: Any | None = None):
        if isinstance(config, lab_config.RunConfig):
            self.config = config
        else:
            self.config = lab_config.RunConfig.from_dict(config)
        environment = self.config.get("environment", {}) or {}
        self.llm = llm or LLMClient.from_environment(environment.get("llm") or {})
        self.embedding = embedding or EmbeddingClient.from_environment(environment.get("embedding") or {})
        self.prompts = dict(legacy.PROMPTS if prompts is None else prompts)
        self.cache = cache if cache is not None else ArtifactCache()
        self.store = store

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

    def attach_store(self, store: Any) -> Any:
        """Bind a built :class:`memlab.store.MemoryStore` for R stages."""
        self.store = store
        return store

    def build_store(self, sample_id: str, **kwargs):
        """Run W -> S for one conversation and bind the resulting store."""
        from .ingest import build_store

        result = build_store(sample_id, self, **kwargs)
        self.store = result.store
        return result

    def retrieve(self, query: str, *, k: int | None = None):
        """Run R against the bound store."""
        from .retrieve import RetrievalRunner

        return RetrievalRunner().run(query, self, k=k)
