from __future__ import annotations


def test_japanese_phonemizer_initializes_with_bundled_dictionary() -> None:
    from misaki.ja import JAG2P

    phonemizer = JAG2P()
    phonemes, _tokens = phonemizer("こんにちは。")

    assert phonemes
