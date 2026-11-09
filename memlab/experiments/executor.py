"""E2E executor for the S5 runner.

`Runtime` is fail-closed: only explicit legacy/B0 configs may run (hardening
requirement).  R0-style module configs therefore need a different entry point that
knows it is running the module pipeline.  This executor builds an
:class:`~memlab.e2e.E2EPipeline` context directly; it never falls back to
``legacy_dynamic`` and never bypasses a *missing* implementation silently — a
missing registry entry raises during context construction and is recorded as an
error by the runner.

Offline mode uses deterministic local clients (hash embeddings + extractive
answers).  It is for interface/A-level screening when Ollama is unavailable; its
F1 is an extractive baseline, not an LLM answer, and is labelled in run metadata.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from memlab import cache as lab_cache
from memlab import config as lab_config
from memlab import e2e, ingest, legacy, maintenance, merge
from memlab.llm import EmbeddingClient, LLMClient

OFFLINE_MODEL = "offline-extractive"
_CONTEXT_LINE = re.compile(r"^\[([^\]]+)\] \(([^)]*turns=([^)]*))\) (.+)$", re.MULTILINE)
_AUDIT_INDEX = re.compile(r'"index":\s*(\d+)')


class OfflineLLM:
    """Deterministic stand-in used only when no model server is available."""

    model = OFFLINE_MODEL
    is_offline = True

    def __init__(self):
        self.calls = 0

    @property
    def effective_model(self) -> str:
        return OFFLINE_MODEL

    def fingerprint(self) -> str:
        return "sha256:" + hashlib.sha256(b"offline-extractive-v1").hexdigest()

    def generate(self, prompt: str, json_mode: bool = False, max_tokens: int | None = None):
        self.calls += 1
        if "temporal memory analyst" in prompt:
            return {"memories": []}
        if "Audit these proposed memory relations" in prompt:
            return {"accepted": [int(value) for value in _AUDIT_INDEX.findall(prompt)]}
        matches = _CONTEXT_LINE.findall(prompt)
        if not matches:
            return {"answer": "unknown", "citations": [], "refused": True}
        section = prompt.split("Superseded memories:", 1)[0]
        section_matches = _CONTEXT_LINE.findall(section) or matches
        _memory_id, _meta, turns, text = section_matches[0]
        citations = [turn.strip() for turn in turns.split(",") if turn.strip() and turn.strip() != "none"]
        return {"answer": text.strip(), "citations": citations[:1], "refused": False}

    def usage(self) -> dict[str, Any]:
        return {"calls": self.calls, "errors": 0, "tokens_in": None, "tokens_out": None,
                "tokens_known_calls": 0, "latency_ms": 0.0, "latency_mean_ms": None, "items": 0}


class HashingEmbedding:
    """Deterministic bag-of-characters embedding; not semantic, and labelled offline."""

    dimensions = 32
    effective_model = "offline-hash"

    def fingerprint(self) -> str:
        return "sha256:" + hashlib.sha256(b"offline-hash-embedding-v1").hexdigest()

    def embed(self, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for index, character in enumerate(str(text)):
                vector[(index * 31 + ord(character)) % self.dimensions] += 1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors

    def usage(self) -> dict[str, Any]:
        return {"calls": 0, "errors": 0, "tokens_in": None, "tokens_out": None,
                "tokens_known_calls": 0, "latency_ms": 0.0, "latency_mean_ms": None, "items": 0}


@dataclass
class E2EContext:
    config: lab_config.RunConfig
    llm: Any
    embedding: Any
    cache: Any
    prompts: dict[str, str]
    store: Any = None


def build_context(plan: Any, sample_id: str, *, offline: bool = False,
                  cache: Any | None = None, prompts: dict[str, str] | None = None) -> E2EContext:
    """Build a module context for one RunPlan.  Deliberately does not use Runtime."""
    config = lab_config.RunConfig.from_dict(plan.effective_config)
    environment = config.get("environment") or {}
    shared_cache = cache if cache is not None else lab_cache.ArtifactCache()
    ctx = E2EContext(
        config=config,
        llm=OfflineLLM() if offline else LLMClient.from_environment(environment.get("llm") or {}),
        embedding=HashingEmbedding() if offline else EmbeddingClient.from_environment(
            environment.get("embedding") or {}),
        cache=shared_cache,
        prompts=dict(legacy.PROMPTS if prompts is None else prompts),
    )
    ingested = ingest.build_store(sample_id, ctx)
    ctx.store = ingested.store
    return ctx


def retrieval_k(plan: Any, default: int = 15) -> int:
    """Read the per-plan retrieval budget; never hardcode the e2e k."""
    config = getattr(plan, "effective_config", None) or getattr(plan, "config", None) or {}
    value = lab_config.get_path(config, "retrieval.k", default) if hasattr(config, "get") else default
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def make_e2e_executor(*, offline: bool = False, cache: Any | None = None,
                      cache_root: str | Path | None = None, prompts: dict[str, str] | None = None):
    """Return a Runner-compatible executor using E2EPipeline."""
    shared_cache = cache if cache is not None else lab_cache.ArtifactCache(cache_root)
    built: dict[tuple[str, str, bool], tuple[E2EContext, e2e.E2EPipeline]] = {}

    def execute(plan: Any, question: Any) -> dict[str, Any]:
        key = (plan.config_hash, question.sample_id, offline)
        entry = built.get(key)
        if entry is None:
            ctx = build_context(plan, question.sample_id, offline=offline,
                                cache=shared_cache, prompts=prompts)
            entry = (ctx, e2e.E2EPipeline(ctx))
            built[key] = entry
        ctx, pipeline = entry
        gold = []
        try:
            from memwb import evaluation
            gold = evaluation.evidence_turns(question.qa)
        except Exception:
            pass
        result = pipeline.run(question.qa["question"], k=retrieval_k(plan), gold_turns=gold)
        final = result.merge.waterfall[-1] if result.merge.waterfall else {}
        turns = set()
        for unit in result.merge.units:
            turns |= merge.unit_turns(unit)
        facts = ctx.store.facts
        completeness = (sum(1 for unit in facts if all(
            key in unit.structured for key in ("fact", "temporal", "relation", "evidence"))) / len(facts)
                        if facts else 0.0)
        graph = ctx.store.ensure_graph(ctx.config.impl("graph.repr") or "state_slot")
        return {
            "answer": result.answer.answer,
            "retrieved_turns": sorted(turns),
            "latency_ms": result.latency_ms,
            "tokens": result.merge.tokens,
            "tokens_total": result.tokens,
            "ndcg": final.get("ndcg"),
            "context_precision": final.get("context_precision"),
            "redundancy": final.get("redundancy"),
            "candidates": len(result.merge.candidates),
            "citations": len(result.answer.citations),
            "refused": int(result.answer.refused),
            "store_units": len(ctx.store),
            "store_facts": len(facts),
            "store_turns": len(ctx.store.turns),
            "field_completeness": round(completeness, 4),
            "graph_nodes": len(graph.nodes),
            "graph_edges": graph.stats()["edges"],
            "plan_nodes": len(result.retrieval.plan.nodes),
            "channels": len(result.retrieval.by_channel),
            "valid_units": len(result.answer.state.valid),
            "superseded_units": len(result.answer.state.superseded),
            "conflict_pairs": len(result.answer.state.conflicts),
            "_meta": {
                "executor": "e2e",
                "offline": offline,
                "llm": OFFLINE_MODEL if offline else getattr(ctx.llm, "effective_model", None),
                "embedding": "offline-hash" if offline else getattr(ctx.embedding, "effective_model", None),
                "store_units": len(ctx.store),
                "fallbacks": list(result.merge.fallbacks),
            },
        }

    return execute


def make_k_executor(*, policy: str = "none", params: dict[str, Any] | None = None,
                    offline: bool = False, cache: Any | None = None):
    """K candidate executor: applies one maintenance action then reports health metrics."""
    action_cache: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    def execute(plan: Any, question: Any) -> dict[str, Any]:
        key = (plan.config_hash, question.sample_id, policy, str(sorted((params or {}).items())))
        if key not in action_cache:
            ctx = build_context(plan, question.sample_id, offline=offline, cache=cache)
            as_of = None
            moments = [unit.t_ingest.start for unit in ctx.store.units
                       if unit.t_ingest is not None and unit.t_ingest.start is not None]
            if moments:
                as_of = max(moments)
            removed = 0
            if policy == "consolidate":
                result = maintenance.consolidate(ctx.store, "dedupe", params=params)
                removed = len(result.removed)
            elif policy == "archive":
                result = maintenance.forget(ctx.store, "archive", params=params, as_of=as_of)
                removed = len(result.removed)
            elif policy == "ttl":
                result = maintenance.forget(ctx.store, "ttl", params=params, as_of=as_of)
                removed = len(result.removed)
            report = maintenance.scan(ctx.store, as_of=as_of)
            action_cache[key] = {
                "staleness": report.metrics.get("staleness"),
                "contradiction_rate": report.metrics.get("contradiction_rate"),
                "update_correctness": report.metrics.get("update_correctness"),
                "duplicates": len(report.duplicates),
                "removed": removed,
                "units": len(ctx.store),
                "_meta": {"executor": "k", "policy": policy, "offline": offline},
            }
        return action_cache[key]

    return execute
