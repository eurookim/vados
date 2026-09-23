import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ai  # noqa: E402
import database  # noqa: E402


class FakeClient:
    """Stands in for the Anthropic client: returns canned text, records requests."""

    def __init__(self, text="Fake insight.", error=None):
        self.text, self.error = text, error
        self.messages = self
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.text)])


@pytest.fixture
def fake_ai(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(ai, "get_client", lambda: client)
    return client


@pytest.fixture
def db(tmp_path, monkeypatch):
    # Never touch vados.db or a Turso database configured on this machine.
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(database, "_use_turso", lambda: False)
    database.init_db()
    database.get_or_create_profile()
    return database
