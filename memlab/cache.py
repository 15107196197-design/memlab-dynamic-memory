"""Content-addressed artifact cache (docs/optimization/02-architecture 2.9.2).

The key is the hash of *everything that can change the artifact*::

    sha256(canonical_json({
        "stage": ..., "input": ..., "impl": ..., "params": ...,
        "prompt_hash": ..., "model_fingerprint": ..., "schema_version": ...,
    }))

so changing a prompt, a schema version, an implementation or a model never reuses
an old artifact.  That is the difference between an ablation and a cached lie.

Artifacts are JSON values stored under ``root/<first two hex>/<digest>.json`` and
written with a temporary file + rename, so an interrupted run cannot leave a
half-written artifact that looks like a cache hit.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

from . import config as lab_config

KEY_PREFIX = "sha256:"
DEFAULT_ROOT = lab_config.ROOT / "cache" / "memlab"
_MISSING = object()


class CacheError(RuntimeError):
    """The cache entry exists but cannot be read as an artifact."""


def make_key(stage: str, payload: Any, *, impl: str | None = None,
             params: Mapping[str, Any] | None = None, prompt_hash: str | None = None,
             model_fingerprint: str | None = None,
             schema_version: str | None = None) -> str:
    """Deterministic cache key for one stage artifact."""
    if not isinstance(stage, str) or not stage.strip():
        raise ValueError("cache stage must be a non-empty string")
    return lab_config.digest({
        "stage": stage,
        "input": payload,
        "impl": impl,
        "params": dict(params or {}),
        "prompt_hash": prompt_hash,
        "model_fingerprint": model_fingerprint,
        "schema_version": schema_version,
    })


class ArtifactCache:
    """A filesystem cache keyed by :func:`make_key`."""

    def __init__(self, root: str | Path | None = None, *, log: Callable[[dict[str, Any]], None] | None = None):
        self.root = Path(root) if root is not None else DEFAULT_ROOT
        self.hits = 0
        self.misses = 0
        self._log = log

    # ---- keys ---------------------------------------------------------
    def key(self, stage: str, payload: Any, **fields: Any) -> str:
        """``make_key`` bound to this cache (same signature minus ``stage``/``payload``)."""
        return make_key(stage, payload, **fields)

    def path_for(self, key: str) -> Path:
        if not isinstance(key, str) or not key.startswith(KEY_PREFIX):
            raise ValueError(f"cache key must start with {KEY_PREFIX!r}")
        digest = key[len(KEY_PREFIX):]
        if len(digest) != 64:
            raise ValueError("cache key must contain a 64-character sha256 digest")
        try:
            int(digest, 16)
        except ValueError as exc:
            raise ValueError("cache key digest must be hexadecimal") from exc
        return self.root / digest[:2] / f"{digest}.json"

    # ---- reads/writes -------------------------------------------------
    def has(self, key: str) -> bool:
        return self.path_for(key).is_file()

    def get(self, key: str, default: Any = None) -> Any:
        path = self.path_for(key)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._record(key, hit=False)
            return default
        except OSError as exc:
            raise CacheError(f"cannot read cache entry {path}: {exc}") from exc
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CacheError(f"corrupt cache entry {path}: {exc}") from exc
        self._record(key, hit=True)
        return value

    def put(self, key: str, value: Any) -> Path:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
        handle = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.stem[:8]}-", suffix=".tmp", delete=False,
        )
        temporary = Path(handle.name)
        try:
            with handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return path

    def get_or_compute(self, key: str, producer: Callable[[], Any]) -> Any:
        """Return the cached value, or compute it once and store it."""
        cached = self.get(key, _MISSING)
        if cached is not _MISSING:
            return cached
        value = producer()
        self.put(key, value)
        return value

    # ---- accounting ---------------------------------------------------
    def _record(self, key: str, *, hit: bool) -> None:
        if hit:
            self.hits += 1
        else:
            self.misses += 1
        if self._log is not None:
            self._log({"cache": "hit" if hit else "miss", "key": key})

    def stats(self) -> dict[str, Any]:
        lookups = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "lookups": lookups,
            "hit_rate": round(self.hits / lookups, 4) if lookups else None,
            "root": str(self.root),
        }
