"""W -> S -> R ingestion helpers.

``build_store`` takes a conversation that already has legacy extraction/state
artifacts, runs the W module (extract -> resolve -> audit -> apply), and builds the
requested graph representation.  No legacy metric or file is modified.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from memwb import dataset as legacy_dataset

from . import model
from .store import MemoryStore
from .write import WritePipeline, WriteResult


@dataclass
class IngestResult:
    store: MemoryStore
    write: WriteResult
    graph: str
    conversation: str

    @property
    def counts(self) -> dict[str, Any]:
        return {
            "conversation": self.conversation,
            "turns": len(self.store.turns),
            "facts": len(self.store.facts),
            "units": len(self.store.units),
            "relations": len(self.store.relations),
            "graph": self.graph,
            "write": self.write.counts,
        }

    def as_dict(self) -> dict[str, Any]:
        return {"counts": self.counts, "write_trace": list(self.write.trace)}


def _impl(ctx: Any, path: str, default: str) -> str:
    config = getattr(ctx, "config", None)
    value = config.impl(path) if config is not None and hasattr(config, "impl") else None
    return value or default


def _params(ctx: Any, path: str) -> dict[str, Any]:
    config = getattr(ctx, "config", None)
    return config.params(path) if config is not None and hasattr(config, "params") else {}


def build_store(sample: str | Mapping[str, Any], ctx: Any, *,
                extractor: str | None = None, resolver: str | None = None,
                auditor: str | None = None, graph: str | None = None,
                extractor_params: Mapping[str, Any] | None = None,
                resolver_params: Mapping[str, Any] | None = None,
                auditor_params: Mapping[str, Any] | None = None) -> IngestResult:
    """Build a ready-to-retrieve store for one conversation."""
    record = legacy_dataset.store().get(sample) if isinstance(sample, str) else sample
    view = model.from_sample(record)
    turns = [unit for unit in view.units if unit.kind == "turn"]

    extractor_name = extractor or _impl(ctx, "schema", "legacy_flat")
    resolver_name = resolver or _impl(ctx, "write.resolver", "append")
    auditor_name = auditor or _impl(ctx, "write.auditor", "none")

    pipeline = WritePipeline(
        extractor_name, resolver_name, auditor_name,
        extractor_params=_params(ctx, "schema") if extractor_params is None else extractor_params,
        resolver_params=_params(ctx, "write.resolver") if resolver_params is None else resolver_params,
        auditor_params=_params(ctx, "write.auditor") if auditor_params is None else auditor_params,
    )
    store = MemoryStore(turns)
    write = pipeline.write(turns, store, ctx)
    graph_name = graph or _impl(ctx, "graph.repr", "state_slot")
    if graph_name and graph_name != "none":
        store.ensure_graph(graph_name)
    return IngestResult(store=store, write=write, graph=graph_name, conversation=record["sample_id"])
