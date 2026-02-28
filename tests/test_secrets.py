"""Tests for secrets utility."""

import os
import pytest
from shared.utils.secrets import get_secret


class TestGetSecret:
    def test_returns_env_var(self, monkeypatch):
        monkeypatch.setenv("MY_SECRET", "env_value")
        assert get_secret("MY_SECRET") == "env_value"

    def test_returns_default_when_not_found(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT", raising=False)
        assert get_secret("NONEXISTENT", default="fallback") == "fallback"

    def test_returns_none_when_no_default(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT", raising=False)
        assert get_secret("NONEXISTENT") is None
