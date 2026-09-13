"""Pruefungen der mitgelieferten Materialklassen.

Wichtig ist vor allem, dass der Abgleich beim Start nichts kaputt macht: er laeuft
bei JEDEM Start und darf weder doppelt anlegen noch ueberschreiben, was der
Administrator geaendert hat.
"""

import pytest

from app import models
from app.seed import seed_system_categories
from app.systemkategorien import FELDER, KATEGORIEN, PRUEFARTEN, STATUS


def _kat(db, system_key):
    return db.query(models.Category).filter(models.Category.system_key == system_key).first()


# --- Anlage -----------------------------------------------------------------

@pytest.mark.parametrize("system_key", [k[0] for k in KATEGORIEN])
def test_jede_systemklasse_ist_vorhanden(db_session, system_key):
    assert _kat(db_session, system_key) is not None


def test_schluessel_hat_schliessanlagen_kennzeichen(db_session):
    assert _kat(db_session, "schluessel").key_system is True


def test_funk_unterklassen_haengen_unter_funk(db_session):
    funk = _kat(db_session, "funk")
    for sub in ("funk_akkus", "funk_zubehoer"):
        assert _kat(db_session, sub).parent_id == funk.id


def test_standardfelder_sind_angelegt(db_session):
    for skey, felder in FELDER.items():
        kat = _kat(db_session, skey)
        vorhanden = {f.system_key for f in db_session.query(models.CustomFieldDef)
                     .filter(models.CustomFieldDef.category_id == kat.id).all()}
        for feld_key, *_ in felder:
            assert f"{skey}.{feld_key}" in vorhanden, f"{skey}.{feld_key} fehlt"


def test_funk_hat_rufname_opta_und_issi_getrennt(db_session):
    kat = _kat(db_session, "funk")
    keys = {f.system_key for f in db_session.query(models.CustomFieldDef)
            .filter(models.CustomFieldDef.category_id == kat.id).all()}
    assert {"funk.rufname", "funk.opta", "funk.issi"} <= keys


def test_behaelter_kennt_beladenes_gewicht(db_session):
    kat = _kat(db_session, "behaelter")
    labels = {f.label for f in db_session.query(models.CustomFieldDef)
              .filter(models.CustomFieldDef.category_id == kat.id).all()}
    assert any("Beladenes Gewicht" in l for l in labels)


# --- Status -----------------------------------------------------------------

def test_kleidungsstatus_gelten_nicht_mehr_fuer_schluessel(db_session):
    kleidung = _kat(db_session, "kleidung")
    schluessel = _kat(db_session, "schluessel")
    for key in ("zu_waschen", "beschaedigt", "infektioes"):
        st = db_session.query(models.StatusDef).filter(models.StatusDef.key == key).first()
        assert st is not None, key
        assert kleidung.id in (st.category_ids or [])
        assert schluessel.id not in (st.category_ids or [])


def test_entwendet_gilt_fuer_alle_klassen(db_session):
    st = db_session.query(models.StatusDef).filter(models.StatusDef.key == "entwendet").first()
    assert st is not None
    assert (st.category_ids or []) == []      # leer = alle Klassen
    assert st.require_note is True
    assert st.issue_policy == "blocked"


@pytest.mark.parametrize("key", [s[0] for s in STATUS if s[4]])
def test_status_mit_notizpflicht(db_session, key):
    st = db_session.query(models.StatusDef).filter(models.StatusDef.key == key).first()
    assert st is not None and st.require_note is True


def test_schluesselstatus_haengen_nur_an_schluesseln(db_session):
    schluessel = _kat(db_session, "schluessel")
    for key in ("schluessel_abgebrochen", "schluessel_verloren", "schluessel_entwertet"):
        st = db_session.query(models.StatusDef).filter(models.StatusDef.key == key).first()
        assert (st.category_ids or []) == [schluessel.id]


# --- Pruefarten -------------------------------------------------------------

def test_pruefarten_sind_den_klassen_zugeordnet(db_session):
    for name, _b, kat_keys, *_rest in PRUEFARTEN:
        art = db_session.query(models.MaintenanceType).filter(
            models.MaintenanceType.name == name).first()
        assert art is not None, name
        for k in kat_keys:
            kat = _kat(db_session, k)
            zuordnung = db_session.query(models.MaintenanceAssignment).filter(
                models.MaintenanceAssignment.mtype_id == art.id,
                models.MaintenanceAssignment.category_id == kat.id).first()
            assert zuordnung is not None, f"{name} -> {k}"


