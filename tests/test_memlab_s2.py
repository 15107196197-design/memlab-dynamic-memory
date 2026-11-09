"""S2 tests: MemoryUnit v2 migration, export v2/v1 compatibility, content-addressed cache."""
import json
import tempfile
import unittest
from pathlib import Path

from memlab import cache, export, model
from memwb import dataset, export as legacy_export, memory


class ConversationCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample = dataset.store().get("conv-26")
        cls.turns, cls.facts = memory.build(cls.sample)
        cls.view = model.from_legacy(cls.turns, cls.facts, conversation="conv-26")
        cls.units = {unit.memory_id: unit for unit in cls.view.units}


class ModelTests(ConversationCase):
    def test_v2_view_covers_every_legacy_record(self):
        self.assertEqual(len(self.view.units), len(self.turns) + len(self.facts))
        self.assertEqual(len(self.view.of_kind("turn")), len(self.turns))
        self.assertEqual(len(self.view.of_kind("fact")), len(self.facts))
        self.assertTrue(self.view.relations)
        self.assertEqual(self.view.conversation, "conv-26")
        self.assertEqual(self.view.units[0].schema_version, model.SCHEMA_VERSION)
        with self.assertRaises(ValueError):
            self.view.of_kind("rumour")

    def test_load_reads_the_existing_facts_and_states(self):
        view = model.load("conv-26")
        self.assertEqual(len(view.units), len(self.view.units))
        self.assertEqual(len(view.relations), len(self.view.relations))
        self.assertEqual(view.conversation, "conv-26")

    def test_turn_maps_to_the_full_v2_envelope(self):
        legacy = self.turns[0]
        unit = self.units[legacy["memory_id"]]
        self.assertEqual((unit.kind, unit.text), ("turn", legacy["content"]))
        self.assertEqual(unit.entity_ids, ["caroline"])
        self.assertEqual(unit.structured["speaker"], "Caroline")
        self.assertEqual(unit.structured["turn"], "D1:1")
        self.assertEqual(unit.t_ingest.start.isoformat(timespec="minutes"), "2023-05-08T13:56")
        self.assertEqual(unit.t_ingest.precision, "session")
        self.assertEqual(unit.t_event, unit.t_ingest)  # an utterance is observed when spoken
        self.assertIsNone(unit.valid_interval)
        self.assertEqual(unit.evidence[0].turn_id, "D1:1")
        self.assertEqual(unit.evidence[0].quote, legacy["content"])
        self.assertEqual(unit.evidence[0].start, 0)
        self.assertEqual(unit.provenance["origin"], "memwb.memory.build")
        self.assertEqual(unit.provenance["extractor"], model.LEGACY_EXTRACTOR)
        self.assertEqual(unit.provenance["source"], legacy["source"])

    def test_fact_without_event_time_is_marked_unknown_not_guessed(self):
        legacy = next(fact for fact in self.facts if not fact["resolved_date"])
        unit = self.units[legacy["memory_id"]]
        self.assertEqual(unit.kind, "fact")
        self.assertEqual(unit.t_event.precision, "unknown")
        self.assertIsNone(unit.t_event.start)
        self.assertIsNone(unit.t_event.end)
        self.assertEqual(unit.t_ingest.start.isoformat(timespec="minutes"), legacy["session_time"])
        self.assertIsNone(unit.structured["resolved_date"])
        self.assertEqual(unit.valid_interval.precision, "unknown")
        self.assertIsNone(unit.valid_interval.start)

    def test_resolved_relative_date_becomes_a_day_precision_event_time(self):
        unit = self.units["conv26_D1_3_f0"]
        self.assertEqual(unit.t_event.start.isoformat(), "2023-05-07T00:00:00")
        self.assertEqual(unit.t_event.precision, "day")
        self.assertEqual(unit.valid_interval.start, unit.t_event.start)
        self.assertEqual(unit.evidence[0].turn_id, "D1:3")
        self.assertIn("LGBTQ", unit.evidence[0].quote)

    def test_invalidation_closes_validity_at_the_recorded_endpoint(self):
        unit = self.units["conv26_D2_8_f0"]
        self.assertEqual(unit.provenance["validity"]["legacy_state"], "HISTORICAL")
        self.assertEqual(unit.provenance["validity"]["invalidated_by"], "conv26_D8_9_f0")
        self.assertEqual(unit.valid_interval.end.isoformat(), "2023-07-14T00:00:00")
        self.assertEqual(unit.provenance["validity"]["endpoint"], "t_event")

        fallback = self.units["conv26_D5_4_f0"]
        self.assertEqual(fallback.provenance["validity"]["endpoint"], "t_ingest")
        self.assertEqual(fallback.valid_interval.end.isoformat(), "2023-07-03T13:36:00")

    def test_every_fact_event_time_matches_its_recorded_date(self):
        for fact in self.facts:
            unit = self.units[fact["memory_id"]]
            if fact["resolved_date"]:
                self.assertEqual(unit.t_event.start.isoformat(), fact["resolved_date"] + "T00:00:00")
                self.assertEqual(unit.t_event.precision, "day")
            else:
                self.assertIsNone(unit.t_event.start)
                self.assertEqual(unit.t_event.precision, "unknown")

    def test_legacy_fact_round_trips_through_v2(self):
        keys = ("memory_id", "content", "entity", "attribute", "value", "event", "time_expression",
                "resolved_date", "slot", "kind", "state", "timestamp", "session_time", "source",
                "source_memory_id")
        for fact in self.facts[:40]:
            restored = model.to_legacy(self.units[fact["memory_id"]], self.view.relations)
            for key in keys:
                self.assertEqual(restored.get(key), fact.get(key), msg=f"{fact['memory_id']} {key}")
            original = {(r["type"], r["direction"], r["memory_id"]) for r in fact["relations"]}
            rebuilt = {(r["type"], r["direction"], r["memory_id"]) for r in restored["relations"]}
            self.assertEqual(rebuilt, original, msg=fact["memory_id"])

    def test_legacy_turn_round_trips_through_v2(self):
        for turn in self.turns[:20]:
            restored = model.to_legacy(self.units[turn["memory_id"]])
            for key in ("memory_id", "content", "entity", "timestamp", "session_time", "source",
                        "state", "fact_ids", "resolved_time_expressions"):
                self.assertEqual(restored[key], turn[key], msg=f"{turn['memory_id']} {key}")

    def test_unit_dictionary_round_trip(self):
        for unit in self.view.units[:80]:
            self.assertEqual(model.unit_from_dict(model.unit_to_dict(unit)), unit)
        with self.assertRaises(ValueError):
            model.unit_from_dict({**model.unit_to_dict(self.view.units[0]), "schema_version": "1.0"})

    def test_relations_are_typed_and_deduplicated(self):
        seen = set()
        for relation in self.view.relations:
            self.assertNotEqual(relation.head_id, relation.tail_id)
            self.assertIn(relation.type, {"RETAIN", "UPDATE", "SUPERSEDE", "CONFLICT"})
            key = (relation.head_id, relation.tail_id, relation.type)
            self.assertNotIn(key, seen)
            seen.add(key)
            self.assertTrue(relation.provenance["origin"])
        self.assertIn("UPDATE", {relation.type for relation in self.view.relations})


