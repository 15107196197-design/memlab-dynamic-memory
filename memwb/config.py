"""Paths, dataset split and runtime settings.

Settings are read from environment variables at call time so that tests and
scripts can override them without reloading modules.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_FILE = DATA_DIR / "locomo10.json"
FACTS_DIR = DATA_DIR / "facts"
STATES_DIR = DATA_DIR / "states"
IMPORT_DIR = DATA_DIR / "imported"
CACHE_DIR = ROOT / "cache"
EXPORT_DIR = ROOT / "exports"
EVAL_DIR = ROOT / "eval"
WEB_DIR = ROOT / "web"

# Course data subset: 4 development + 2 test conversations, the rest as extension.
SPLIT = {
    "development": ["conv-26", "conv-30", "conv-43", "conv-44"],
    "test": ["conv-41", "conv-42"],
    "extension": ["conv-47", "conv-48", "conv-49", "conv-50"],
}
COURSE_SAMPLES = SPLIT["development"] + SPLIT["test"]

DEFAULT_MODEL = "qwen3.8:27b-q4_K_M"
DEFAULT_EMBED_MODEL = "bge-m3"


def split_of(sample_id):
    return next((name for name, ids in SPLIT.items() if sample_id in ids), "imported")


def answer_model():
    return os.getenv("MEMORY_MODEL", DEFAULT_MODEL)


def extraction_model():
    return os.getenv("EXTRACTION_MODEL", DEFAULT_MODEL)


def embed_model():
    return os.getenv("EMBED_MODEL", DEFAULT_EMBED_MODEL)


def ollama_url():
    return os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")


def embed_url():
    return os.getenv("EMBED_URL", ollama_url()).rstrip("/")


def context_size():
    return int(os.getenv("MEMORY_CONTEXT", "32768"))


def model_slug(model):
    return "".join(c if c.isalnum() or c in "_.-" else "_" for c in model)
