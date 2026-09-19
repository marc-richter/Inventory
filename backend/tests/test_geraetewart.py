"""Termin-Erinnerungen an den zustaendigen Geraetewart.

Eine Rundnachricht an alle liest nach der dritten Woche niemand mehr. Deshalb
geht die HU-Erinnerung zusaetzlich an genau den, der fuer das Fahrzeug
zustaendig ist - und zwar mit dem Kennzeichen vorn, denn danach sucht niemand in
der Artikelnummer.
"""

import datetime as dt
import time

import pytest

from app import models, scheduler, security, telegram
from app.database import Base, SessionLocal, engine
from app.settings_helper import set_setting


def _telegram_an(db):
    """Anbindung aktiv, Token gesetzt, Termin-Meldungen eingeschaltet."""
    set_setting(db, "telegram_enabled", "true")
    set_setting(db, "telegram_bot_token", "123:TESTTOKEN")
    set_setting(db, "telegram_notify_events",
                "provisional,inventory,low_stock,request,inspection_due,"
                "damage_loss,maintenance_due")


@pytest.fixture(scope="module")
def echte_db():
    """Datei-Datenbank - der Zeitplaner liest ueber SessionLocal, wie im Betrieb."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def aufbau(echte_db):
    """Fahrzeug mit Geraetewart und einer HU, die in fuenf Tagen faellig ist."""
    stempel = int(time.time() * 1000)
    wart = models.User(username=f"wart_{stempel}", full_name="Gerd Gerätewart",
                       roles=["verwalter"], active=True,
                       password_hash=security.hash_secret("egal1234"),
                       telegram_chat_id=f"chat_{stempel}",
                       telegram_consent_at=dt.datetime.utcnow())
    echte_db.add(wart)
    echte_db.commit()

    kat = models.Category(name=f"Fahrzeuge {stempel}")
    echte_db.add(kat)
    echte_db.commit()
    typ = models.ArticleType(category_id=kat.id, name=f"MTW {stempel}")
    echte_db.add(typ)
    echte_db.commit()
    artikel = models.Article(artikelnummer=f"2026-{stempel % 100000:05d}",
                             category_id=kat.id, type_id=typ.id, is_vehicle=True,
                             license_plate="HN-DRK 4711")
    echte_db.add(artikel)
    echte_db.commit()
    echte_db.add(models.ArticleWarden(article_id=artikel.id, user_id=wart.id))
    echte_db.commit()

    art = models.MaintenanceType(name=f"Hauptuntersuchung {stempel}", interval_months=24)
    echte_db.add(art)
    echte_db.commit()
    echte_db.add(models.MaintenanceReminder(type_id=art.id, days_before=30, urgency="normal"))
    echte_db.add(models.ArticleMaintenance(
        article_id=artikel.id, mtype_id=art.id, active=True,
        due_date=dt.datetime.utcnow() + dt.timedelta(days=5)))
    echte_db.commit()
    yield {"db": echte_db, "wart": wart, "artikel": artikel, "art": art}


def test_erinnerung_geht_an_den_geraetewart(aufbau, monkeypatch):
    gesendet = []
    monkeypatch.setattr(telegram, "notify_event",
                        lambda db, key, text, extra_user_ids=None:
                        gesendet.append((key, text, extra_user_ids)))
    scheduler._run_maintenance_reminders()

    meine = [g for g in gesendet if "HN-DRK 4711" in g[1]]
    assert meine, f"keine Erinnerung zum Fahrzeug verschickt: {gesendet}"
    key, text, extra = meine[0]
    assert key == "maintenance_due"
    # Das Kennzeichen steht vorn, die Artikelnummer daneben.
    assert text.startswith("⏰ Termin fällig: HN-DRK 4711 (")
    assert aufbau["artikel"].artikelnummer in text
    assert "Zuständig: Gerd Gerätewart" in text
    # Und der Zustaendige steht als zusaetzlicher Empfaenger drin.
    assert extra == [aufbau["wart"].id]


def test_ohne_geraetewart_bleibt_es_bei_den_eingestellten_empfaengern(aufbau, monkeypatch):
    db = aufbau["db"]
    db.query(models.ArticleWarden).filter(
        models.ArticleWarden.article_id == aufbau["artikel"].id).delete()
    db.commit()
    db.refresh(aufbau["artikel"])
    # Die Erinnerung wurde noch nicht verschickt - Merker zuruecksetzen.
    am = db.query(models.ArticleMaintenance).filter(
        models.ArticleMaintenance.article_id == aufbau["artikel"].id).first()
    am.reminded = []
    db.commit()

    gesendet = []
    monkeypatch.setattr(telegram, "notify_event",
                        lambda db_, key, text, extra_user_ids=None:
                        gesendet.append((key, text, extra_user_ids)))
    scheduler._run_maintenance_reminders()
    meine = [g for g in gesendet if "HN-DRK 4711" in g[1]]
    assert meine
    assert meine[0][2] is None
    assert "Zuständig" not in meine[0][1]


def test_zusaetzlicher_empfaenger_bekommt_die_nachricht(aufbau, monkeypatch):
    """notify_event stellt dem Geraetewart zu, auch wenn er in der eingestellten
    Empfaengerliste gar nicht steht."""
    db = aufbau["db"]
    _telegram_an(db)
    # Empfaengerliste: ausdruecklich NICHT "alle" und ohne den Geraetewart.
    telegram.set_event_targets(db, "maintenance_due", {"all": False})

    verschickt = []
    monkeypatch.setattr(telegram, "queue_message",
                        lambda token, chat, text: verschickt.append((chat, text)))
    telegram.notify_event(db, "maintenance_due", "HU faellig",
                          extra_user_ids=[aufbau["wart"].id])
    assert [c for c, _t in verschickt] == [aufbau["wart"].telegram_chat_id]


def test_abgeschaltetes_ereignis_erreicht_auch_den_geraetewart_nicht(aufbau, monkeypatch):
    """Hat der Administrator die Termin-Meldungen abgeschaltet, gilt das fuer alle.
    Ein zusaetzlicher Empfaenger ist kein Hintertuerchen."""
    db = aufbau["db"]
    _telegram_an(db)
    set_setting(db, "telegram_notify_events", "provisional,inventory")

    verschickt = []
    monkeypatch.setattr(telegram, "queue_message",
                        lambda token, chat, text: verschickt.append((chat, text)))
    telegram.notify_event(db, "maintenance_due", "HU faellig",
                          extra_user_ids=[aufbau["wart"].id])
    assert verschickt == []


def test_gesperrter_chat_bekommt_auch_als_zusaetzlicher_empfaenger_nichts(aufbau, monkeypatch):
    """Die Sperrliste gilt auch hier - sonst waere sie umgehbar."""
    db = aufbau["db"]
    _telegram_an(db)
    telegram.set_event_targets(db, "maintenance_due", {"all": False})
    telegram.add_blacklist(db, aufbau["wart"].telegram_chat_id)

    verschickt = []
    monkeypatch.setattr(telegram, "queue_message",
                        lambda token, chat, text: verschickt.append((chat, text)))
    telegram.notify_event(db, "maintenance_due", "HU faellig",
                          extra_user_ids=[aufbau["wart"].id])
    assert verschickt == []
    telegram.remove_blacklist(db, aufbau["wart"].telegram_chat_id)


def test_geraetewart_laesst_sich_am_artikel_setzen(client, admin_headers, db_session):
    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "fahrzeuge").first()
    typ = client.post("/api/v1/types", json={"name": "MTW", "category_id": kat.id},
                      headers=admin_headers).json()["id"]
    a = client.post("/api/v1/articles",
                    json={"category_id": kat.id, "type_id": typ, "is_vehicle": True},
                    headers=admin_headers).json()
    assert a["warden_list"] == []

    admin = db_session.query(models.User).filter(models.User.username == "admin").first()
    r = client.put(f"/api/v1/articles/{a['id']}", json={"warden_user_ids": [admin.id]},
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    assert [w["id"] for w in r.json()["warden_list"]] == [admin.id]
    assert r.json()["warden_list"][0]["art"] == "person"
    # Und wieder abwaehlbar.
    r = client.put(f"/api/v1/articles/{a['id']}", json={"warden_user_ids": []},
                   headers=admin_headers)
    assert r.json()["warden_list"] == []
