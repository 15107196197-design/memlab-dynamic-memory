"""R3: graph.retrieval.impl is a real dispatch, not a validated-only switch.

Each implementation must produce a different, explainable candidate set or score;
vector_only must remove the graph channel; unimplemented impls must fail closed.
"""
import unittest
from types import SimpleNamespace

from memlab import config as lab_config, model, retrieve, store as store_module
from memlab.contracts import Interval, MemoryUnit, Span


def _interval(moment):
    parsed = model.parse_time(moment)
    return Interval(start=parsed, precision="day") if parsed else Interval(precision="unknown")


def turn_unit(memory_id, turn, text, entity, moment):
    interval = _interval(moment)
    return MemoryUnit(
        memory_id=memory_id, kind="turn", text=text,
        structured={"speaker": entity, "turn": turn, "state": "ACTIVE"},
        entity_ids=[entity.casefold()], t_event=interval, t_ingest=interval,
        evidence=[Span(turn, text)],
    )


def fact_unit(memory_id, entity, slot, value, source_turn, moment):
    return MemoryUnit(
        memory_id=memory_id, kind="fact", text=f"{entity} {slot} {value}",
        structured={"entity": entity, "attribute": slot, "slot": slot, "value": value,
                    "kind": "state", "state": "ACTIVE", "source_memory_id": source_turn},
        entity_ids=[entity.casefold()], t_ingest=_interval(moment),
        evidence=[Span(source_turn, value)],
    )


def fixture(representation="state_slot"):
    units = [
        turn_unit("t1", "D1:1", "Caroline job teacher", "Caroline", "2023-01-01T10:00"),
        turn_unit("t2", "D2:1", "Caroline job engineer", "Caroline", "2023-05-01T10:00"),
        turn_unit("t3", "D3:1", "Caroline job manager", "Caroline", "2023-09-01T10:00"),
        turn_unit("t4", "D4:1", "Caroline city Paris", "Caroline", "2023-02-01T10:00"),
        turn_unit("t5", "D5:1", "Melanie job nurse", "Melanie", "2023-03-01T10:00"),
        fact_unit("f1", "Caroline", "job", "teacher", "D1:1", "2023-01-01T10:00"),
        fact_unit("f2", "Caroline", "job", "engineer", "D2:1", "2023-05-01T10:00"),
        fact_unit("f3", "Caroline", "job", "manager", "D3:1", "2023-09-01T10:00"),
        fact_unit("f4", "Caroline", "city", "Paris", "D4:1", "2023-02-01T10:00"),
        fact_unit("f5", "Melanie", "job", "nurse", "D5:1", "2023-03-01T10:00"),
    ]
    store = store_module.MemoryStore(units)
    store.ensure_graph(representation)
    return store


def context(impl, representation="state_slot", params=None):
    data = {"graph": {"repr": {"impl": representation},
                      "retrieval": {"impl": impl, "params": dict(params or {})}}}
    return SimpleNamespace(store=fixture(representation),
                           config=lab_config.RunConfig.from_dict(data, validate=False),
                           embedding=None, cache=None)


FRAME = retrieve.QueryFrame(query="Caroline job", intent="multi_hop", complexity=0.6)


def run(impl, representation="state_slot", params=None, seeds=("f3",), k=10):
    ctx = context(impl, representation, params)
    node = retrieve.PlanNode("n1", FRAME.query, "graph_khop", filters={"seed_ids": list(seeds)})
    candidates = retrieve.GraphKHopRetriever().retrieve(FRAME, node, k, ctx)
    return ctx, candidates


