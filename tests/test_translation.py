import pytest

from app.services.translation import LocalTranslator, expand_translation_terms


class _Encoded(dict):
    def to(self, _device: str):
        return self


class _RecordingTokenizer:
    def __init__(self, translated_text: str) -> None:
        self.translated_text = translated_text
        self.inputs: list[str] = []
        self.src_lang = ""

    def __call__(self, text: str, **_kwargs) -> _Encoded:
        self.inputs.append(text)
        return _Encoded()

    def get_lang_id(self, _target_code: str) -> int:
        return 0

    def batch_decode(self, _generated, **_kwargs) -> list[str]:
        return [self.translated_text]


class _FakeModel:
    def generate(self, **_kwargs) -> list[int]:
        return [0]


def test_english_target_skips_model_loading() -> None:
    translator = LocalTranslator()
    assert translator.translate("Read this exactly.", "en") == "Read this exactly."
    assert translator.translate("Read this exactly.", "en-gb") == "Read this exactly."
    assert translator._model is None


def test_unknown_translation_language_is_rejected() -> None:
    with pytest.raises(ValueError, match="does not support"):
        LocalTranslator().translate("Test", "unknown")


def test_modern_role_terms_are_expanded_before_translation() -> None:
    translator = LocalTranslator()
    tokenizer = _RecordingTokenizer("我是一个视频内容创作者。")
    translator._tokenizer = tokenizer
    translator._model = _FakeModel()

    translated = translator.translate("I am a vlogger.", "zh")

    assert tokenizer.inputs == ["I am a video content creator."]
    assert translated == "我是一个视频内容创作者。"


def test_term_expansion_preserves_names_and_brands() -> None:
    translator = LocalTranslator()
    tokenizer = _RecordingTokenizer("我的名字是Divyansh。")
    translator._tokenizer = tokenizer
    translator._model = _FakeModel()

    translator.translate(
        "My name is Divyansh. I study at CodingGita. I have a YouTube channel.",
        "zh",
    )

    assert tokenizer.inputs == [
        "My name is Divyansh.",
        "I study at CodingGita.",
        "I have a YouTube channel.",
    ]


def test_mixed_chinese_and_english_translates_only_english_sentence() -> None:
    translator = LocalTranslator()
    tokenizer = _RecordingTokenizer("我在 CodingGita 学习。")
    translator._tokenizer = tokenizer
    translator._model = _FakeModel()

    translated = translator.translate(
        "我的名字是 Divyansh. I am studying at CodingGita.",
        "zh",
    )

    assert tokenizer.inputs == ["I am studying at CodingGita."]
    assert translated == "我的名字是 Divyansh.\n\n我在 CodingGita 学习。"


@pytest.mark.parametrize(
    ("source", "expanded"),
    [
        ("vloggers", "video content creators"),
        ("YouTuber", "YouTube video creator"),
        ("influencer", "social media content creator"),
        ("streamer", "live video creator"),
        ("podcaster", "host of an online audio show"),
    ],
)
def test_common_creator_terms_have_translation_friendly_expansions(
    source: str,
    expanded: str,
) -> None:
    assert expand_translation_terms(source) == expanded
