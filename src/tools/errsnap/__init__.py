"""
errsnap
~~~~~~~
Capture exception snapshots — including arbitrary state — to ``.errsnap``
dump files for post-mortem inspection.

Quickstart
----------
::

    import errsnap

    with errsnap.capture(my_state, filename=__file__):
        run_something_risky()

    # Reading a dump
    dump = errsnap.load("my_module_20250310T142301_001.errsnap")
    print(dump.summary())
    inspect_state = dump.state

Public API
----------
- :func:`capture` — context manager; writes dump on exception, always re-raises.
- :func:`load` — load a ``.errsnap`` file into a :class:`DumpFile`.
- :class:`DumpFile` — loaded dump with ``meta``, ``traceback``, and ``state``.
- :class:`DumpMeta` — frozen dataclass with exception and location metadata.
"""

from ._capture import CaptureContext, capture
from ._reader import DumpFile, load
from ._types import DumpMeta

__all__ = [
    "capture",
    "load",
    "CaptureContext",
    "DumpFile",
    "DumpMeta",
]
