import unicodedata


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)
