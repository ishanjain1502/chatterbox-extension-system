import re

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?")


def tokenize_words(text: str) -> list[str]:
    return _WORD_RE.findall(text)
