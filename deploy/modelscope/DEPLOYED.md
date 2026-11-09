# ModelScope deployment record

- Studio: https://www.modelscope.cn/studios/A1211JOY/dynamic-memory-workbench
- GitHub mirror of this code: https://github.com/15107196197-design/memlab-dynamic-memory
- SDK: Docker
- Hardware: `platform/2v-cpu-8g-mem` (free CPU)
- Port: 7860
- Status: `Running` (2026-11-09 22:14 CST)

## Endpoints

| Purpose | URL | Notes |
|---|---|---|
| Human entry point | https://www.modelscope.cn/studios/A1211JOY/dynamic-memory-workbench | Open this in a browser |
| Raw app host | https://a1211joy-dynamic-memory-workbench.ms.show | Returns 403 without a browser referer; do not use for scripts |
| API host | https://studio-a1211joy-dynamic-memory-workbench.api-inference.modelscope.net | Requires `Authorization: Bearer <ModelScope token>` |

## Verified

Checked on 2026-11-09 22:40 CST:

- Studio page: `200`.
- API host, with a ModelScope token:
  - `GET /api/v2/evaluation` → `200`, 243 KB, 26 project reports including `final-w3-test-online-fixed`, `final-w3-test-online`, `final-w3-test-offline`.
  - `GET /api/v2/experiments/final-w3-test-online-fixed/report` → `200`, 12.8 KB, F1 `0.2547`, refused `0.30`, with `analysis.diagnosis` and `analysis.before_after`.
- Without the token the API host returns `401`; the `ms.show` host returns `403` for non-browser clients.
- Full local suite: 276 tests OK.

```bash
TOKEN="$(tr -d '[:space:]' < .secrets/modelscope_token)"   # workspace-level, never committed
API=https://studio-a1211joy-dynamic-memory-workbench.api-inference.modelscope.net
curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/v2/evaluation" -o /tmp/eval.json
curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/v2/experiments/final-w3-test-online-fixed/report"
```

## Notes

- The free CPU Studio may sleep after inactivity; the first request can be slow.
- Online LLM ask/lab pages need Ollama, which is not available inside the Studio; the evaluation, memory, and report pages are the public demo.
- Token stays in the local workspace `.secrets/modelscope_token`; it is not committed and not written into the Studio repo.
- Update the GitHub documentation whenever the Studio owner or URL changes.

## Update

```bash
python deploy/modelscope/build_bundle.py
MODELSCOPE=/path/to/modelscope deploy/modelscope/publish.sh A1211JOY/dynamic-memory-workbench
```
