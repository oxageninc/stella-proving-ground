"""Handler protocol.

Describes the shape every command module follows. Nothing is registered
here — see the registry.
"""

from typing import Protocol


class Handler(Protocol):
    def run(self, args: dict, store) -> str: ...
