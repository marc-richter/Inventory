"""Fahrzeuge: Reifen, abweichende Prueferintervalle, Fahrzeugschein."""

import datetime as dt

from app import models


def _fahrzeug(client, admin_headers, db_session, name="MTW"):
    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "fahrzeuge").first()
    typ = client.post("/api/v1/types", json={"name": f"Typ-{name}", "category_id": kat.id},
                      headers=admin_headers).json()
    return client.post("/api/v1/articles",
                       json={"category_id": kat.id, "type_id": typ["id"], "is_vehicle": True,
                             "license_plate": f"KL-RK {name}"},
                       headers=admin_headers).json()


# --- Reifen -----------------------------------------------------------------

def test_reifen_anlegen_und_lesen(client, admin_headers, db_session):
    f = _fahrzeug(client, admin_headers, db_session, "R1")
    r = client.post(f"/api/v1/tires/{f['id']}",
                    json={"position": "vorne links", "target_pressure": "2,5 bar",
                          "dot": "3823", "size": "225/75 R16"},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    liste = client.get(f"/api/v1/tires/{f['id']}", headers=admin_headers).json()
    assert len(liste) == 1
    assert liste[0]["target_pressure"] == "2,5 bar"


def test_alter_wird_aus_der_dot_nummer_errechnet(client, admin_headers, db_session):
    f = _fahrzeug(client, admin_headers, db_session, "R2")
    jahr = dt.datetime.utcnow().year - 3
    dot = f"20{str(jahr)[2:]}"          # KW 20 vor drei Jahren
    client.post(f"/api/v1/tires/{f['id']}", json={"position": "hinten rechts", "dot": dot},
                headers=admin_headers)
    reifen = client.get(f"/api/v1/tires/{f['id']}", headers=admin_headers).json()[0]
    assert reifen["age_years"] is not None
    assert 2.5 <= reifen["age_years"] <= 3.6


def test_unplausible_dot_nummer_liefert_kein_alter(client, admin_headers, db_session):
    f = _fahrzeug(client, admin_headers, db_session, "R3")
    for unsinn in ("", "abc", "9923", "12345"):
        client.post(f"/api/v1/tires/{f['id']}", json={"position": f"Pos {unsinn or 'leer'}",
                                                      "dot": unsinn}, headers=admin_headers)
    for reifen in client.get(f"/api/v1/tires/{f['id']}", headers=admin_headers).json():
        assert reifen["age_years"] is None, reifen["dot"]


def test_beliebige_reifenzahl(client, admin_headers, db_session):
    """Anhaenger mit zwei Raedern, Lkw mit sechs - beides muss gehen."""
    haenger = _fahrzeug(client, admin_headers, db_session, "Haenger")
    for pos in ("links", "rechts"):
        client.post(f"/api/v1/tires/{haenger['id']}", json={"position": pos}, headers=admin_headers)
    assert len(client.get(f"/api/v1/tires/{haenger['id']}", headers=admin_headers).json()) == 2

    lkw = _fahrzeug(client, admin_headers, db_session, "Lkw")
    r = client.post(f"/api/v1/tires/{lkw['id']}/standard?achsen=3", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert len(r.json()) == 6


def test_standardsatz_legt_nichts_doppelt_an(client, admin_headers, db_session):
    f = _fahrzeug(client, admin_headers, db_session, "R4")
    client.post(f"/api/v1/tires/{f['id']}/standard?achsen=2", headers=admin_headers)
    zweiter = client.post(f"/api/v1/tires/{f['id']}/standard?achsen=2", headers=admin_headers)
    assert len(zweiter.json()) == 4


def test_reifen_aendern_und_entfernen(client, admin_headers, db_session):
    f = _fahrzeug(client, admin_headers, db_session, "R5")
    reifen = client.post(f"/api/v1/tires/{f['id']}", json={"position": "vorne links"},
                         headers=admin_headers).json()
    client.put(f"/api/v1/tires/{reifen['id']}", json={"target_pressure": "3,0 bar"},
               headers=admin_headers)
    assert client.get(f"/api/v1/tires/{f['id']}",
                      headers=admin_headers).json()[0]["target_pressure"] == "3,0 bar"
    client.delete(f"/api/v1/tires/{reifen['id']}", headers=admin_headers)
    assert client.get(f"/api/v1/tires/{f['id']}", headers=admin_headers).json() == []


# --- Prueferintervalle je Fahrzeug ------------------------------------------

def test_hu_intervall_je_fahrzeug_abweichend(client, admin_headers, db_session):
    f = _fahrzeug(client, admin_headers, db_session, "HU")
    hu = db_session.query(models.MaintenanceType).filter(
        models.MaintenanceType.name == "Hauptuntersuchung (HU)").first()
    assert hu.interval_months == 24        # Vorgabe der Pruefart

    r = client.post(f"/api/v1/maintenance/article/{f['id']}/schedule",
                    json={"mtype_id": hu.id, "interval_months": 12},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["interval_months"] == 12
    assert r.json()["interval_overridden"] is True

    # Andere Fahrzeuge bleiben bei der Vorgabe.
    anderes = _fahrzeug(client, admin_headers, db_session, "HU2")
    eintraege = client.get(f"/api/v1/maintenance/article/{anderes['id']}",
                           headers=admin_headers).json()
    hu_eintrag = [e for e in eintraege if e["mtype_id"] == hu.id][0]
    assert hu_eintrag["interval_months"] == 24
    assert hu_eintrag["interval_overridden"] is False


def test_beliebiges_intervall_moeglich(client, admin_headers, db_session):
    f = _fahrzeug(client, admin_headers, db_session, "Frei")
    hu = db_session.query(models.MaintenanceType).filter(
        models.MaintenanceType.name == "Hauptuntersuchung (HU)").first()
    r = client.post(f"/api/v1/maintenance/article/{f['id']}/schedule",
                    json={"mtype_id": hu.id, "interval_months": 36}, headers=admin_headers)
    assert r.json()["interval_months"] == 36


def test_intervall_zuruecksetzen(client, admin_headers, db_session):
    f = _fahrzeug(client, admin_headers, db_session, "Reset")
    hu = db_session.query(models.MaintenanceType).filter(
        models.MaintenanceType.name == "Hauptuntersuchung (HU)").first()
    client.post(f"/api/v1/maintenance/article/{f['id']}/schedule",
                json={"mtype_id": hu.id, "interval_months": 12}, headers=admin_headers)
    r = client.post(f"/api/v1/maintenance/article/{f['id']}/schedule",
                    json={"mtype_id": hu.id, "interval_months": 0}, headers=admin_headers)
    assert r.json()["interval_months"] == 24
    assert r.json()["interval_overridden"] is False


def test_sp_laesst_sich_je_fahrzeug_entfernen(client, admin_headers, db_session):
    f = _fahrzeug(client, admin_headers, db_session, "SP")
    sp = db_session.query(models.MaintenanceType).filter(
        models.MaintenanceType.name == "Sicherheitsprüfung (SP)").first()
    vorher = client.get(f"/api/v1/maintenance/article/{f['id']}", headers=admin_headers).json()
    assert any(e["mtype_id"] == sp.id for e in vorher)

    client.post("/api/v1/maintenance/assignments",
                json={"mtype_id": sp.id, "article_id": f["id"], "mode": "exclude"},
                headers=admin_headers)
    nachher = client.get(f"/api/v1/maintenance/article/{f['id']}", headers=admin_headers).json()
    assert not any(e["mtype_id"] == sp.id for e in nachher)


# --- Fahrzeugschein ---------------------------------------------------------

def test_fahrzeugschein_wird_getrennt_gefuehrt(client, admin_headers, db_session):
    import io
    from PIL import Image
    f = _fahrzeug(client, admin_headers, db_session, "Schein")
    puffer = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(puffer, format="PNG")
    puffer.seek(0)
    r = client.post(f"/api/v1/articles/{f['id']}/images?kind=vehicle_doc",
                    files={"file": ("schein.png", puffer, "image/png")}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "vehicle_doc"

    geladen = client.get(f"/api/v1/articles/{f['id']}", headers=admin_headers).json()
    scheine = [i for i in geladen["images"] if i["kind"] == "vehicle_doc"]
    assert len(scheine) == 1
    # Anders als ein Schadensbild darf er ersetzt werden - Fahrzeuge werden umgemeldet.
    assert client.delete(f"/api/v1/articles/images/{scheine[0]['id']}",
                         headers=admin_headers).status_code == 200