class ExportTests(ConversationCase):
    def test_v2_export_passes_the_contract_check(self):
        document = export.export_v2(self.sample)
        export.validate_v2(document)
        self.assertEqual(document["schema"], export.SCHEMA_V2)
        self.assertEqual(document["conversation"], "conv-26")
        self.assertEqual(document["counts"]["memories"], len(self.view.units))
        self.assertEqual(document["counts"]["relations"], len(self.view.relations))
        ids = [memory["memory_id"] for memory in document["memories"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(document["counts"]["by_kind"], {"fact": len(self.facts), "turn": len(self.turns)})

    def test_v2_memories_round_trip_from_the_document(self):
        document = export.export_v2(self.sample)
        for memory in document["memories"][:60]:
            self.assertEqual(model.unit_to_dict(model.unit_from_dict(memory)), memory)

    def test_v1_export_is_byte_compatible_with_the_legacy_exporter(self):
        old = legacy_export.export(self.sample)
        through_lab = export.export(self.sample, "v1")
        for key in ("schema", "conversation", "split", "extraction_model", "counts",
                    "memories", "turns", "slots"):
            self.assertEqual(json.dumps(through_lab[key], sort_keys=True, ensure_ascii=False),
                             json.dumps(old[key], sort_keys=True, ensure_ascii=False), msg=key)
        self.assertEqual(through_lab["schema"], legacy_export.SCHEMA)

    def test_export_schema_dispatch(self):
        for value in ("2", "v2", export.SCHEMA_V2):
            self.assertEqual(export.export(self.sample, value)["schema"], export.SCHEMA_V2)
        for value in ("1", "v1", export.SCHEMA_V1):
            self.assertEqual(export.export(self.sample, value)["schema"], export.SCHEMA_V1)
        with self.assertRaises(ValueError):
            export.export(self.sample, "v3")

    def test_validate_v2_rejects_broken_documents(self):
        document = export.export_v2(self.sample)
        broken = json.loads(json.dumps(document))
        del broken["memories"][0]["evidence"]
        with self.assertRaises(ValueError):
            export.validate_v2(broken)

        broken = json.loads(json.dumps(document))
        broken["memories"][0]["t_event"]["precision"] = "fortnight"
        with self.assertRaises(ValueError):
            export.validate_v2(broken)

        broken = json.loads(json.dumps(document))
        broken["relations"][0]["tail_id"] = "missing-memory"
        with self.assertRaises(ValueError):
            export.validate_v2(broken)

        broken = json.loads(json.dumps(document))
        broken["counts"]["memories"] += 1
        with self.assertRaises(ValueError):
            export.validate_v2(broken)

        with self.assertRaises(ValueError):
            export.validate_v2(legacy_export.export(self.sample))

    def test_unknown_intervals_never_carry_invented_bounds(self):
        document = export.export_v2(self.sample)
        for memory in document["memories"]:
            for field in ("t_event", "t_ingest", "valid_interval"):
                interval = memory[field]
                if interval and interval["precision"] == "unknown":
                    self.assertIsNone(interval["start"])
                    self.assertIsNone(interval["end"])

    def test_read_validates_exported_files(self):
        document = export.export_v2(self.sample)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "export.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            self.assertEqual(export.read(str(path))["schema"], export.SCHEMA_V2)
            path.write_text(json.dumps({**document, "schema": export.SCHEMA_V1}), encoding="utf-8")
            self.assertEqual(export.read(str(path))["schema"], export.SCHEMA_V1)  # v1 is read as-is
            path.write_text(json.dumps({**document, "schema_version": "9.9"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                export.read(str(path))


class CacheTests(unittest.TestCase):
    BASE = {
        "impl": "legacy_flat",
        "params": {"k": 1},
        "prompt_hash": "sha256:" + "a" * 64,
        "model_fingerprint": "sha256:" + "b" * 64,
        "schema_version": "2.0",
    }

    def key(self, *, stage="extract", payload=None, **overrides):
        fields = {**self.BASE, **overrides}
        return cache.make_key(stage, {"turn": "D1:1"} if payload is None else payload, **fields)

    def test_key_is_stable_under_dict_order(self):
        self.assertEqual(self.key(params={"k": 1, "b": 2}), self.key(params={"b": 2, "k": 1}))

    def test_every_key_field_is_content_addressed(self):
        baseline = self.key()
        self.assertEqual(baseline, self.key())
        variants = {
            "stage": self.key(stage="answer"),
            "payload": self.key(payload={"turn": "D1:2"}),
            "impl": self.key(impl="meta_schema"),
            "params": self.key(params={"k": 2}),
            "prompt_hash": self.key(prompt_hash="sha256:" + "c" * 64),
            "model_fingerprint": self.key(model_fingerprint="sha256:" + "d" * 64),
            "schema_version": self.key(schema_version="3.0"),
        }
        for field, value in variants.items():
            self.assertNotEqual(baseline, value, msg=field)
        self.assertEqual(len({baseline, *variants.values()}), len(variants) + 1)

    def test_prompt_and_schema_changes_miss(self):
        with tempfile.TemporaryDirectory() as directory:
            store = cache.ArtifactCache(directory)
            prompt_a = self.key()
            prompt_b = self.key(prompt_hash="sha256:" + "e" * 64)
            schema_2 = self.key(schema_version="2.0")
            schema_3 = self.key(schema_version="3.0")
            store.put(prompt_a, {"answer": "cached"})
            store.put(schema_2, {"answer": "cached"})
            self.assertIsNone(store.get(prompt_b))
            self.assertIsNone(store.get(schema_3))
            self.assertEqual(store.get(prompt_a), {"answer": "cached"})
            self.assertEqual(store.stats()["hits"], 1)
            self.assertEqual(store.stats()["misses"], 2)

    def test_put_get_and_stats(self):
        with tempfile.TemporaryDirectory() as directory:
            store = cache.ArtifactCache(directory)
            key = self.key()
            self.assertFalse(store.has(key))
            self.assertIsNone(store.get(key))
            path = store.put(key, {"memories": [1, 2], "nested": {"b": 1, "a": 2}})
            self.assertTrue(path.is_file())
            self.assertTrue(store.has(key))
            self.assertEqual(store.get(key), {"memories": [1, 2], "nested": {"b": 1, "a": 2}})
            self.assertEqual(store.stats(), {"hits": 1, "misses": 1, "lookups": 2,
                                             "hit_rate": 0.5, "root": directory})

    def test_get_or_compute_runs_the_producer_once(self):
        with tempfile.TemporaryDirectory() as directory:
            store = cache.ArtifactCache(directory)
            calls = []

            def producer():
                calls.append(1)
                return {"computed": len(calls)}

            key = self.key()
            self.assertEqual(store.get_or_compute(key, producer), {"computed": 1})
            self.assertEqual(store.get_or_compute(key, lambda: self.fail("should hit")), {"computed": 1})
            self.assertEqual(calls, [1])

    def test_invalid_and_corrupt_entries_are_not_silent(self):
        with tempfile.TemporaryDirectory() as directory:
            store = cache.ArtifactCache(directory)
            with self.assertRaises(ValueError):
                store.get("not-a-key")
            with self.assertRaises(ValueError):
                store.path_for("sha256:" + "x" * 64)
            key = self.key()
            path = store.path_for(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(cache.CacheError):
                store.get(key)

    def test_key_requires_a_stage(self):
        with self.assertRaises(ValueError):
            cache.make_key("", {})


if __name__ == "__main__":
    unittest.main()
