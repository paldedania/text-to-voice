from __future__ import annotations

import re
import unicodedata

_SPACE_RUN = re.compile(r"[\t\f\v ]+")
_PARAGRAPH_RUN = re.compile(r"\n{3,}")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?।])\s+")


def has_visible_text(text: str) -> bool:
    return any(
        not character.isspace() and unicodedata.category(character) not in {"Cc", "Cf"}
        for character in unicodedata.normalize("NFKC", text)
    )


def normalize_text(text: str) -> str:
    """Normalize invisible and repeated whitespace without flattening paragraphs."""
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [_SPACE_RUN.sub(" ", line).strip() for line in text.splitlines()]
    return _PARAGRAPH_RUN.sub("\n\n", "\n".join(lines)).strip()


def split_text(text: str, max_characters: int = 600) -> list[str]:
    """Split text at paragraphs, sentences, then words while preserving order."""
    if max_characters < 40:
        raise ValueError("max_characters must be at least 40")

    normalized = normalize_text(text)
    if not normalized:
        return []

    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current:
            chunks.append(current)
            current = ""

    def add_piece(piece: str) -> None:
        nonlocal current
        piece = piece.strip()
        if not piece:
            return
        candidate = f"{current} {piece}".strip()
        if len(candidate) <= max_characters:
            current = candidate
            return
        flush()
        if len(piece) <= max_characters:
            current = piece
            return
        words = piece.split()
        for word in words:
            candidate_word = f"{current} {word}".strip()
            if len(candidate_word) <= max_characters:
                current = candidate_word
            else:
                flush()
                if len(word) <= max_characters:
                    current = word
                else:
                    for start in range(0, len(word), max_characters):
                        chunks.append(word[start : start + max_characters])

    for paragraph in normalized.split("\n\n"):
        for sentence in _SENTENCE_BOUNDARY.split(paragraph):
            add_piece(sentence)
        flush()

    flush()
    return chunks
