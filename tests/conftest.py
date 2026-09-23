import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402


@pytest.fixture
def db(tmp_path, monkeypatch):
    # Never touch vados.db or a Turso database configured on this machine.
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(database, "_use_turso", lambda: False)
    database.init_db()
    database.get_or_create_profile()
    return database
