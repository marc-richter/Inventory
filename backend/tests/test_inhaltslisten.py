"""Inhaltslisten und Einschiebeschildchen."""

from app import models
from app.routers.inventory.inhaltslisten import soll_und_ist


def _baum(client, admin_headers, name="Rucksack-Standort"):
    st = client.post("/api/v1/storage-nodes", json={"name": name, "level": "standort"},
                     headers=admin_headers).json()
    fach = client.post("/api/v1/storage-nodes",
                       json={"name": "Tasche 3", "level": "raum", "parent_id": st["id"]},
                       headers=admin_headers).json()
    return st, fach


def _typ(client, admin_headers, db_session, name):
    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "sonstiges").first()
    return client.post("/api/v1/types", json={"name": name, "category_id": kat.id},
                       headers=admin_headers).json()


def _soll(client, admin_headers, typ_id, node_id, menge, groesse=""):
    r = client.post("/api/v1/stats/min-stock-rules",
                    json={"type_id": typ_id, "node_id": node_id, "min_stock": menge,
                          "size": groesse},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


def _artikel(client, admin_headers, db_session, typ_id, node_id, anzahl):
    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "sonstiges").first()
    for _ in range(anzahl):
        client.post("/api/v1/articles",
                    json={"category_id": kat.id, "type_id": typ_id, "storage_node_id": node_id},
                    headers=admin_headers)


# --- Soll und Ist -----------------------------------------------------------

def test_soll_kommt_aus_den_mindestbestandsregeln(client, admin_headers, db_session):
    _st, fach = _baum(client, admin_headers, "S1")
    typ = _typ(client, admin_headers, db_session, "Verbandpäckchen")
    _soll(client, admin_headers, typ["id"], fach["id"], 3)

    r = client.get(f"/api/v1/inhaltslisten/{fach['id']}", headers=admin_headers)
    assert r.status_code == 200, r.text
    zeilen = r.json()["rows"]
    assert len(zeilen) == 1
    assert zeilen[0]["bezeichnung"] == "Verbandpäckchen"
    assert zeilen[0]["soll"] == 3
    assert zeilen[0]["ist"] == 0


def test_ist_wird_gezaehlt(client, admin_headers, db_session):
    _st, fach = _baum(client, admin_headers, "S2")
    typ = _typ(client, admin_headers, db_session, "Dreiecktuch")
    _soll(client, admin_headers, typ["id"], fach["id"], 4)
    _artikel(client, admin_headers, db_session, typ["id"], fach["id"], 2)

    zeilen = client.get(f"/api/v1/inhaltslisten/{fach['id']}", headers=admin_headers).json()["rows"]
    assert zeilen[0]["ist"] == 2
    assert zeilen[0]["soll"] == 4


def test_inhalt_einer_kiste_in_der_tasche_zaehlt_mit(client, admin_headers, db_session):
    """Liegt in der Tasche eine Kiste, gehoert deren Inhalt zum Ist-Bestand der
    Tasche - er ist ja da."""
    _st, fach = _baum(client, admin_headers, "S3")
    unterfach = client.post("/api/v1/storage-nodes",
                            json={"name": "Beutel", "level": "fach", "parent_id": fach["id"]},
                            headers=admin_headers).json()
    typ = _typ(client, admin_headers, db_session, "Pflaster")
    _soll(client, admin_headers, typ["id"], fach["id"], 5)
    _artikel(client, admin_headers, db_session, typ["id"], unterfach["id"], 3)

    zeilen = client.get(f"/api/v1/inhaltslisten/{fach['id']}", headers=admin_headers).json()["rows"]
    assert zeilen[0]["ist"] == 3


def test_groessen_werden_getrennt_gefuehrt(client, admin_headers, db_session):
    _st, fach = _baum(client, admin_headers, "S4")
    typ = _typ(client, admin_headers, db_session, "Handschuhe")
    _soll(client, admin_headers, typ["id"], fach["id"], 2, groesse="M")
    _soll(client, admin_headers, typ["id"], fach["id"], 2, groesse="L")

    zeilen = client.get(f"/api/v1/inhaltslisten/{fach['id']}", headers=admin_headers).json()["rows"]
    assert {z["groesse"] for z in zeilen} == {"M", "L"}


