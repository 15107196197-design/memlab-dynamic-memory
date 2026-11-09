"""Run manifest: the reproducibility record for one run (02-architecture 2.9.1).

A manifest answers "which code, which config, which data, which model, which
prompts?" without reading the experiment log.  It is written before a run and
updated as artifacts appear; ``config_hash`` is the join key between manifest,
cache entries and results.

``dataset_hash`` and ``model_fingerprint`` are deliberately cheap (file digest and
configuration digest).  They identify the inputs, not the model weights: a resolved
``digest`` field in the environment block, when available, is included verbatim.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from memwb import config as legacy_config

from . import config as lab_config
from . import llm as lab_llm

MANIFEST_SCHEMA = "memlab/run-manifest@1"


def git_commit(root: str | Path | None = None) -> str:
    """Short HEAD commit, or ``"unknown"`` outside a git checkout."""
    command = ["git", "-C", str(root or lab_config.ROOT), "rev-parse", "--short", "HEAD"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    revision = result.stdout.strip()
    return revision if result.returncode == 0 and revision else "unknown"


def file_hash(path: str | Path, *, chunk_size: int = 1 << 20) -> str:
    """``sha256:<hex>`` of a file's bytes; streaming, so large datasets are fine."""
    hasher = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            hasher.update(chunk)
    return "sha256:" + hasher.hexdigest()


def dataset_hash(path: str | Path | None = None) -> str | None:
    """Digest of the conversation data used by a run (``None`` when absent)."""
    file = Path(path) if path is not None else legacy_config.DATA_FILE
    return file_hash(file) if file.is_file() else None


def prompt_hash(prompt: str) -> str:
    """Digest of one prompt template."""
    return "sha256:" + hashlib.sha256(str(prompt).encode("utf-8")).hexdigest()


def prompts_hash(prompts: Mapping[str, str]) -> str | None:
    """Digest of the whole prompt set (one hash for the manifest, one per key kept)."""
    return lab_config.digest(dict(prompts)) if prompts else None


def _now() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def _as_datetime(created_at: datetime | str | None) -> datetime:
    if isinstance(created_at, datetime):
        return created_at
    if isinstance(created_at, str):
        try:
            return datetime.fromisoformat(created_at)
        except ValueError:
            pass
    return _now()


def new_run_id(config: lab_config.RunConfig | Mapping[str, Any], created_at: datetime | str | None = None) -> str:
    """Readable run id: ``r-YYYYMMDD-HHMM-<preset>``."""
    cfg = lab_config.as_config(config)
    stamp = _as_datetime(created_at).strftime("%Y%m%d-%H%M")
    slug = (cfg.preset or "run").strip().lower()
    slug = "".join(character if character.isalnum() or character in "-_" else "-" for character in slug)
    return f"r-{stamp}-{slug or 'run'}"


@dataclass(frozen=True)
class RunManifest:
    """Everything needed to explain and rerun one configuration."""

    run_id: str
    created_at: str
    git_commit: str
    config_hash: str
    dataset_hash: str | None = None
    model_fingerprint: str | None = None
    seed: int | None = None
    judge: dict[str, Any] = field(default_factory=dict)
    prompt_hash: str | None = None
    prompts: dict[str, str] = field(default_factory=dict)
    split: str | None = None
    preset: str | None = None
    environment: dict[str, Any] = field(default_factory=dict)
    status: str = "created"
    artifacts: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": MANIFEST_SCHEMA,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "git_commit": self.git_commit,
            "config_hash": self.config_hash,
            "dataset_hash": self.dataset_hash,
            "model_fingerprint": self.model_fingerprint,
            "seed": self.seed,
            "judge": self.judge,
            "prompt_hash": self.prompt_hash,
            "prompts": self.prompts,
            "split": self.split,
            "preset": self.preset,
            "environment": self.environment,
            "status": self.status,
            "artifacts": list(self.artifacts),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RunManifest":
        payload = dict(data)
        payload.pop("schema", None)
        known = {item.name for item in fields(cls)}
        unknown = sorted(set(payload) - known)
        if unknown:
            raise ValueError(f"unknown run manifest field(s): {unknown}")
        if payload.get("artifacts") is not None:
            artifacts = payload["artifacts"]
            if not isinstance(artifacts, (list, tuple)):
                raise ValueError("run manifest artifacts must be a list")
            payload["artifacts"] = tuple(artifacts)
        try:
            return cls(**payload)
        except TypeError as exc:
            raise ValueError(f"invalid run manifest: {exc}") from exc

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, ensure_ascii=False) + "\n"

    def write(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_json(), encoding="utf-8")
        return target

    @classmethod
    def read(cls, path: str | Path) -> "RunManifest":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def as_run(self) -> dict[str, Any]:
        """Compact identity used in logs and the SQLite ``runs`` table."""
        return {
            "run_id": self.run_id,
            "config_hash": self.config_hash,
            "dataset_hash": self.dataset_hash,
            "model_fingerprint": self.model_fingerprint,
            "split": self.split,
            "preset": self.preset,
            "seed": self.seed,
            "status": self.status,
        }


def build_manifest(config: lab_config.RunConfig | Mapping[str, Any], *,
                   prompts: Mapping[str, str] | None = None,
                   model_fingerprint: str | None = None,
                   dataset_path: str | Path | None = None,
                   run_id: str | None = None,
                   created_at: datetime | str | None = None,
                   status: str = "created",
                   git_revision: str | None = None) -> RunManifest:
    """Build a manifest for ``config`` without running anything."""
    cfg = lab_config.as_config(config)
    created = _as_datetime(created_at)
    raw_environment = cfg.get("environment")
    environment = raw_environment if isinstance(raw_environment, Mapping) else {}
    prompt_set = {str(key): str(value) for key, value in (prompts or {}).items()}
    judge = dict(environment.get("judge") or {}) if isinstance(environment.get("judge"), Mapping) else {}
    if "judge" in prompt_set:
        judge.setdefault("prompt_hash", prompt_hash(prompt_set["judge"]))
    return RunManifest(
        run_id=run_id or new_run_id(cfg, created),
        created_at=created.isoformat(timespec="seconds"),
        git_commit=git_revision or git_commit(),
        config_hash=cfg.config_hash,
        dataset_hash=dataset_hash(dataset_path),
        model_fingerprint=model_fingerprint or lab_llm.fingerprint_environment(environment),
        seed=cfg.seed,
        judge=judge,
        prompt_hash=prompts_hash(prompt_set),
        prompts=prompt_set,
        split=cfg.split,
        preset=cfg.preset,
        environment=dict(environment),
        status=status,
    )
