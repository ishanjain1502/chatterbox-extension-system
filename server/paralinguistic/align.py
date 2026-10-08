import re

from server.paralinguistic.tags import INDEX_TO_TAG, PARALINGUISTIC_TAGS, TAG_TO_INDEX
from server.paralinguistic.tokens import tokenize_words

_TAG_PATTERN = "|".join(re.escape(tag) for tag in PARALINGUISTIC_TAGS)
_TAG_RE = re.compile(rf"({_TAG_PATTERN})")
_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?")


def _iter_tagged_tokens(tagged: str):
    pos = 0
    text = tagged.strip()
    while pos < len(text):
        tag_match = _TAG_RE.match(text, pos)
        if tag_match:
            yield ("tag", tag_match.group(1))
            pos = tag_match.end()
            continue
        word_match = _WORD_RE.match(text, pos)
        if word_match:
            yield ("word", word_match.group(0))
            pos = word_match.end()
            continue
        pos += 1


def parse_tagged_text(tagged: str) -> tuple[list[str], list[int]]:
    """Return words and gap class indices (length len(words) + 1)."""
    allowed = set(PARALINGUISTIC_TAGS)
    words: list[str] = []
    gap_labels: list[int] = []
    pending_tag = TAG_TO_INDEX["none"]
    for kind, value in _iter_tagged_tokens(tagged):
        if kind == "tag":
            if value not in allowed:
                raise ValueError(f"unsupported tag: {value}")
            pending_tag = TAG_TO_INDEX[value]
            continue
        gap_labels.append(pending_tag)
        pending_tag = TAG_TO_INDEX["none"]
        words.append(value)
    gap_labels.append(pending_tag)
    return words, gap_labels


def align_pair(plain: str, tagged: str) -> list[int] | None:
    plain_words = tokenize_words(plain)
    try:
        tagged_words, gap_labels = parse_tagged_text(tagged)
    except ValueError:
        return None
    if tagged_words != plain_words:
        return None
    if len(gap_labels) != len(plain_words) + 1:
        return None
    return gap_labels


def build_tagged_string(words: list[str], gap_class_indices: list[int]) -> str:
    if len(gap_class_indices) != len(words) + 1:
        raise ValueError("gap_class_indices must have length len(words) + 1")
    parts: list[str] = []
    for index, word in enumerate(words):
        label = gap_class_indices[index]
        if label != 0:
            parts.append(INDEX_TO_TAG[label])
        parts.append(word)
    trailing = gap_class_indices[len(words)]
    if trailing != 0:
        parts.append(INDEX_TO_TAG[trailing])
    return " ".join(parts)
