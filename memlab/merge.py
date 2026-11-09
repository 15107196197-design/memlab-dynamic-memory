"""M module: fusion, reranking and post-processing with a stage waterfall.

Input is the S3 :class:`~memlab.retrieve.RetrievalResult` (per-channel rankings are
preserved in ``by_channel``); output is a ranked, deduplicated and optionally
compressed context.  Every stage records the same metrics before/after
(``recall``, ``nDCG``, ``context_precision``, ``redundancy``, ``tokens``), which is
what makes "where did the gain disappear?" answerable.

Implementations live on separate registry axes so E1 can swap one stage at a time:
``fusion``, ``rerank``, ``post.filter``, ``post.mmr``, ``post.decay``,
``post.compress``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from . import model
from .contracts import Candidate, MemoryUnit
from .registry import UnknownImplementation
from .registry import build as build_impl
from .registry import register
from .tokens import estimate_tokens
from .trace import Trace
from .write import Parametrised, fact_fields

AXIS_FUSION = "fusion"
AXIS_RERANK = "rerank"
AXIS_FILTER = "post.filter"
AXIS_MMR = "post.mmr"
AXIS_DECAY = "post.decay"
AXIS_COMPRESS = "post.compress"

DEFAULT_ORDER = ("fusion", "rerank", "filter", "mmr", "decay", "compress")


# ---- metrics -----------------------------------------------------------

def unit_turns(unit: MemoryUnit) -> set[str]:
    turns: set[str] = set()
    if unit.kind == "turn" and unit.structured.get("turn"):
        turns.add(str(unit.structured["turn"]))
    turns.update(span.turn_id for span in unit.evidence)
    return turns


def candidate_units(store: Any, candidates: Sequence[Candidate]) -> list[MemoryUnit]:
    units = []
    for candidate in candidates:
        unit = store.get(candidate.memory_id)
        if unit is not None:
            units.append(unit)
    return units


def recalled_turns(store: Any, candidates: Sequence[Candidate]) -> set[str]:
    turns: set[str] = set()
    for unit in candidate_units(store, candidates):
        turns |= unit_turns(unit)
    return turns


def recall_at_k(store: Any, candidates: Sequence[Candidate], gold_turns: Sequence[str]) -> float | None:
    gold = {str(turn) for turn in gold_turns}
    if not gold:
        return None
    return round(len(gold & recalled_turns(store, candidates)) / len(gold), 4)


def ndcg_at_k(store: Any, candidates: Sequence[Candidate], gold_turns: Sequence[str]) -> float | None:
    gold = {str(turn) for turn in gold_turns}
    if not gold or not candidates:
        return None
    gains = []
    for unit in candidate_units(store, candidates):
        gains.append(1.0 if gold & unit_turns(unit) else 0.0)
    dcg = sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))
    relevant = int(sum(gains))
    if not relevant:
        return 0.0
    ideal = sum(1.0 / math.log2(index + 2) for index in range(relevant))
    return round(dcg / ideal, 4) if ideal else None


def context_precision(store: Any, candidates: Sequence[Candidate], gold_turns: Sequence[str]) -> float | None:
    gold = {str(turn) for turn in gold_turns}
    if not gold or not candidates:
        return None
    relevant = sum(1 for unit in candidate_units(store, candidates) if gold & unit_turns(unit))
    return round(relevant / len(candidates), 4)


def redundancy(units: Sequence[MemoryUnit]) -> float:
    if len(units) < 2:
        return 0.0
    from memwb import retrieval as legacy_retrieval

    token_sets = [set(legacy_retrieval.tokens(unit.text)) for unit in units]
    pairs, total = 0, 0.0
    for left in range(len(token_sets)):
        for right in range(left + 1, len(token_sets)):
            union = token_sets[left] | token_sets[right]
            total += len(token_sets[left] & token_sets[right]) / len(union) if union else 1.0
            pairs += 1
    return round(total / pairs, 4) if pairs else 0.0


def context_tokens(units: Sequence[MemoryUnit]) -> int:
    return sum(estimate_tokens(unit.text) for unit in units)


def stage_metrics(store: Any, candidates: Sequence[Candidate],
                  gold_turns: Sequence[str] | None) -> dict[str, Any]:
    units = candidate_units(store, candidates)
    gold = list(gold_turns or [])
    return {
        "candidates": len(candidates),
        "tokens": context_tokens(units),
        "recall": recall_at_k(store, candidates, gold) if gold else None,
        "ndcg": ndcg_at_k(store, candidates, gold) if gold else None,
        "context_precision": context_precision(store, candidates, gold) if gold else None,
        "redundancy": redundancy(units),
    }


# ---- fusion ------------------------------------------------------------

def _clone(candidate: Candidate, channel: str = "fusion") -> Candidate:
    return Candidate(
        memory_id=candidate.memory_id, channel=channel, rank=0,
        raw_score=candidate.raw_score, score=None,
        stage_scores=dict(candidate.stage_scores),
        provenance={**candidate.provenance, "channels": [candidate.channel]},
    )


def _merge_provenance(target: Candidate, source: Candidate) -> None:
    channels = target.provenance.setdefault("channels", [])
    if source.channel not in channels:
        channels.append(source.channel)
    target.stage_scores.update({key: value for key, value in source.stage_scores.items()
                                if key not in target.stage_scores})


class Fusion(Parametrised):
    axis = AXIS_FUSION
    name = ""

    def fuse(self, channels: Mapping[str, Sequence[Candidate]], frame: Any, ctx: Any) -> list[Candidate]:
        raise NotImplementedError


@register(AXIS_FUSION, "single_channel")
class SingleChannelFusion(Fusion):
    params_allowed = frozenset({"channel"})

    def fuse(self, channels, frame, ctx):
        name = self.params.get("channel")
        if name not in channels:
            name = next(iter(channels), None)
        if name is None:
            return []
        output = []
        for rank, candidate in enumerate(channels[name], 1):
            cloned = _clone(candidate)
            cloned.rank, cloned.score = rank, candidate.score
            output.append(cloned)
        return output


@register(AXIS_FUSION, "rrf")
class RRFFusion(Fusion):
    params_allowed = frozenset({"rrf_k", "k"})

    def fuse(self, channels, frame, ctx):
        constant = int(self.params.get("rrf_k", self.params.get("k", 60)) or 60)
        scores: dict[str, float] = {}
        lookup: dict[str, Candidate] = {}
        for ranking in channels.values():
            for rank, candidate in enumerate(ranking, 1):
                memory_id = candidate.memory_id
                scores[memory_id] = scores.get(memory_id, 0.0) + 1.0 / (constant + rank)
                if memory_id in lookup:
                    _merge_provenance(lookup[memory_id], candidate)
                else:
                    lookup[memory_id] = _clone(candidate)
        output = []
        for rank, memory_id in enumerate(sorted(scores, key=lambda item: (-scores[item], item)), 1):
            candidate = lookup[memory_id]
            candidate.rank, candidate.score = rank, scores[memory_id]
            candidate.stage_scores["fusion"] = scores[memory_id]
            output.append(candidate)
        return output


@register(AXIS_FUSION, "weighted_rrf")
class WeightedRRFFusion(Fusion):
    params_allowed = frozenset({"rrf_k", "weights", "k"})

    def fuse(self, channels, frame, ctx):
        constant = int(self.params.get("rrf_k", self.params.get("k", 60)) or 60)
        weights = self.params.get("weights") or {}
        scores: dict[str, float] = {}
        lookup: dict[str, Candidate] = {}
        for name, ranking in channels.items():
            weight = float(weights.get(name, 1.0))
            for rank, candidate in enumerate(ranking, 1):
                memory_id = candidate.memory_id
                scores[memory_id] = scores.get(memory_id, 0.0) + weight / (constant + rank)
                if memory_id in lookup:
                    _merge_provenance(lookup[memory_id], candidate)
                else:
                    lookup[memory_id] = _clone(candidate)
        output = []
        for rank, memory_id in enumerate(sorted(scores, key=lambda item: (-scores[item], item)), 1):
            candidate = lookup[memory_id]
            candidate.rank, candidate.score = rank, scores[memory_id]
            candidate.stage_scores["fusion"] = scores[memory_id]
            output.append(candidate)
        return output


@register(AXIS_FUSION, "linear")
class LinearFusion(Fusion):
    params_allowed = frozenset({"alpha", "weights"})

    def fuse(self, channels, frame, ctx):
        weights = dict(self.params.get("weights") or {})
        alpha = float(self.params.get("alpha", 0.5))
        if not weights:
            names = list(channels)
            weights = {name: (alpha if index == 0 else 1.0 - alpha) / max(1, len(names) - 1)
                       for index, name in enumerate(names)}
        scores: dict[str, float] = {}
        lookup: dict[str, Candidate] = {}
        for name, ranking in channels.items():
            if not ranking:
                continue
            values = [candidate.score or 0.0 for candidate in ranking]
            low, high = min(values), max(values)
            for rank, candidate in enumerate(ranking, 1):
                normalized = ((candidate.score or 0.0) - low) / (high - low) if high > low else 1.0 / rank
                scores[candidate.memory_id] = scores.get(candidate.memory_id, 0.0) + weights.get(name, 1.0) * normalized
                if candidate.memory_id not in lookup:
                    lookup[candidate.memory_id] = _clone(candidate)
                else:
                    _merge_provenance(lookup[candidate.memory_id], candidate)
        output = []
        for rank, memory_id in enumerate(sorted(scores, key=lambda item: (-scores[item], item)), 1):
            candidate = lookup[memory_id]
            candidate.rank, candidate.score = rank, scores[memory_id]
            candidate.stage_scores["fusion"] = scores[memory_id]
            output.append(candidate)
        return output


@register(AXIS_FUSION, "query_adaptive_weights")
class QueryAdaptiveFusion(Fusion):
    params_allowed = frozenset({"base_weights", "rrf_k", "rules"})

    def fuse(self, channels, frame, ctx):
        weights = dict(self.params.get("base_weights") or {
            "dense": 0.45, "bm25": 0.35, "graph_khop": 0.20, "temporal": 0.30,
        })
        if getattr(frame, "intent", "") == "temporal" or getattr(frame, "as_of", None) is not None:
            weights["temporal"] = weights.get("temporal", 0.3) * 1.5
            weights["bm25"] = weights.get("bm25", 0.35) * 1.1
        if getattr(frame, "intent", "") == "multi_hop":
            weights["graph_khop"] = weights.get("graph_khop", 0.2) * 1.5
        if getattr(frame, "entity_ids", None):
            weights["bm25"] = weights.get("bm25", 0.35) * 1.2
        present = {name: weights.get(name, 1.0) for name in channels}
        helper = WeightedRRFFusion(rrf_k=int(self.params.get("rrf_k", 60) or 60), weights=present)
        return helper.fuse(channels, frame, ctx)


# ---- rerank ------------------------------------------------------------

class Reranker(Parametrised):
    axis = AXIS_RERANK
    name = ""

    def rerank(self, candidates: Sequence[Candidate], frame: Any, store: Any,
               ctx: Any) -> tuple[list[Candidate], dict[str, Any]]:
        raise NotImplementedError


@register(AXIS_RERANK, "none")
class NoReranker(Reranker):
    def rerank(self, candidates, frame, store, ctx):
        return list(candidates), {"impl": "none", "fallback": False}


@register(AXIS_RERANK, "cross_encoder")
class CrossEncoderReranker(Reranker):
    """Optional dependency: if sentence-transformers is missing, keep the order."""

    params_allowed = frozenset({"model", "top_n", "batch_size", "device", "max_length"})

    def __init__(self, **params):
        super().__init__(**params)
        self._model = None

    def _load(self):
        from sentence_transformers import CrossEncoder  # optional dependency
        return CrossEncoder(self.params.get("model", "BAAI/bge-reranker-v2-m3"))

    def rerank(self, candidates, frame, store, ctx):
        if not candidates:
            return list(candidates), {"impl": "cross_encoder", "fallback": False}
        try:
            if self._model is None:
                self._model = self._load()
            units = [store.get(candidate.memory_id) for candidate in candidates]
            pairs = [(frame.query, unit.text if unit is not None else "") for unit in units]
            scores = [float(score) for score in self._model.predict(pairs)]
        except Exception as exc:  # missing optional dependency or model load failure
            return list(candidates), {"impl": "cross_encoder", "fallback": True,
                                      "reason": f"{type(exc).__name__}: {exc}"}
        top_n = int(self.params.get("top_n", len(candidates)) or len(candidates))
        reranked = []
        for candidate, score in sorted(zip(candidates, scores), key=lambda item: (-item[1], item[0].memory_id))[:top_n]:
            cloned = replace(candidate)
            cloned.score = score
            cloned.stage_scores = {**candidate.stage_scores, "rerank": score}
            cloned.provenance = {**candidate.provenance, "reranker": "cross_encoder"}
            reranked.append(cloned)
        for rank, candidate in enumerate(reranked, 1):
            candidate.rank = rank
        return reranked, {"impl": "cross_encoder", "fallback": False}


# ---- post-processing ---------------------------------------------------

class Filter(Parametrised):
    axis = AXIS_FILTER
    name = ""

    def apply(self, candidates: Sequence[Candidate], frame: Any, store: Any) -> list[Candidate]:
        raise NotImplementedError


@register(AXIS_FILTER, "none")
class NoFilter(Filter):
    def apply(self, candidates, frame, store):
        return list(candidates)


@register(AXIS_FILTER, "threshold")
class ThresholdFilter(Filter):
    params_allowed = frozenset({"min_score", "drop_stale", "drop_conflicting", "min_relevance", "stale_only"})

    def apply(self, candidates, frame, store):
        min_score = self.params.get("min_score")
        min_relevance = self.params.get("min_relevance")
        drop_stale = bool(self.params.get("drop_stale", False))
        drop_conflicting = bool(self.params.get("drop_conflicting", False))
        conflicting = {memory_id for pair in getattr(store, "conflicts", []) for memory_id in pair}
        maximum = max((abs(candidate.score) for candidate in candidates if candidate.score is not None), default=0.0)
        output = []
        for candidate in candidates:
            unit = store.get(candidate.memory_id)
            if unit is None:
                continue
            if min_score is not None and candidate.score is not None and candidate.score < float(min_score):
                continue
            if min_relevance is not None and candidate.score is not None:
                relative = abs(candidate.score) / maximum if maximum else 0.0
                if relative < float(min_relevance):
                    continue
            if drop_conflicting and candidate.memory_id in conflicting:
                continue
            if drop_stale:
                as_of = getattr(frame, "as_of", None)
                if as_of is not None:
                    if not model.is_valid_at(unit, as_of):
                        continue
                elif fact_fields(unit).get("state") == "HISTORICAL":
                    continue
            output.append(candidate)
        return output


class MMR(Parametrised):
    axis = AXIS_MMR
    name = ""

    def apply(self, candidates: Sequence[Candidate], frame: Any, store: Any) -> list[Candidate]:
        raise NotImplementedError


@register(AXIS_MMR, "none")
class NoMMR(MMR):
    def apply(self, candidates, frame, store):
        return list(candidates)


@register(AXIS_MMR, "mmr")
class MMRPost(MMR):
    params_allowed = frozenset({"lambda", "top_n", "similarity"})

    def apply(self, candidates, frame, store):
        if len(candidates) < 2:
            return list(candidates)
        from memwb import retrieval as legacy_retrieval

        lam = float(self.params.get("lambda", 0.7))
        top_n = int(self.params.get("top_n", len(candidates)) or len(candidates))
        units = {candidate.memory_id: store.get(candidate.memory_id) for candidate in candidates}
        tokens = {memory_id: set(legacy_retrieval.tokens(unit.text)) if unit else set()
                  for memory_id, unit in units.items()}
        scores = [candidate.score or 0.0 for candidate in candidates]
        low, high = min(scores), max(scores)
        relevance = {candidate.memory_id: ((candidate.score or 0.0) - low) / (high - low) if high > low else 1.0
                     for candidate in candidates}
        selected: list[Candidate] = []
        remaining = list(candidates)
        while remaining and len(selected) < top_n:
            best, best_value = None, None
            for candidate in remaining:
                similarity = max((len(tokens[candidate.memory_id] & tokens[chosen.memory_id]) /
                                  len(tokens[candidate.memory_id] | tokens[chosen.memory_id])
                                  if tokens[candidate.memory_id] | tokens[chosen.memory_id] else 1.0)
                                 for chosen in selected) if selected else 0.0
                value = lam * relevance[candidate.memory_id] - (1 - lam) * similarity
                if best_value is None or value > best_value:
                    best, best_value = candidate, value
            selected.append(best)
            remaining.remove(best)
        for rank, candidate in enumerate(selected, 1):
            candidate.rank = rank
            candidate.stage_scores["mmr"] = candidate.score or 0.0
        return selected


class Decay(Parametrised):
    axis = AXIS_DECAY
    name = ""

    def apply(self, candidates: Sequence[Candidate], frame: Any, store: Any) -> list[Candidate]:
        raise NotImplementedError


@register(AXIS_DECAY, "none")
class NoDecay(Decay):
    def apply(self, candidates, frame, store):
        return list(candidates)


@register(AXIS_DECAY, "time_decay")
class TimeDecayPost(Decay):
    params_allowed = frozenset({"lambda", "unit", "except_history"})

    def apply(self, candidates, frame, store):
        lam = float(self.params.get("lambda", 0.005))
        unit = self.params.get("unit", "day")
        except_history = bool(self.params.get("except_history", True))
        reference = getattr(frame, "as_of", None)
        if reference is None:
            moments = [candidate_unit.t_ingest.start for candidate_unit in
                       (store.get(candidate.memory_id) for candidate in candidates)
                       if candidate_unit is not None and candidate_unit.t_ingest and candidate_unit.t_ingest.start]
            reference = max(moments) if moments else None
        if reference is None:
            return list(candidates)
        output = []
        for candidate in candidates:
            memory = store.get(candidate.memory_id)
            factor = 1.0
            if memory is not None and not (except_history and fact_fields(memory).get("state") == "HISTORICAL"):
                interval = memory.t_event or memory.t_ingest
                start = interval.start if interval is not None else None
                if start is not None:
                    days = max(0.0, (reference - start).total_seconds() / 86400)
                    if unit == "hour":
                        days *= 24
                    factor = math.exp(-lam * days)
            cloned = replace(candidate)
            cloned.score = (candidate.score if candidate.score is not None else 1.0) * factor
            cloned.stage_scores = {**candidate.stage_scores, "decay": factor}
            output.append(cloned)
        output.sort(key=lambda candidate: (-(candidate.score or 0.0), candidate.memory_id))
        for rank, candidate in enumerate(output, 1):
            candidate.rank = rank
        return output


class Compress(Parametrised):
    axis = AXIS_COMPRESS
    name = ""

    def apply(self, candidates: Sequence[Candidate], frame: Any, store: Any) -> list[Candidate]:
        raise NotImplementedError


@register(AXIS_COMPRESS, "none")
class NoCompress(Compress):
    def apply(self, candidates, frame, store):
        return list(candidates)


@register(AXIS_COMPRESS, "extractive")
class ExtractiveCompress(Compress):
    """Keep the highest-ranked candidates that fit the token budget."""

    params_allowed = frozenset({"budget_tokens", "max_tokens"})

    def apply(self, candidates, frame, store):
        budget = int(self.params.get("budget_tokens", self.params.get("max_tokens", 4000)) or 4000)
        output, used = [], 0
        for candidate in candidates:
            unit = store.get(candidate.memory_id)
            cost = estimate_tokens(unit.text) if unit is not None else 0
            if output and used + cost > budget:
                continue
            output.append(candidate)
            used += cost
        for rank, candidate in enumerate(output, 1):
            candidate.rank = rank
        return output


# ---- pipeline ----------------------------------------------------------

@dataclass
class MergeResult:
    candidates: list[Candidate]
    units: list[MemoryUnit]
    waterfall: list[dict]
    trace: list[dict]
    fallbacks: list[str]
    tokens: int
    budget: int

    def context_text(self) -> str:
        return "\n".join(f"[{unit.memory_id}] {unit.text}" for unit in self.units)

    def by_id(self) -> dict[str, MemoryUnit]:
        return {unit.memory_id: unit for unit in self.units}

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidates": [candidate.memory_id for candidate in self.candidates],
            "tokens": self.tokens,
            "budget": self.budget,
            "waterfall": list(self.waterfall),
            "fallbacks": list(self.fallbacks),
        }


class MergePipeline:
    """Fusion -> rerank -> filter -> MMR -> decay -> compression."""

    def __init__(self, fusion: str = "rrf", rerank: str = "none", *,
                 filter: str = "none", mmr: str = "none", decay: str = "none",
                 compress: str = "none", params: Mapping[str, Mapping[str, Any]] | None = None,
                 order: Sequence[str] | None = None):
        params = params or {}
        self.fusion_name, self.rerank_name = fusion, rerank
        self.filter_name, self.mmr_name = filter, mmr
        self.decay_name, self.compress_name = decay, compress
        self.fusion = build_impl(AXIS_FUSION, fusion, params.get("fusion"))
        self.reranker = build_impl(AXIS_RERANK, rerank, params.get("rerank"))
        self.filter = build_impl(AXIS_FILTER, filter, params.get("filter"))
        self.mmr = build_impl(AXIS_MMR, mmr, params.get("mmr"))
        self.decay = build_impl(AXIS_DECAY, decay, params.get("decay"))
        self.compress = build_impl(AXIS_COMPRESS, compress, params.get("compress"))
        self.order = tuple(order or DEFAULT_ORDER)
        self.params = {key: dict(value or {}) for key, value in params.items()}

    @classmethod
    def from_config(cls, ctx: Any, **overrides) -> "MergePipeline":
        config = getattr(ctx, "config", None)

        def impl(path: str, default: str) -> str:
            value = config.impl(path) if config is not None and hasattr(config, "impl") else None
            return value or default

        def params(path: str) -> dict[str, Any]:
            return config.params(path) if config is not None and hasattr(config, "params") else {}

        order = overrides.pop("order", None)
        if order is None and config is not None:
            order = config.get("post.order")
        return cls(
            overrides.pop("fusion", impl("fusion", "rrf")),
            overrides.pop("rerank", impl("rerank", "none")),
            filter=overrides.pop("filter", impl("post.filter", "none")),
            mmr=overrides.pop("mmr", impl("post.mmr", "none")),
            decay=overrides.pop("decay", impl("post.decay", "none")),
            compress=overrides.pop("compress", impl("post.compress", "none")),
            params={
                "fusion": params("fusion"), "rerank": params("rerank"),
                "filter": params("post.filter"), "mmr": params("post.mmr"),
                "decay": params("post.decay"), "compress": params("post.compress"),
            },
            order=order,
            **overrides,
        )

    def run(self, retrieval: Any, store: Any, ctx: Any, *,
            gold_turns: Sequence[str] | None = None,
            budget: int | None = None) -> MergeResult:
        trace = Trace()
        waterfall: list[dict] = []
        fallbacks: list[str] = []
        budget = int(budget or getattr(retrieval, "k", 15) or 15)

        def record(stage: str, candidates: Sequence[Candidate], detail: str = "") -> None:
            row = {"stage": stage, "candidates": len(candidates),
                   **{key: value for key, value in stage_metrics(store, candidates, gold_turns).items()
                      if key != "candidates"}}
            waterfall.append(row)
            trace.add("merge", stage, detail or f"{len(candidates)} candidates, {row['tokens']} tokens")

        raw = list(retrieval.candidates)
        record("raw_channels", raw, f"{len(raw)} candidates from {len(getattr(retrieval, 'by_channel', {}) or {})} channel(s)")
        channels = getattr(retrieval, "by_channel", None) or {"fused": raw}
        candidates = list(raw)
        for stage in self.order:
            if stage == "fusion":
                candidates = self.fusion.fuse(channels, retrieval.frame, ctx)
                candidates = candidates[:budget]
            elif stage == "rerank":
                candidates, info = self.reranker.rerank(candidates, retrieval.frame, store, ctx)
                if info.get("fallback"):
                    fallbacks.append(f"rerank:{info.get('reason', 'fallback')}")
                candidates = candidates[:budget]
            elif stage == "filter":
                candidates = self.filter.apply(candidates, retrieval.frame, store)
            elif stage == "mmr":
                candidates = self.mmr.apply(candidates, retrieval.frame, store)
            elif stage == "decay":
                candidates = self.decay.apply(candidates, retrieval.frame, store)
            elif stage == "compress":
                candidates = self.compress.apply(candidates, retrieval.frame, store)
            else:
                raise ValueError(f"unknown merge stage: {stage!r}")
            candidates = candidates[:budget]
            record(f"after_{stage}", candidates,
                   f"{len(candidates)} candidates (fusion={self.fusion_name}, rerank={self.rerank_name})")
        units = candidate_units(store, candidates)
        total_tokens = context_tokens(units)
        trace.add("merge", "context", f"{len(units)} units, {total_tokens} tokens")
        return MergeResult(candidates=candidates, units=units, waterfall=waterfall,
                           trace=trace.to_list(), fallbacks=fallbacks,
                           tokens=total_tokens, budget=budget)
