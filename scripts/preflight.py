#!/usr/bin/env python3
"""Check a model provider before starting an experiment.

    python scripts/preflight.py --config configs/reference-r0.json
    python scripts/preflight.py --provider deepseek --model deepseek-chat \
        --base-url https://api.deepseek.com/v1 --api-key-env DEEPSEEK_API_KEY

Exits 0 when the provider/key/model look ready; 2 with a JSON error otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memlab import config as lab_config, providers


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MemLab provider preflight")
    parser.add_argument("--config", default=str(ROOT / "configs" / "reference-r0.json"))
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key-env", default=None)
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args(argv)
    try:
        config = lab_config.RunConfig.load(args.config)
        environment = dict(config.get("environment") or {})
        llm = dict(environment.get("llm") or {})
        for key, value in (("provider", args.provider), ("model", args.model),
                           ("base_url", args.base_url), ("api_key_env", args.api_key_env)):
            if value:
                llm[key] = value
        environment["llm"] = llm
        result = providers.preflight(llm, timeout=args.timeout)
        print(json.dumps({"ok": True, "llm": result}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
