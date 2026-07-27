import textwrap

from ..normalize import nfc


def apply(text: str, opts: dict) -> str:
    width = opts.get("width", 79)
    return "\n".join(textwrap.fill(ln, width) for ln in nfc(text).splitlines())
