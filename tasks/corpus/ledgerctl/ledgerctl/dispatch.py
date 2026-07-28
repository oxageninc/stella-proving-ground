"""Legacy dispatch shim.

Pre-registry entry point. `main` no longer consults this; it is kept so the
2019 import scripts keep importing cleanly.
"""

LEGACY_ROUTES: dict = {}


def route(name: str):
    """Return the legacy handler for `name`, if one was ever registered."""
    return LEGACY_ROUTES.get(name)
