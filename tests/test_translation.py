import pytest

from app.services.translation import LocalTranslator


def test_english_target_skips_model_loading() -> None:
    translator = LocalTranslator()
    assert translator.translate("Read this exactly.", "en") == "Read this exactly."
    assert translator.translate("Read this exactly.", "en-gb") == "Read this exactly."
    assert translator._model is None


def test_unknown_translation_language_is_rejected() -> None:
    with pytest.raises(ValueError, match="does not support"):
        LocalTranslator().translate("Test", "unknown")
