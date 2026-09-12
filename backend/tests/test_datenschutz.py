"""Pruefungen zum Datenschutz: Aufbewahrungsfristen, Einwilligung, Selbstauskunft."""

import datetime as dt

import pytest

from app import models, telegram
from app.datenschutz import (ausgabehistorie_anonymisieren, meldungen_anonymisieren,
                             quittungen_loeschen, vorschau)
from app.settings_helper import set_setting


def _artikel(db_session):
    kat = models.Category(name=f"Kat-{dt.datetime.utcnow().timestamp()}")
    db_session.add(kat)
    db_session.commit()
    typ = models.ArticleType(name="Typ", category_id=kat.id)
    db_session.add(typ)
    db_session.commit()
    art = models.Article(category_id=kat.id, type_id=typ.id, artikelnummer=f"A{kat.id}")
    db_session.add(art)
    db_session.commit()
    return art


def _person(db_session, name="Alt"):
    p = models.Person(first_name=name, last_name="Mustermann")
    db_session.add(p)
    db_session.commit()
    return p


# --- Ausgabehistorie --------------------------------------------------------

def test_alte_rueckgabe_verliert_den_personenbezug(db_session):
    art, person = _artikel(db_session), _person(db_session)
    alt = models.IssueRecord(article_id=art.id, person_id=person.id,
                             recipient_name_freetext="Max Mustermann",
                             notes="private Notiz",
                             issue_date=dt.datetime.utcnow() - dt.timedelta(days=500),
                             return_date=dt.datetime.utcnow() - dt.timedelta(days=400))
    db_session.add(alt)
    db_session.commit()
    alt_id = alt.id

    assert ausgabehistorie_anonymisieren(db_session, 365) == 1
    db_session.expire_all()
    geprueft = db_session.get(models.IssueRecord, alt_id)
    # Der Vorgang bleibt, der Personenbezug ist weg.
    assert geprueft is not None
    assert geprueft.person_id is None
    assert geprueft.recipient_name_freetext == ""
    assert geprueft.notes == ""
    assert geprueft.return_date is not None


def test_laufende_ausgabe_bleibt_unberuehrt(db_session):
    art, person = _artikel(db_session), _person(db_session)
    laufend = models.IssueRecord(article_id=art.id, person_id=person.id,
                                 issue_date=dt.datetime.utcnow() - dt.timedelta(days=900))
    db_session.add(laufend)
    db_session.commit()
    assert ausgabehistorie_anonymisieren(db_session, 365) == 0
    db_session.expire_all()
    assert db_session.get(models.IssueRecord, laufend.id).person_id == person.id


def test_junge_rueckgabe_bleibt_unberuehrt(db_session):
    art, person = _artikel(db_session), _person(db_session)
    jung = models.IssueRecord(article_id=art.id, person_id=person.id,
                              issue_date=dt.datetime.utcnow() - dt.timedelta(days=10),
                              return_date=dt.datetime.utcnow() - dt.timedelta(days=5))
    db_session.add(jung)
    db_session.commit()
    assert ausgabehistorie_anonymisieren(db_session, 365) == 0


def test_ohne_frist_passiert_nichts(db_session):
    art, person = _artikel(db_session), _person(db_session)
    db_session.add(models.IssueRecord(
        article_id=art.id, person_id=person.id,
        issue_date=dt.datetime.utcnow() - dt.timedelta(days=5000),
        return_date=dt.datetime.utcnow() - dt.timedelta(days=4000)))
    db_session.commit()
    assert ausgabehistorie_anonymisieren(db_session, 0) == 0


# --- Quittungen -------------------------------------------------------------

def test_alte_quittung_wird_geloescht(db_session):
    person = _person(db_session)
    q = models.Receipt(kind="issue", person_id=person.id, filename="",
                       created_at=dt.datetime.utcnow() - dt.timedelta(days=100))
    db_session.add(q)
    db_session.commit()
    q_id = q.id
    assert quittungen_loeschen(db_session, 30) == 1
    assert db_session.get(models.Receipt, q_id) is None


# --- Schadensmeldungen ------------------------------------------------------

def test_abgeschlossene_meldung_verliert_personenangaben(db_session, admin_user):
    art = _artikel(db_session)
    m = models.DamageLossReport(article_id=art.id, kind="damage", status="done",
                                reporter_user_id=admin_user.id,
                                description="Riss im Ärmel",
                                witnesses="Frau Beispiel",
                                reporter_contact="0170 1234567",
                                created_at=dt.datetime.utcnow() - dt.timedelta(days=800))
    db_session.add(m)
    db_session.commit()
    assert meldungen_anonymisieren(db_session, 365) == 1
    db_session.expire_all()
    geprueft = db_session.get(models.DamageLossReport, m.id)
    assert geprueft.reporter_user_id is None
    assert geprueft.witnesses == ""
    assert geprueft.reporter_contact == ""
    # Der Sachverhalt bleibt erhalten.
    assert geprueft.description == "Riss im Ärmel"


