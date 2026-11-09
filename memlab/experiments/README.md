# memlab.experiments · S5 experiment control plane

S5 turns a design spec into a reproducible run matrix, executes it with resume and
sharding, and stores per-question metrics in SQLite. It does not implement new
memory modules; it makes existing W/S/R (and later M/U/K) measurable.

## CLI

```bash
# compile only; never calls a model
python -m memlab.experiments.cli sweep \
  --spec configs/experiments/e1-adoption.json \
  --dry-run --out runs/e1-adoption-matrix.json

# run a small shard; resume skips completed (run_id, qid)
python -m memlab.experiments.cli run \
  --spec configs/experiments/e1-adoption.json \
  --db runs/s5.sqlite --limit 10 --shard 0 --shards 4

# summarize
python -m memlab.experiments.cli analyze --db runs/s5.sqlite --metric answer_f1
```

## Spec support

| design | status | notes |
|---|---|---|
| `single_factor` | ✅ | one factor at a time; supports `applies_when` |
| `single_factor_adoption` | ✅ | B0+ / R0− pairs; respects `add_baseline: R0_only` |
| `full_factorial` | ✅ | low/high or levels; full cross product |
| `fractional_factorial` | ✅ (limited) | only `2^(k-1)` half-fraction; `p>1` raises a clear error |
| `environment_grid` | ✅ | LLM × data scale × scene × candidate |
| `nested_factorial` | ❌ | out of S5 scope |

Every plan records both `requested_config` and `effective_config`. `effective_config`
is the result of applying the spec's `derived_rules` (for example
`graph.repr=none → graph.retrieval=vector_only`) and the environment/dataset
overrides. `config_hash` is the digest of the effective config, so two runs with
the same hash are the same point even if one was requested differently.

## Store

SQLite tables:

- `runs`: run_id, spec_id, design, config_hash, status, config/environment/dataset/
  factors/notes JSON;
- `metrics`: one row per `(run_id, qid, metric)`, so resume and analysis are simple
  queries;
- `artifacts`: run_id, kind, path, hash.

`Runner.resume=True` skips a question only when at least one metric row for
`(run_id, qid)` exists. Errors are stored as `metric=error` with a type/message,
not silently dropped.

## Runner

- `--limit` questions per conversation (stratified by LoCoMo category);
- `--shard/--shards` for manual parallelism (run one process per shard);
- `--no-resume` to rerun everything;
- default executor uses `memlab.runtime.Runtime`; R0 is rejected by
  `memlab.guards.require_runnable` until the module pipeline exists;
- tests inject a fake executor, so no Ollama is needed for the S5 suite.

## Known limits (S5 scope)

- **Analysis is minimal**: per-run mean/count/min/max. Bootstrap, LMM, interactions
  and Pareto belong to S6/S7 and must read the same SQLite rows.
- **No process pool**: parallelism is `--shard/--shards`; the caller starts N
  processes.
- **Fractional factorial** supports only the half-fraction used by E3; other
  fractions fail rather than silently generating a wrong design.
- **Environment grid** maps candidate IDs to B0/R0 reference configs; full preset
  resolution is a later concern.
- **API provider adapter** is not part of S5; S9 will add it. Default executor is
  local Ollama.
- **Artifacts** are registered but not content-addressed by the runner; module
  caches already use `memlab.cache`.

## Tests

```bash
python -m unittest tests.test_memlab_s5 -v
python -m unittest discover -s tests -t .
```

S5 tests cover: spec validation, derived rules, adoption pairs, half-fraction
count, environment cross product, SQLite round-trip, 3 configs × 10 questions,
resume, sharding, and CLI dry-run.