class GraphDispatchTests(unittest.TestCase):
    def test_slot_expand_returns_only_the_same_slot_version_chain(self):
        _ctx, candidates = run("slot_expand", "state_slot", {"limit": 8}, seeds=("f2",))
        ids = {candidate.memory_id for candidate in candidates}
        self.assertEqual(ids, {"f1", "f2", "f3"})  # no evidence turns, no city fact
        self.assertTrue(all(candidate.provenance["retrieval_impl"] == "slot_expand" for candidate in candidates))
        self.assertLessEqual(len(candidates), 8)
        self.assertEqual([candidate.memory_id for candidate in candidates], ["f2", "f3", "f1"])

    def test_entity_subgraph_walks_the_entity_hub(self):
        _ctx, candidates = run("entity_subgraph", "entity_triple", {"k_hop": 2}, seeds=("f3",))
        ids = {candidate.memory_id for candidate in candidates}
        self.assertIn("f4", ids)  # same entity, different slot, reached through entity:caroline
        self.assertTrue({"f1", "f2", "f3"} <= ids)
        self.assertTrue(all(candidate.provenance["retrieval_impl"] == "entity_subgraph"
                            for candidate in candidates))

    def test_dual_channel_keeps_the_set_but_changes_the_scores(self):
        _entity_ctx, entity = run("entity_subgraph", "entity_triple", {"k_hop": 2}, seeds=("f3",))
        _dual_ctx, dual = run("dual_channel", "entity_triple",
                              {"k_hop": 2, "channel_weights": {"entity": 0.6, "semantic": 0.4}},
                              seeds=("f3",))
        entity_scores = {candidate.memory_id: candidate.score for candidate in entity}
        dual_scores = {candidate.memory_id: candidate.score for candidate in dual}
        self.assertEqual(set(entity_scores), set(dual_scores))
        self.assertNotEqual(entity_scores, dual_scores)
        self.assertTrue(all(candidate.provenance["retrieval_impl"] == "dual_channel" for candidate in dual))

    def test_ppr_is_deterministic_and_uses_the_configured_constants(self):
        _ctx, first = run("ppr", "three_layer", seeds=("f3",))
        _ctx2, second = run("ppr", "three_layer", seeds=("f3",))
        self.assertTrue(first)
        self.assertEqual([(c.memory_id, c.score) for c in first],
                         [(c.memory_id, c.score) for c in second])
        self.assertEqual(first[0].provenance["retrieval_impl"], "ppr")
        self.assertEqual(first[0].provenance["alpha"], 0.15)
        self.assertEqual(first[0].provenance["top_k"], 30)
        _entity_ctx, entity = run("entity_subgraph", "three_layer", {"k_hop": 2}, seeds=("f3",))
        self.assertNotEqual([c.memory_id for c in first], [c.memory_id for c in entity])

    def test_slot_expand_rejects_a_non_state_slot_graph(self):
        with self.assertRaises(ValueError):
            run("slot_expand", "entity_triple")


class GraphGateTests(unittest.TestCase):
    def test_vector_only_removes_the_graph_channel_and_returns_nothing(self):
        ctx = context("vector_only", "state_slot")
        self.assertNotIn("graph_khop", retrieve._channels_for(FRAME, ctx))
        plan = retrieve.RuleRouterPlanner().plan(FRAME, ctx)
        self.assertNotIn("graph_khop", [node.channel for node in plan.nodes])
        node = retrieve.PlanNode("n1", FRAME.query, "graph_khop", filters={"seed_ids": ["f3"]})
        self.assertEqual(retrieve.GraphKHopRetriever().retrieve(FRAME, node, 10, ctx), [])

    def test_graph_impl_still_routes_in_the_graph_channel(self):
        ctx = context("dual_channel", "state_slot")
        self.assertIn("graph_khop", retrieve._channels_for(FRAME, ctx))

    def test_unimplemented_impls_fail_closed(self):
        node = retrieve.PlanNode("n1", FRAME.query, "graph_khop", filters={"seed_ids": ["f3"]})
        for impl in ("community_summary", "hybrid_graph"):
            with self.subTest(impl=impl):
                ctx = context(impl, "state_slot")
                with self.assertRaises(NotImplementedError):
                    retrieve.GraphKHopRetriever().retrieve(FRAME, node, 10, ctx)


if __name__ == "__main__":
    unittest.main()
