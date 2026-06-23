"""Tests for the measurement harness (synthetic fixtures only)."""

from __future__ import annotations

from anamnesis.eval import estimate_tokens


def test_estimate_tokens_empty_is_zero():
    assert estimate_tokens("") == 0


def test_estimate_tokens_four_chars_is_one_token():
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_estimate_tokens_is_monotonic():
    assert estimate_tokens("a" * 100) >= estimate_tokens("a" * 40)
