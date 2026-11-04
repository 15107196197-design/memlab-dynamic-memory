"""Candidate retrieval over turn memories: BM25, dense vectors and their RRF fusion."""
import hashlib
import json
import math
import re
import threading
from collections import Counter

from . import config, llm

STOP_WORDS = {
    "a", "an", "the", "and", "or", "of", "to", "is", "are", "was", "were", "be", "been", "being", "what", "who",
    "when", "where", "why", "how", "did", "do", "does", "which", "with", "for", "on", "in", "at", "it", "this",
    "that", "i", "you", "me", "my", "your", "her", "his", "she", "he", "they", "their", "about", "as", "from", "by",
}
_cache_lock = threading.Lock()
_memo = {}  # cache file -> embeddings dict, avoids re-reading large JSON for every query


def tokens(text):
    """Lower-cased word tokens with stop words removed and a light suffix stemmer."""
    out = []
    for word in re.findall(r"[a-z0-9]+|[一-鿿]", str(text).lower()):
        if word in STOP_WORDS or (len(word) == 1 and word.isascii()):
            continue
        if len(word) > 5 and word.endswith("ing"):
            word = word[:-3]
        elif len(word) > 5 and word.endswith("ied"):
            word = word[:-3] + "y"
        elif len(word) > 5 and word.endswith("ed"):
            word = word[:-2]
        out.append(word)
    return out


def _search_text(item, facts_by_turn):
    # Extracted facts widen lexical recall; answers still receive the original utterance.
    expanded = " ".join(f"{f['entity']} {f['attribute']} {f['value']} {f.get('event') or ''}" for f in facts_by_turn.get(item["memory_id"], []))
    return f"{item['content']} {item['entity']} {expanded.replace('_', ' ')}"


def bm25(query, items, k=15, facts=None, k1=1.2, b=0.75):
    facts_by_turn = {}
    for fact in facts or []:
        facts_by_turn.setdefault(fact["source_memory_id"], []).append(fact)
    docs = [tokens(_search_text(x, facts_by_turn)) for x in items]
    q = tokens(query)
    df = Counter(t for d in docs for t in set(d))
    avg = sum(map(len, docs)) / max(1, len(docs))
    scored = []
    for i, doc in enumerate(docs):
        counts = Counter(doc)
        score = 0.0
        for term in q:
            f = counts[term]
            if f:
                idf = math.log(1 + (len(docs) - df[term] + 0.5) / (df[term] + 0.5))
                score += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * len(doc) / max(avg, 1)))
        if score:
            scored.append((score, i))
    return [items[i] for _, i in sorted(scored, reverse=True)[:k]]


def _embed_text(item):
    return f"{item['entity']}: {item['content']}"


def _cache_file(sample_id):
    return config.CACHE_DIR / f"embeddings-{sample_id}-{config.model_slug(config.embed_model())}.json"


def embeddings_for(items):
    """Return one vector per item, embedding only items missing from the per-conversation cache."""
    if not items:
        return []
    sample_id = items[0]["source"]["conversation"]
    path = _cache_file(sample_id)
    keys = [hashlib.sha1(_embed_text(x).encode("utf8")).hexdigest() for x in items]
    with _cache_lock:
        cache = _memo.get(path)
        if cache is None:
            cache = json.loads(path.read_text(encoding="utf8")) if path.exists() else {}
            _memo[path] = cache
        missing = [i for i, key in enumerate(keys) if key not in cache]
        if missing:
            vectors = llm.embed([_embed_text(items[i]) for i in missing])
            for i, vec in zip(missing, vectors):
                cache[keys[i]] = vec
            config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(cache), encoding="utf8")
            tmp.replace(path)
    return [cache[key] for key in keys]


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def vector(query, items, k=15, query_vector=None):
    if not items:
        return []
    matrix = embeddings_for(items)
    q = query_vector or llm.embed([query])[0]
    scores = [_cosine(q, v) for v in matrix]
    return [items[i] for i in sorted(range(len(items)), key=scores.__getitem__, reverse=True)[:k]]


def rrf(rankings, k=15, constant=60):
    """Reciprocal rank fusion of several ranked lists of memories."""
    scores, lookup = {}, {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, 1):
            mid = item["memory_id"]
            lookup[mid] = item
            scores[mid] = scores.get(mid, 0.0) + 1.0 / (constant + rank)
    return [lookup[m] for m in sorted(scores, key=scores.get, reverse=True)[:k]]


def hybrid(query, items, k=15, facts=None, query_vector=None, depth=None):
    depth = depth or max(k, 30)
    return rrf([vector(query, items, depth, query_vector), bm25(query, items, depth, facts)], k)
