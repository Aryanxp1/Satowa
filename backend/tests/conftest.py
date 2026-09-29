"""Keep every test away from the developer's persistent demo database."""

import pytest
from pydantic import SecretStr

from app.config import settings


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", SecretStr(""))
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", SecretStr(""))
    monkeypatch.setattr(settings, "LEX_DB_PATH", str(tmp_path / "setowa-test.sqlite3"))
