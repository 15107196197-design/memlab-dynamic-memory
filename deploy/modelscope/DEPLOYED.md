# ModelScope deployment record

- Studio: https://www.modelscope.cn/studios/A1211JOY/dynamic-memory-workbench
- GitHub mirror of this code: https://github.com/15107196197-design/memlab-dynamic-memory
- SDK: Docker
- Hardware: `platform/2v-cpu-8g-mem` (free CPU)
- Port: 7860
- Status: `Running`, online Q&A backed by the author's GPU host (2026-11-09 23:15 CST)

## Endpoints

| Purpose | URL | Notes |
|---|---|---|
| Human entry point | https://www.modelscope.cn/studios/A1211JOY/dynamic-memory-workbench | Open this in a browser |
| Raw app host | https://a1211joy-dynamic-memory-workbench.ms.show | Returns 403 without a browser referer; do not use for scripts |
| API host | https://studio-a1211joy-dynamic-memory-workbench.api-inference.modelscope.net | Requires `Authorization: Bearer <ModelScope token>` |

## Online Q&A backend (GPU host)

The Studio container has no Ollama. It reaches the project's own GPU box instead:

```text
browser ─▶ Studio (search, retrieval, prompt) ─▶ http://121.41.215.161:8443/<token>
                                                     │  token gateway (systemd)
                                                     ▼
                                            127.0.0.1:11434  Ollama
                                            qwen3.8:27b-q4_K_M + bge-m3
```

- Gateway: [ollama_gateway.py](ollama_gateway.py), unit file [memlab-gateway.service](memlab-gateway.service).
- The gateway keeps Ollama bound to `127.0.0.1` and only proxies paths prefixed with the random token, because MemLab's Ollama client cannot send auth headers. Anything without the token gets `404`.
- Studio variables (`modelscope studio variable`):

```text
OLLAMA_URL      http://121.41.215.161:8443/<token>
EMBED_URL       http://121.41.215.161:8443/<token>
MEMORY_MODEL    qwen3.8:27b-q4_K_M
EMBED_MODEL     bge-m3
MEMORY_CONTEXT  8192
```

- Install / restart on the GPU host:

```bash
scp deploy/modelscope/ollama_gateway.py deploy/modelscope/memlab-gateway.service root@121.41.215.161:/root/memlab-deploy/
ssh root@121.41.215.161 'install -m 644 /root/memlab-deploy/memlab-gateway.service /etc/systemd/system/ \
  && systemctl daemon-reload && systemctl restart memlab-gateway'
```

- Rotate the token: replace `gateway.token`, `systemctl restart memlab-gateway`, then
  `modelscope studio variable update A1211JOY/dynamic-memory-workbench OLLAMA_URL ...`
  (and `EMBED_URL`), and trigger a redeploy.

### Why not the Cloudflare quick tunnel

A `cloudflared` quick tunnel was tried first and worked, but the connector registered in
`lax08` (Los Angeles): every embedding round trip took 5-6 s, one question needed 21 of
them, and the ModelScope ingress returns `504` after 120 s. A direct security-group port
drops the round trip to ~60 ms and the whole question to ~30 s, so the tunnel is retired.

## Verified

2026-11-09 23:12 CST:

- `GET /api/v2/health` → `200`, `available: true`, `base_url` = the gateway URL, model `qwen3.8:27b-q4_K_M`.
- `POST /api/v2/runs` `{sample: conv-26, question: "What is Caroline's current mood?", preset: R0, offline: false}` → `200` in 30 s, `latency_ms 24244`, `refused: false`, model `qwen3.8:27b-q4_K_M`, tokens `1088`. This is a real 27B answer, not the offline extractive demo.
- Studio page and `/api/v2/evaluation` (26 project reports) still `200`.
- Local suite: `tests.test_webapp` 29 tests OK.

Earlier baseline (2026-11-09 22:40 CST): 26 project reports reachable, `final-w3-test-online-fixed` returns F1 `0.2547`, refused `0.30`, with `analysis.diagnosis` and `analysis.before_after`.

## Notes and limits

- Free CPU Studio sleeps after inactivity; the first request can be slow.
- The GPU host is a personal machine: when it is off, `/api/v2/health` reports
  `available: false` and the ask page falls back to the offline demo; evaluation,
  memory and report pages keep working.
- The gateway link is plain HTTP with the secret in the path, i.e. protection against
  accidental use, not against a compromised network. Do not put anything sensitive in
  demo questions.
- `MEMORY_CONTEXT=8192` is deliberate: 32k context plus the cross-encoder OOMed the
  48 GB card during the experiments.
- Token stays in the local workspace `.secrets/modelscope_token` (ModelScope) and
  `/root/memlab-deploy/gateway.token` (gateway); neither is committed.
- Update this file whenever the Studio owner, URL, or backend host changes.

## Update

```bash
python deploy/modelscope/build_bundle.py
MODELSCOPE=/path/to/modelscope deploy/modelscope/publish.sh A1211JOY/dynamic-memory-workbench
```
