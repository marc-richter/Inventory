"""Materialklasse Elektrogeraete und die wiederkehrende DGUV-V3-Pruefung."""

from app import models


def _kat(db_session):
    return db_session.query(models.Category).filter(
        models.Category.system_key == "elektrogeraete").first()


def test_klasse_wird_mitgeliefert(db_session):
    kat = _kat(db_session)
    assert kat is not None
    assert kat.name == "Elektrogeräte"
    # Sie ist weder Schliessanlage noch traegt sie eigene Schloesser.
    assert kat.key_system is False
    assert kat.has_locks is False


def test_felder_der_klasse(client, admin_headers, db_session):
    kat = _kat(db_session)
    felder = client.get(f"/api/v1/custom-fields?category_id={kat.id}",
                        headers=admin_headers).json()
    labels = [f["label"] for f in felder]
    for erwartet in ("Hersteller", "Schutzklasse", "Art des Betriebsmittels",
                     "Einsatzumgebung", "Seriennummer"):
        assert erwartet in labels, labels
    schutzklasse = [f for f in felder if f["label"] == "Schutzklasse"][0]
    assert schutzklasse["options"] == ["I", "II", "III"]


def test_dguv_pruefart_haengt_an_der_klasse(client, admin_headers, db_session):
    kat = _kat(db_session)
    art = db_session.query(models.MaintenanceType).filter(
        models.MaintenanceType.name.like("DGUV V3%")).first()
    assert art is not None
    assert art.interval_months == 12
    assert art.kind == "funktion"
    zuordnung = db_session.query(models.MaintenanceAssignment).filter(
        models.MaintenanceAssignment.mtype_id == art.id,
        models.MaintenanceAssignment.category_id == kat.id).first()
    assert zuordnung is not None and zuordnung.mode == "include"


def test_messwerte_werden_beim_abhaken_erfasst(db_session):
    """Ohne Messwerte waere ein DGUV-V3-Protokoll wertlos."""
    art = db_session.query(models.MaintenanceType).filter(
        models.MaintenanceType.name.like("DGUV V3%")).first()
    felder = db_session.query(models.MaintenanceField).filter(
        models.MaintenanceField.type_id == art.id).order_by(
        models.MaintenanceField.position).all()
    labels = [f.label for f in felder]
    assert "Schutzleiterwiderstand (Ω)" in labels
    assert "Isolationswiderstand (MΩ)" in labels
    assert "Prüfende Elektrofachkraft" in labels


def test_checkliste_ist_hinterlegt(db_session):
    art = db_session.query(models.MaintenanceType).filter(
        models.MaintenanceType.name.like("DGUV V3%")).first()
    assert art.checklist_id is not None
    punkte = db_session.query(models.InspectionChecklistItem).filter(
        models.InspectionChecklistItem.checklist_id == art.checklist_id).all()
    texte = " ".join(p.label for p in punkte)
    assert "Sichtprüfung" in texte
    assert "Isolationswiderstand" in texte
    assert "Prüfplakette" in texte


def test_status_nicht_bestanden_sperrt_die_ausgabe(client, admin_headers, db_session):
    kat = _kat(db_session)
    typ = client.post("/api/v1/types", json={"name": "Stromerzeuger", "category_id": kat.id},
                      headers=admin_headers).json()["id"]
    art = client.post("/api/v1/articles", json={"category_id": kat.id, "type_id": typ},
                      headers=admin_headers).json()
    r = client.put(f"/api/v1/articles/{art['id']}/status",
                   json={"status": "elektro_nicht_bestanden",
                         "condition_note": "Isolationswiderstand zu gering"},
                   headers=admin_headers)
    assert r.status_code == 200, r.text

    person = client.post("/api/v1/persons", json={"first_name": "Erika", "last_name": "Muster"},
                         headers=admin_headers).json()
    aus = client.post("/api/v1/issues/issue",
                      json={"article_id": art["id"], "person_id": person["id"]},
                      headers=admin_headers)
    assert aus.status_code == 400
    assert "gesperrt" in aus.json()["detail"].lower()


def test_status_gilt_nur_fuer_elektrogeraete(client, admin_headers, db_session):
    """Der Status darf nicht bei Kleidung in der Auswahl auftauchen."""
    kleidung = db_session.query(models.Category).filter(
        models.Category.system_key == "kleidung").first()
    r = client.get(f"/api/v1/statuses?category_id={kleidung.id}", headers=admin_headers)
    assert r.status_code == 200, r.text
    keys = [s["key"] for s in r.json()]
    assert "elektro_nicht_bestanden" not in keys
