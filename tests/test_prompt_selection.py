"""
tests/test_prompt_selection.py
───────────────────────────────
Unit tests for app/retrieval/prompts.py

Covers:
  - get_prompt returns a non-empty string for all three valid modes
  - Each mode returns a different prompt
  - Prompts contain the required {context} and {query} placeholders
  - Prompts contain mode-specific persona names
  - get_prompt raises ValueError for unsupported/unknown mode strings
  - Prompts can be .format()'ed without KeyError
"""

import pytest
from app.retrieval.prompts import get_prompt, SUPPORTED_MODES


# ── Basic return value tests ───────────────────────────────────────────────────

@pytest.mark.parametrize("mode", ["prelims", "mains", "current_affairs"])
def test_get_prompt_returns_string(mode):
    prompt = get_prompt(mode)
    assert isinstance(prompt, str)
    assert len(prompt) > 100


@pytest.mark.parametrize("mode", ["prelims", "mains", "current_affairs"])
def test_get_prompt_contains_placeholders(mode):
    prompt = get_prompt(mode)
    assert "{context}" in prompt, f"Mode '{mode}' prompt missing {{context}} placeholder"
    assert "{query}" in prompt,   f"Mode '{mode}' prompt missing {{query}} placeholder"
    assert "{history}" in prompt, f"Mode '{mode}' prompt missing {{history}} placeholder"


# ── Mode differentiation ───────────────────────────────────────────────────────

def test_all_three_prompts_are_different():
    prelims  = get_prompt("prelims")
    mains    = get_prompt("mains")
    current  = get_prompt("current_affairs")
    assert prelims  != mains,   "Prelims and Mains prompts must be distinct"
    assert mains    != current, "Mains and Current Affairs prompts must be distinct"
    assert prelims  != current, "Prelims and Current Affairs prompts must be distinct"


# ── Persona name checks ────────────────────────────────────────────────────────

def test_prelims_prompt_contains_persona():
    assert "UPSC-PREP" in get_prompt("prelims")


def test_mains_prompt_contains_persona():
    assert "UPSC-MAINS-MENTOR" in get_prompt("mains")


def test_current_affairs_prompt_contains_persona():
    assert "UPSC-CURRENT" in get_prompt("current_affairs")


# ── Error handling ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad_mode", ["", "PRELIMS", "essay", "interview", None])
def test_get_prompt_raises_on_invalid_mode(bad_mode):
    with pytest.raises((ValueError, AttributeError)):
        get_prompt(bad_mode)


# ── Format safety ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mode", ["prelims", "mains", "current_affairs"])
def test_prompt_can_be_formatted(mode):
    prompt = get_prompt(mode)
    formatted = prompt.format(
        context="Sample context passage about Article 21 of the Indian Constitution.",
        query="What is Article 21?",
        history="User: Hello\nAssistant: Hi",
    )
    assert "Article 21" in formatted
    assert "Sample context" in formatted


# ── SUPPORTED_MODES tuple ─────────────────────────────────────────────────────

def test_supported_modes_contains_all_modes():
    assert "prelims"         in SUPPORTED_MODES
    assert "mains"           in SUPPORTED_MODES
    assert "current_affairs" in SUPPORTED_MODES
    assert len(SUPPORTED_MODES) == 3
