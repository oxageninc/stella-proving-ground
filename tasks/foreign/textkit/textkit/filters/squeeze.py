from ..normalize import nfc


def apply(text: str, opts: dict) -> str:
    keep = opts.get("keep_blank", False)
    lines = [ln.rstrip() for ln in nfc(text).splitlines()]
    if keep:
        return "\n".join(lines)
    return "\n".join(ln for ln in lines if ln)