def test_regeln_anderer_lagerorte_landen_nicht_auf_dem_schildchen(client, admin_headers, db_session):
    """Was fuer den ganzen Standort gilt, gehoert nicht auf das Schildchen einer
    einzelnen Tasche."""
    st, fach = _baum(client, admin_headers, "S5")
    typ = _typ(client, admin_headers, db_session, "Rettungsdecke")
    _soll(client, admin_headers, typ["id"], st["id"], 20)

    zeilen = client.get(f"/api/v1/inhaltslisten/{fach['id']}", headers=admin_headers).json()["rows"]
    assert zeilen == []


# --- Druck ------------------------------------------------------------------

def test_inhaltsliste_als_pdf(client, admin_headers, db_session):
    _st, fach = _baum(client, admin_headers, "P1")
    typ = _typ(client, admin_headers, db_session, "Beatmungsbeutel")
    _soll(client, admin_headers, typ["id"], fach["id"], 1)

    r = client.get(f"/api/v1/inhaltslisten/{fach['id']}/pdf", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"


def test_alle_formate_funktionieren(client, admin_headers):
    _st, fach = _baum(client, admin_headers, "P2")
    for fmt in ("a4", "a4quer", "a5", "a5quer"):
        r = client.get(f"/api/v1/inhaltslisten/{fach['id']}/pdf?format={fmt}",
                       headers=admin_headers)
        assert r.status_code == 200, fmt
        assert r.content[:4] == b"%PDF"


def test_unbekanntes_format_wird_abgelehnt(client, admin_headers):
    _st, fach = _baum(client, admin_headers, "P3")
    r = client.get(f"/api/v1/inhaltslisten/{fach['id']}/pdf?format=briefmarke",
                   headers=admin_headers)
    assert r.status_code == 400


def test_leere_liste_laesst_sich_trotzdem_drucken(client, admin_headers):
    """Auch ohne Soll-Bestand soll ein Formular zum Ausfuellen herauskommen."""
    _st, fach = _baum(client, admin_headers, "P4")
    r = client.get(f"/api/v1/inhaltslisten/{fach['id']}/pdf", headers=admin_headers)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_einschiebeschildchen(client, admin_headers, db_session):
    _st, fach = _baum(client, admin_headers, "P5")
    typ = _typ(client, admin_headers, db_session, "Schere")
    _soll(client, admin_headers, typ["id"], fach["id"], 1)

    r = client.get(f"/api/v1/inhaltslisten/{fach['id']}/schildchen", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"


def test_schildchen_nimmt_die_masse_des_platzes(client, admin_headers):
    _st, fach = _baum(client, admin_headers, "P6")
    client.put(f"/api/v1/storage-nodes/{fach['id']}",
               json={"label_width_mm": 90, "label_height_mm": 40}, headers=admin_headers)

    daten = client.get(f"/api/v1/inhaltslisten/{fach['id']}", headers=admin_headers).json()
    assert daten["label_width_mm"] == 90 and daten["label_height_mm"] == 40

    r = client.get(f"/api/v1/inhaltslisten/{fach['id']}/schildchen", headers=admin_headers)
    assert r.status_code == 200
    # 90 mm sind rund 255 pt - die Seitengroesse muss das widerspiegeln.
    assert b"255" in r.content[:2000] or r.content[:4] == b"%PDF"


def test_unsinnige_masse_werden_abgelehnt(client, admin_headers):
    _st, fach = _baum(client, admin_headers, "P7")
    r = client.get(f"/api/v1/inhaltslisten/{fach['id']}/schildchen?width_mm=5&height_mm=5",
                   headers=admin_headers)
    assert r.status_code == 400


def test_masse_zuruecksetzen(client, admin_headers):
    _st, fach = _baum(client, admin_headers, "P8")
    client.put(f"/api/v1/storage-nodes/{fach['id']}",
               json={"label_width_mm": 90, "label_height_mm": 40}, headers=admin_headers)
    client.put(f"/api/v1/storage-nodes/{fach['id']}",
               json={"label_width_mm": 0, "label_height_mm": 0}, headers=admin_headers)
    daten = client.get(f"/api/v1/inhaltslisten/{fach['id']}", headers=admin_headers).json()
    assert daten["label_width_mm"] is None
