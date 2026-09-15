from __future__ import annotations

import importlib.util
import re
from collections.abc import Callable

from app.services.text import split_text

MODEL_ID = "facebook/m2m100_418M"
M2M_LANGUAGE_CODES = {
    "ar": "ar",
    "da": "da",
    "de": "de",
    "el": "el",
    "en": "en",
    "en-gb": "en",
    "es": "es",
    "fi": "fi",
    "fr": "fr",
    "he": "he",
    "hi": "hi",
    "it": "it",
    "ja": "ja",
    "ko": "ko",
    "ms": "ms",
    "nl": "nl",
    "no": "no",
    "pl": "pl",
    "pt": "pt",
    "pt-br": "pt",
    "ru": "ru",
    "sv": "sv",
    "sw": "sw",
    "tr": "tr",
    "zh": "zh",
}

# M2M100 often copies newer English job/creator labels instead of translating
# them. Expanding those labels into plain English gives the model enough
# semantic context to produce native target-language wording.
SOURCE_TERM_EXPANSIONS = {
    "vloggers": "video content creators",
    "vlogger": "video content creator",
    "youtubers": "YouTube video creators",
    "youtuber": "YouTube video creator",
    "influencers": "social media content creators",
    "influencer": "social media content creator",
    "streamers": "live video creators",
    "streamer": "live video creator",
    "podcasters": "hosts of online audio shows",
    "podcaster": "host of an online audio show",
}
_SOURCE_TERM_PATTERN = re.compile(
    rf"\b({'|'.join(map(re.escape, SOURCE_TERM_EXPANSIONS))})\b",
    flags=re.IGNORECASE,
)
_TRANSLATION_BOUNDARY = re.compile(r"(?<=[.!?。！？।])\s*")
_TARGET_SCRIPT_PATTERNS = {
    "ar": re.compile(r"[\u0600-\u06ff]"),
    "hi": re.compile(r"[\u0900-\u097f]"),
    "ja": re.compile(r"[\u3040-\u30ff\u3400-\u9fff]"),
    "ko": re.compile(r"[\uac00-\ud7af]"),
    "zh": re.compile(r"[\u3400-\u9fff]"),
}


def expand_translation_terms(text: str) -> str:
    """Rewrite English loanwords that M2M100 commonly copies unchanged."""

    return _SOURCE_TERM_PATTERN.sub(
        lambda match: SOURCE_TERM_EXPANSIONS[match.group(0).lower()],
        text,
    )


def _translation_chunks(text: str) -> list[str]:
    chunks = []
    for sentence in _TRANSLATION_BOUNDARY.split(text):
        if sentence.strip():
            chunks.extend(split_text(sentence, max_characters=450))
    return chunks


def _is_mostly_target_script(text: str, target_code: str) -> bool:
    pattern = _TARGET_SCRIPT_PATTERNS.get(target_code)
    if pattern is None:
        return False
    letters = [character for character in text if character.isalpha()]
    if not letters:
        return False
    target_letters = sum(bool(pattern.fullmatch(character)) for character in letters)
    return target_letters / len(letters) >= 0.25


class LocalTranslator:
    """Translate English text with a lazily loaded local M2M100 model."""

    def __init__(self) -> None:
        self._tokenizer = None
        self._model = None
        self._device = "cpu"

    @property
    def available(self) -> bool:
        return (
            importlib.util.find_spec("sentencepiece") is not None
            and importlib.util.find_spec("transformers") is not None
        )

    def _load(self):
        if self._model is not None and self._tokenizer is not None:
            return self._tokenizer, self._model
        if not self.available:
            raise RuntimeError(
                "Local translation is not installed. Run: uv sync --extra dev --extra kokoro"
            )

        import torch
        from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if self._device == "cuda" else torch.float32
        self._tokenizer = M2M100Tokenizer.from_pretrained(MODEL_ID)
        self._model = M2M100ForConditionalGeneration.from_pretrained(
            MODEL_ID,
            torch_dtype=dtype,
        ).to(self._device)
        self._model.eval()
        return self._tokenizer, self._model

    def translate(
        self,
        text: str,
        target_language: str,
        progress: Callable[[int], None] | None = None,
    ) -> str:
        target_code = M2M_LANGUAGE_CODES.get(target_language)
        if target_code is None:
            raise ValueError(f"Local translation does not support '{target_language}'.")
        if target_code == "en":
            return text

        normalized_text = expand_translation_terms(text)
        chunks = _translation_chunks(normalized_text)
        translations: list[str] = []
        tokenizer = None
        model = None
        for index, chunk in enumerate(chunks):
            if _is_mostly_target_script(chunk, target_code):
                translations.append(chunk)
            else:
                import torch

                if tokenizer is None or model is None:
                    tokenizer, model = self._load()
                    tokenizer.src_lang = "en"
                encoded = tokenizer(
                    chunk,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512,
                ).to(self._device)
                with torch.inference_mode():
                    generated = model.generate(
                        **encoded,
                        forced_bos_token_id=tokenizer.get_lang_id(target_code),
                        max_new_tokens=512,
                    )
                translations.append(tokenizer.batch_decode(generated, skip_special_tokens=True)[0])
            if progress:
                progress(round((index + 1) / len(chunks) * 100))
        return "\n\n".join(translations)
