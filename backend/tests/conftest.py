"""Keep every test away from the developer's persistent demo database."""

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEX_DB_PATH", str(tmp_path / "setowa-test.sqlite3"))
