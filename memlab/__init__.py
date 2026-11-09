"""MemLab: one runtime, many switchable memory implementations.

S1 scope: contracts, registry, run config, manifest, instrumented LLM wrapper and
legacy (B0) method adapters.  Generation behaviour is deliberately unchanged; new
capabilities arrive in later sessions behind the same contracts.
"""

__version__ = "0.1.0"

CONFIG_SCHEMA = "memlab/run-config@1"
MANIFEST_SCHEMA = "memlab/run-manifest@1"

# Importing the package registers the built-in legacy method adapters.
from . import legacy as _legacy  # noqa: E402,F401
