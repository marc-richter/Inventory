"""Pruefungen der Echtzeitanbindung (realtime.py).

Geprueft wird vor allem zweierlei:

* dass eine Aenderung bei einem offenen Fenster tatsaechlich ankommt - und zwar
  auch dann, wenn sie unmittelbar nach dem Verbindungsaufbau passiert (genau
  dort steckte anfangs ein Fehler), und
* dass ueber die Verbindung keine personenbezogenen Daten gehen.

Die Verteilung liest bewusst ueber SessionLocal aus der echten Datei-Datenbank
(die Tests legen sie in einem temporaeren Ordner an), weil jeder Arbeitsprozess
des Servers das genauso tut.
"""

import datetime as dt
import queue
import threading
import time

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from app import models, realtime, security
from app.audit import log_action
from app.database import Base, SessionLocal, engine


@pytest.fixture(scope="module")
def echte_db():
    """Datei-Datenbank, wie sie die Verteilung im Betrieb liest."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def pruefer(echte_db):
    name = f"echtzeit_{int(time.time() * 1000)}"
    user = models.User(username=name, roles=["admin"], active=True,
                       password_hash=security.hash_secret("egal1234"))
    echte_db.add(user)
    echte_db.commit()
    echte_db.refresh(user)
    return user


@pytest.fixture
def ws_client():
    app = FastAPI()

    @app.websocket("/ws")
    async def route(websocket: WebSocket):
        await realtime.websocket_endpoint(websocket)

    return TestClient(app)


def empfange(ws, sekunden=8):
    """Wartet begrenzt auf die naechste Nachricht, damit ein Test nie haengt."""
    kasten = queue.Queue(maxsize=1)

    def holen():
        try:
            kasten.put(ws.receive_json())
        except Exception as exc:  # Verbindungsabbruch ist ein gueltiges Ergebnis
            kasten.put({"typ": "__fehler__", "fehler": repr(exc)})

    threading.Thread(target=holen, daemon=True).start()
    try:
        return kasten.get(timeout=sekunden)
    except queue.Empty:
        return {"typ": "__zeitueberschreitung__"}


# --- Zuordnung der Bereiche -------------------------------------------------

@pytest.mark.parametrize("entity_type,erwartet", [
    ("article", "artikel"),
    ("category", "artikel"),
    ("issue_record", "ausgaben"),
    ("inventory_scan", "inventur"),
    ("damage_report", "meldungen"),
    ("material_request", "anfragen"),
    ("maintenance", "wartung"),
    ("person", "personen"),
    ("voellig_unbekannt", "sonstiges"),
])
def test_bereich_zuordnung(entity_type, erwartet):
    assert realtime.bereich_fuer(entity_type) == erwartet


def test_bereich_faellt_auf_aktion_zurueck():
    assert realtime.bereich_fuer("", "article_create") == "artikel"


def test_vermerk_enthaelt_keine_personenbezogenen_daten():
    vermerk = realtime.ereignis_objekt("article", 7, "article_update")
    spalten = {s.name for s in models.ChangeEvent.__table__.columns}
    assert spalten == {"id", "bereich", "entity_type", "entity_id", "timestamp"}
    assert vermerk.bereich == "artikel"
    assert vermerk.entity_id == 7


def test_vermerk_vertraegt_unsinnige_kennung():
    vermerk = realtime.ereignis_objekt("article", "keine-zahl", "")
    assert vermerk.entity_id is None


# --- Zusammenspiel mit der Protokollierung ----------------------------------

def test_protokolleintrag_erzeugt_vermerk(echte_db, pruefer):
    vorher = echte_db.query(models.ChangeEvent).count()
    log_action(echte_db, pruefer, "article_create", "article", 4711)
    assert echte_db.query(models.ChangeEvent).count() == vorher + 1
    letzter = echte_db.query(models.ChangeEvent).order_by(models.ChangeEvent.id.desc()).first()
    assert letzter.bereich == "artikel"
    assert letzter.entity_id == 4711


def test_aufraeumen_loescht_nur_alte_vermerke(echte_db):
    alt = models.ChangeEvent(bereich="artikel", entity_type="article", entity_id=1,
                             timestamp=dt.datetime.utcnow() - dt.timedelta(hours=5))
    jung = models.ChangeEvent(bereich="artikel", entity_type="article", entity_id=2)
    echte_db.add_all([alt, jung])
    echte_db.commit()
    alt_id, jung_id = alt.id, jung.id   # vor dem Loeschen merken
    geloescht = realtime.alte_ereignisse_loeschen()
    echte_db.expire_all()
    assert geloescht >= 1
    assert echte_db.query(models.ChangeEvent).filter(models.ChangeEvent.id == jung_id).first() is not None
    assert echte_db.query(models.ChangeEvent).filter(models.ChangeEvent.id == alt_id).first() is None


# --- Verbindung -------------------------------------------------------------

def test_ohne_anmeldung_wird_getrennt(ws_client):
    with ws_client.websocket_connect("/ws") as ws:
        ws.send_json({"typ": "abo", "bereiche": ["artikel"]})
        antwort = empfange(ws, 15)
    assert antwort.get("typ") != "bereit"


def test_falscher_schluessel_wird_getrennt(ws_client):
    with ws_client.websocket_connect("/ws") as ws:
        ws.send_json({"typ": "anmeldung", "token": "unsinn"})
        antwort = empfange(ws, 15)
    assert antwort.get("typ") != "bereit"


def test_gesperrter_benutzer_wird_getrennt(ws_client, echte_db):
    name = f"gesperrt_{int(time.time() * 1000)}"
    echte_db.add(models.User(username=name, roles=["lesend"], active=False,
                             password_hash=security.hash_secret("egal1234")))
    echte_db.commit()
    token = security.create_access_token({"sub": name})
    with ws_client.websocket_connect("/ws") as ws:
        ws.send_json({"typ": "anmeldung", "token": token})
        antwort = empfange(ws, 15)
    assert antwort.get("typ") != "bereit"


def test_aenderung_kommt_an_und_bleibt_anonym(ws_client, echte_db, pruefer):
    token = security.create_access_token({"sub": pruefer.username})
    with ws_client.websocket_connect("/ws") as ws:
        ws.send_json({"typ": "anmeldung", "token": token})
        assert empfange(ws).get("typ") == "bereit"

        # Direkt nach dem Verbindungsaufbau - genau hier ging frueher die erste
        # Aenderung verloren, weil der Startpunkt zu spaet bestimmt wurde.
        log_action(echte_db, pruefer, "article_create", "article", 4242)

        nachricht = {}
        ende = time.time() + 12
        while time.time() < ende:
            nachricht = empfange(ws, 6)
            if nachricht.get("typ") in ("aenderung", "__zeitueberschreitung__", "__fehler__"):
                break
        assert nachricht.get("typ") == "aenderung", nachricht
        assert nachricht.get("bereich") == "artikel"
        assert 4242 in nachricht.get("ids", [])
        # Weder Benutzername noch Inhalte duerfen die Verbindung verlassen.
        text = str(nachricht)
        assert pruefer.username not in text
        assert "details" not in text


def test_abonnement_schraenkt_meldungen_ein(ws_client, echte_db, pruefer):
    token = security.create_access_token({"sub": pruefer.username})
    with ws_client.websocket_connect("/ws") as ws:
        ws.send_json({"typ": "anmeldung", "token": token})
        assert empfange(ws).get("typ") == "bereit"
        ws.send_json({"typ": "abo", "bereiche": ["inventur"]})
        bestaetigung = empfange(ws)
        assert bestaetigung.get("bereiche") == ["inventur"]

        log_action(echte_db, pruefer, "article_update", "article", 1)
        log_action(echte_db, pruefer, "inventory_scan", "inventory_scan", 2)

        bereiche = []
        ende = time.time() + 12
        while time.time() < ende:
            m = empfange(ws, 6)
            if m.get("typ") == "aenderung":
                bereiche.append(m["bereich"])
                break
            if m.get("typ") in ("__zeitueberschreitung__", "__fehler__"):
                break
        assert bereiche == ["inventur"], bereiche


def test_herzschlag(ws_client, pruefer):
    token = security.create_access_token({"sub": pruefer.username})
    with ws_client.websocket_connect("/ws") as ws:
        ws.send_json({"typ": "anmeldung", "token": token})
        assert empfange(ws).get("typ") == "bereit"
        ws.send_json({"typ": "ping"})
        antwort = {}
        ende = time.time() + 8
        while time.time() < ende:
            antwort = empfange(ws, 5)
            if antwort.get("typ") in ("pong", "__zeitueberschreitung__", "__fehler__"):
                break
        assert antwort.get("typ") == "pong"
