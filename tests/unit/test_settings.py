from __future__ import annotations
from src.config.settings import Settings


def test_settings_defaults():
    s = Settings()
    assert s.DATABASE_URL.startswith("postgresql+asyncpg://")


def test_autodoc_e2e_defaults_false():
    s = Settings()
    assert s.AUTODOC_E2E is False


def test_autodoc_e2e_env_override(monkeypatch):
    monkeypatch.setenv("AUTODOC_E2E", "1")
    s = Settings()
    assert s.AUTODOC_E2E is True
