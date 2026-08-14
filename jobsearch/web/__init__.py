"""Local web UI for reviewing what the pipeline found and wrote.

    python -m jobsearch web

Loopback only. See `server.py` for why that is not configurable.
"""

from .server import App, WebError, serve

__all__ = ["App", "WebError", "serve"]
