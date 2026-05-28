from __future__ import annotations

import pytest

from writer_ai_assistant.prompt_builder import (
    Mode,
    build_instructions,
    build_user_input,
    prompt_spec_for_mode,
)


@pytest.mark.parametrize("mode", list(Mode))
def test_every_mode_has_a_spec(mode: Mode) -> None:
    spec = prompt_spec_for_mode(mode)
    assert spec.instructions.strip()
    assert spec.user_prefix.strip()


def test_build_instructions_includes_system_rules() -> None:
    instructions = build_instructions(Mode.EMAIL)
    assert "professional AI writing assistant" in instructions
    assert "Draft a professional email" in instructions


def test_build_user_input_folds_in_metadata_and_text() -> None:
    out = build_user_input(
        Mode.IMPROVE,
        "make this nicer",
        tone="friendly",
        length="short",
        signature="Best, Sam",
    )
    assert "Tone: friendly" in out
    assert "Length: short" in out
    assert "Signature: Best, Sam" in out
    assert "make this nicer" in out


def test_build_user_input_omits_empty_optional_fields() -> None:
    out = build_user_input(Mode.GRAMMAR, "fix me")
    assert "Signature:" not in out
    assert "Template:" not in out
