"""Fail-closed guards for configurations the current runtime cannot execute.

S1/S2 only implement the legacy method adapters.  A config that selects R0's
modules (``meta_schema``, ``three_layer`` ...) must therefore *fail* instead of
silently falling back to ``legacy_dynamic``: a run labelled R0 that actually ran
B0 is worse than a run that refuses to start.

The guard is deliberately separate from ``runtime.py`` so S3 can add the call in
one line without merging a large runtime diff:

    from .guards import require_runnable
    ...
    require_runnable(self.config)

It is also usable by the experiment compiler before a run is scheduled.
"""
from __future__ import annotations

from collections.abc import Mapping

from . import config as lab_config


class UnimplementedPipeline(RuntimeError):
    """The config asks for modules this package version does not implement."""


LEGACY_METHOD_PREFIX = "legacy_"
LEGACY_PRESETS = frozenset({"B0", "LEGACY", "LEGACY_B0"})


def _preset(config: lab_config.RunConfig) -> str:
    value = config.preset
    return value.strip().upper() if isinstance(value, str) else ""


def is_legacy_config(config: lab_config.RunConfig | Mapping) -> bool:
    """True only when the config explicitly selects a legacy method/preset."""
    cfg = config if isinstance(config, lab_config.RunConfig) else lab_config.as_config(config)
    raw = cfg.data
    explicit = None
    for root in ("method", "pipeline"):
        block = raw.get(root)
        if isinstance(block, Mapping):
            explicit = block.get("impl")
            if explicit:
                break
    return (isinstance(explicit, str) and explicit.startswith(LEGACY_METHOD_PREFIX)) or _preset(cfg) in LEGACY_PRESETS


def requested_modules(config: lab_config.RunConfig | Mapping) -> dict[str, str]:
    """The module implementations named by the config, for error messages."""
    cfg = config if isinstance(config, lab_config.RunConfig) else lab_config.as_config(config)
    modules: dict[str, str] = {}
    for path in (
        "schema.impl", "graph.repr.impl", "graph.retrieval.impl", "planner.impl",
        "fusion.impl", "rerank.impl", "answer.impl",
    ):
        value = cfg.get(path)
        if isinstance(value, str):
            modules[path] = value
    return modules


def require_runnable(config: lab_config.RunConfig | Mapping) -> None:
    """Raise unless the config is an explicit legacy/B0 run.

    This is intentionally conservative: until the module pipeline registers its
    implementations, a non-legacy config must not run at all.
    """
    cfg = config if isinstance(config, lab_config.RunConfig) else lab_config.as_config(config)
    if is_legacy_config(cfg):
        return
    modules = requested_modules(cfg)
    detail = ", ".join(f"{key}={value}" for key, value in sorted(modules.items())) or "no module blocks"
    raise UnimplementedPipeline(
        "this config selects the module pipeline, but only legacy_* methods are implemented "
        f"in this version ({detail}). Use method.impl=legacy_* for B0, or wait for S3+."
    )