def test_offene_meldung_bleibt_unberuehrt(db_session, admin_user):
    art = _artikel(db_session)
    m = models.DamageLossReport(article_id=art.id, kind="damage", status="open",
                                reporter_user_id=admin_user.id, witnesses="Zeuge",
                                created_at=dt.datetime.utcnow() - dt.timedelta(days=800))
    db_session.add(m)
    db_session.commit()
    assert meldungen_anonymisieren(db_session, 365) == 0


def test_vorschau_zaehlt_ohne_zu_loeschen(db_session):
    art, person = _artikel(db_session), _person(db_session)
    db_session.add(models.IssueRecord(
        article_id=art.id, person_id=person.id,
        issue_date=dt.datetime.utcnow() - dt.timedelta(days=500),
        return_date=dt.datetime.utcnow() - dt.timedelta(days=400)))
    db_session.commit()

    set_setting(db_session, "issue_retention_days", "365")
    try:
        ergebnis = vorschau(db_session)
        assert ergebnis["ausgaben"] >= 1
        # ohne Frist: keine Angabe statt einer Null
        assert ergebnis["quittungen"] is None
        # und wirklich nichts geloescht
        assert db_session.query(models.IssueRecord).filter(
            models.IssueRecord.person_id == person.id).count() == 1
    finally:
        set_setting(db_session, "issue_retention_days", "0")


# --- Telegram-Einwilligung --------------------------------------------------

def test_ohne_einwilligung_keine_telegram_nachricht(db_session, admin_user):
    admin_user.telegram_chat_id = "123456"
    admin_user.telegram_consent_at = None
    db_session.commit()
    assert telegram.consent_required(db_session) is True
    assert telegram.darf_benachrichtigt_werden(db_session, admin_user) is False
    assert telegram.is_allowed(db_session, "123456") is False


def test_mit_einwilligung_erlaubt(db_session, admin_user):
    admin_user.telegram_chat_id = "123456"
    admin_user.telegram_consent_at = dt.datetime.utcnow()
    db_session.commit()
    assert telegram.darf_benachrichtigt_werden(db_session, admin_user) is True
    assert telegram.is_allowed(db_session, "123456") is True


def test_widerruf_wirkt_sofort(client, admin_headers, db_session, admin_user):
    admin_user.telegram_chat_id = "987654"
    admin_user.telegram_consent_at = dt.datetime.utcnow()
    db_session.commit()
    assert telegram.is_allowed(db_session, "987654") is True

    r = client.post("/api/v1/telegram/link/remove", headers=admin_headers)
    assert r.status_code == 200, r.text
    db_session.expire_all()
    assert telegram.is_allowed(db_session, "987654") is False


def test_verknuepfung_ohne_einwilligung_wird_abgelehnt(client, admin_headers, db_session):
    set_setting(db_session, "telegram_self_link_enabled", "true")
    try:
        r = client.post("/api/v1/telegram/link/start", json={"consent": False},
                        headers=admin_headers)
        assert r.status_code == 400, r.text
        assert "Einwilligung" in r.json()["detail"]

        ok = client.post("/api/v1/telegram/link/start", json={"consent": True},
                         headers=admin_headers)
        assert ok.status_code == 200, ok.text
        assert ok.json()["code"]
    finally:
        set_setting(db_session, "telegram_self_link_enabled", "false")


def test_einwilligungstext_wird_mitgeliefert(client, admin_headers):
    r = client.get("/api/v1/telegram/link/status", headers=admin_headers)
    assert r.status_code == 200
    d = r.json()
    assert d["consent_required"] is True
    assert "Telegram" in d["consent_text"] and "widerrufen" in d["consent_text"]


# --- Selbstauskunft ---------------------------------------------------------

def test_selbstauskunft_enthaelt_eigene_daten(client, admin_headers):
    r = client.get("/api/v1/auth/meine-daten", headers=admin_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["konto"]["username"] == "admin"
    assert "hinweis" in d
    # Keine Geheimnisse in der Auskunft.
    text = str(d)
    assert "password_hash" not in text and "pin_hash" not in text


def test_selbstauskunft_braucht_anmeldung(client):
    assert client.get("/api/v1/auth/meine-daten").status_code == 401
