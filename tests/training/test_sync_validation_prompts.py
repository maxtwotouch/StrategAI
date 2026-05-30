from src.training.sync_validation_prompts import clip_prompt, normalize_text


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("  a   b\n\t c  ") == "a b c"


def test_clip_prompt_adds_period_when_hard_clipping() -> None:
    text = "x" * 120
    clipped = clip_prompt(text, max_chars=20)
    assert len(clipped) <= 20
    assert clipped.endswith(".")


def test_clip_prompt_prefers_sentence_boundary() -> None:
    text = "first sentence. second sentence is longer"
    clipped = clip_prompt(text, max_chars=25)
    assert clipped.endswith(".")
    assert clipped == "first sentence."

