"""Pytest-Grundgerüst für die Kernabläufe.

Wichtig: Die Umgebungsvariablen werden gesetzt, BEVOR die App importiert wird –
so nutzt die Anwendung eine frische, temporäre SQLite-Datenbank (in einem
Wegwerf-Verzeichnis) und lässt die echten Daten unberührt. Der TestClient wird
ohne `with` verwendet, damit die Startup-Events (Scheduler, Telegram-Poller)
nicht anlaufen – für die Tests wird nur die bereits beim Import angelegte
Seed-Datenbank benötigt.
"""
import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="inventar_test_")
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "admin1234")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

ADMIN_PW = os.environ["DEFAULT_ADMIN_PASSWORD"]


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def _login(client, username, password=None, pin=None):
    body = {"username": username}
    if password is not None:
        body["password"] = password
    if pin is not None:
        body["pin"] = pin
    r = client.post("/api/auth/login", json=body)
    return r


@pytest.fixture(scope="session")
def admin_headers(client):
    r = _login(client, "admin", ADMIN_PW)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def kleidung_type(client, admin_headers):
    """Liefert (category_id, type_id) aus den Seed-Stammdaten."""
    types = client.get("/api/types", headers=admin_headers).json()
    assert types, "Seed sollte Artikeltypen anlegen"
    t = types[0]
    return t["category_id"], t["id"]
