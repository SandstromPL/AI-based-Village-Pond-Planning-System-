"""A minimal, in-memory, process-lifetime circuit breaker.

Every external provider already retries and fails fast within a single
request (see the elevation cascade and Overpass provider). What this adds
is memory *across* requests: if a provider was just seen rate-limited or
unreachable, a brand-new request skips it immediately for a cooldown
window instead of re-discovering the same failure from scratch every
time — this is exactly what repeated testing against a currently
rate-limited provider (e.g. OpenZenith's Cloudflare-level rate limit,
observed to take 60-90s to clear) was paying for on every single request.

Deliberately simple: one dict keyed by provider name, no persistence
(matches this project's existing no-database, in-memory-cache pattern).
"""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_open_until: dict[str, float] = {}


def is_open(provider: str) -> bool:
    """True if `provider` tripped recently and is still in its cooldown."""
    with _lock:
        until = _open_until.get(provider)
    return until is not None and time.monotonic() < until


def trip(provider: str, cooldown_s: float) -> None:
    """Mark `provider` as failing; `is_open` returns True for the next `cooldown_s` seconds."""
    with _lock:
        _open_until[provider] = time.monotonic() + cooldown_s


def clear_all() -> None:
    """Clear all breaker state. Used by tests and operational maintenance."""
    with _lock:
        _open_until.clear()
