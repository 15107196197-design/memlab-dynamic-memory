"""MemLab: one runtime, many switchable memory implementations.

S1 scope: contracts, registry, run config, manifest, instrumented LLM wrapper and
legacy (B0) method adapters.  Generation behaviour is deliberately unchanged; new
capabilities arrive in later sessions behind the same contracts.
"""

__version__ = "0.1.0"

CONFIG_SCHEMA = "memlab/run-config@1"
MANIFEST_SCHEMA = "memlab/run-manifest@1"

# Importing the package registers the built-in implementations:
# legacy method adapters, the S3 W/S/R modules and the S4 M/U/K modules.
from . import legacy as _legacy  # noqa: E402,F401
from . import write as _write  # noqa: E402,F401
from . import store as _store  # noqa: E402,F401
from . import retrieve as _retrieve  # noqa: E402,F401
from . import merge as _merge  # noqa: E402,F401
from . import use as _use  # noqa: E402,F401
from . import maintenance as _maintenance  # noqa: E402,F401
from . import e2e as _e2e  # noqa: E402,F401