def test_funkpruefung_hat_eine_checkliste(db_session):
    art = db_session.query(models.MaintenanceType).filter(
        models.MaintenanceType.name == "Funk-Funktionsprüfung").first()
    assert art.checklist_id is not None
    punkte = db_session.query(models.InspectionChecklistItem).filter(
        models.InspectionChecklistItem.checklist_id == art.checklist_id).count()
    assert punkte >= 5


def test_hu_steht_auf_24_monaten(db_session):
    art = db_session.query(models.MaintenanceType).filter(
        models.MaintenanceType.name == "Hauptuntersuchung (HU)").first()
    assert art.interval_months == 24


# --- Wiederholter Abgleich --------------------------------------------------

def test_abgleich_legt_beim_zweiten_lauf_nichts_doppelt_an(db_session):
    vorher = (db_session.query(models.Category).count(),
              db_session.query(models.CustomFieldDef).count(),
              db_session.query(models.StatusDef).count(),
              db_session.query(models.MaintenanceType).count())
    seed_system_categories(db_session)
    seed_system_categories(db_session)
    nachher = (db_session.query(models.Category).count(),
               db_session.query(models.CustomFieldDef).count(),
               db_session.query(models.StatusDef).count(),
               db_session.query(models.MaintenanceType).count())
    assert vorher == nachher


def test_abgleich_ueberschreibt_aenderungen_des_admins_nicht(db_session):
    feld = db_session.query(models.CustomFieldDef).filter(
        models.CustomFieldDef.system_key == "funk.issi").first()
    feld.label = "ISSI (Kurzwahl)"
    feld.active = False
    db_session.commit()

    seed_system_categories(db_session)
    db_session.expire_all()

    feld = db_session.query(models.CustomFieldDef).filter(
        models.CustomFieldDef.system_key == "funk.issi").first()
    assert feld.label == "ISSI (Kurzwahl)"
    assert feld.active is False


# --- Schnittstelle ----------------------------------------------------------

def test_nur_admin_darf_klassen_anlegen(client, admin_headers, db_session):
    from app.security import hash_secret
    db_session.add(models.User(username="verw1", roles=["verwalter"], active=True,
                               password_hash=hash_secret("egal1234")))
    db_session.commit()
    token = client.post("/api/v1/auth/login",
                        json={"username": "verw1", "password": "egal1234"}).json()["access_token"]
    verwalter = {"Authorization": f"Bearer {token}"}

    assert client.post("/api/v1/categories", json={"name": "Heimlich"},
                       headers=verwalter).status_code == 403
    assert client.post("/api/v1/categories", json={"name": "Eigene Klasse"},
                       headers=admin_headers).status_code == 200


def test_systemklasse_laesst_sich_nicht_loeschen_oder_umbenennen(client, admin_headers, db_session):
    kat = _kat(db_session, "funk")
    r = client.delete(f"/api/v1/categories/{kat.id}", headers=admin_headers)
    assert r.status_code == 400 and "blenden Sie sie aus" in r.json()["detail"]
    r = client.put(f"/api/v1/categories/{kat.id}", json={"name": "Sprechfunk"}, headers=admin_headers)
    assert r.status_code == 400


def test_systemklasse_laesst_sich_ausblenden(client, admin_headers, db_session):
    kat = _kat(db_session, "sonstiges")
    assert client.put(f"/api/v1/categories/{kat.id}/active", json={"issuable": False},
                      headers=admin_headers).status_code == 200

    sichtbar = [c["id"] for c in client.get("/api/v1/categories", headers=admin_headers).json()]
    assert kat.id not in sichtbar
    alle = [c["id"] for c in client.get("/api/v1/categories?include_hidden=true",
                                        headers=admin_headers).json()]
    assert kat.id in alle

    client.put(f"/api/v1/categories/{kat.id}/active", json={"issuable": True}, headers=admin_headers)


def test_unterklasse_erbt_schliessanlagen_kennzeichen(client, admin_headers, db_session):
    schluessel = _kat(db_session, "schluessel")
    r = client.post("/api/v1/categories",
                    json={"name": "Zylinderschlüssel", "parent_id": schluessel.id},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    neu = db_session.get(models.Category, r.json()["id"])
    assert neu.key_system is True
    assert neu.effective_key_system is True
