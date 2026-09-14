from app.services.text import normalize_text, split_text


def test_normalize_text_preserves_paragraphs() -> None:
    source = "  First   sentence.\r\n\r\n\r\n Second paragraph.  "
    assert normalize_text(source) == "First sentence.\n\nSecond paragraph."


def test_split_text_respects_limit_and_order() -> None:
    source = "First sentence. Second sentence is longer.\n\nThird paragraph is here."
    chunks = split_text(source, max_characters=40)
    assert all(len(chunk) <= 40 for chunk in chunks)
    assert " ".join(chunks) == "First sentence. Second sentence is longer. Third paragraph is here."


def test_split_text_handles_one_long_word() -> None:
    chunks = split_text("x" * 95, max_characters=40)
    assert [len(chunk) for chunk in chunks] == [40, 40, 15]


def test_split_text_rejects_unusable_limit() -> None:
    try:
        split_text("test", max_characters=20)
    except ValueError as error:
        assert "at least 40" in str(error)
    else:
        raise AssertionError("Expected a ValueError")
