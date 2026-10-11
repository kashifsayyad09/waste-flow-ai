"""WasteFlow MCP server: narrow, read-only tools over the existing application data layer.

The backend package (`app`) is reused as the shared service layer, so priority logic is never
duplicated. Its location defaults to ../backend and can be overridden with WASTEFLOW_BACKEND_DIR.
"""
import os
import sys
from pathlib import Path

_BACKEND = Path(os.environ.get("WASTEFLOW_BACKEND_DIR") or Path(__file__).resolve().parents[2] / "backend")
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
