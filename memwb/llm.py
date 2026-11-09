"""Minimal Ollama client (generation and embeddings) using only the standard library."""
import json
import os
import urllib.error
import urllib.request

from . import config


class ContextOverflow(ValueError):
    """The prompt filled the context window, so the model may not have seen all of it."""


def post(path, body, timeout=900, base=None):
    req = urllib.request.Request(
        (base or config.ollama_url()) + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(detail).get("error", detail)
        except (ValueError, AttributeError):
            pass
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc


def model_options():
    if os.getenv("MEMORY_CPU_ONLY") == "1":
        return {"num_gpu": 0, "num_thread": int(os.getenv("MEMORY_THREADS", "4"))}
    if os.getenv("MEMORY_GPU_LAYERS"):
        return {"num_gpu": int(os.environ["MEMORY_GPU_LAYERS"])}
    return {}


def embedding_options():
    if os.getenv("EMBED_CPU_ONLY") == "1":
        return {"num_gpu": 0, "num_thread": int(os.getenv("EMBED_THREADS", "4"))}
    return model_options()


def generate(prompt, json_mode=False, model=None, max_tokens=None, *,
             temperature=None, num_ctx=None, options=None):
    """Deterministic generation. Truncation and context shifting are disabled so that
    an over-long prompt fails loudly instead of silently dropping evidence.

    ``temperature``, ``num_ctx`` and ``options`` are optional overrides used by the
    MemLab wrapper; when omitted the legacy defaults are unchanged.
    """
    effective_ctx = config.context_size() if num_ctx is None else int(num_ctx)
    effective_options = {
        "temperature": 0 if temperature is None else float(temperature),
        "num_ctx": effective_ctx,
        **model_options(),
    }
    if options:
        effective_options.update(dict(options))
    body = {
        "model": model or config.answer_model(),
        "prompt": prompt,
        "stream": False,
        "think": False,
        "truncate": False,
        "shift": False,
        "options": effective_options,
    }
    if max_tokens:
        body["options"]["num_predict"] = max_tokens
    if json_mode:
        body["format"] = "json"
    payload = post("/api/generate", body)
    if payload.get("prompt_eval_count", 0) >= effective_ctx - 16:
        raise ContextOverflow("Model context window was exhausted; results cannot be reliably scored")
    if max_tokens and payload.get("eval_count", 0) >= max_tokens:
        raise ValueError("Model output hit the token limit")
    text = payload["response"]
    if not json_mode:
        return text
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Model returned invalid JSON") from exc


def embed(texts):
    """Embed a list of strings in batches of 32."""
    vectors = []
    for start in range(0, len(texts), 32):
        body = {"model": config.embed_model(), "input": texts[start:start + 32], "options": embedding_options()}
        vectors.extend(post("/api/embed", body, base=config.embed_url())["embeddings"])
    return vectors
