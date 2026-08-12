"""Platform-specific helpers for protocol tests."""

from __future__ import annotations

import sys

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore[assignment,misc]

IS_LINUX = sys.platform.startswith("linux")
HAS_FCNTL = fcntl is not None
