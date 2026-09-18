"""Fahrzeuge muessen ueber ihr Kennzeichen auffindbar sein.

Vorher fand die Suche ein Kennzeichen nur als Lagerort - naemlich den Knoten,
den das Fahrzeug im Baum darstellt - und nie den Artikel selbst. Wer ein
Fahrzeug sucht, tippt aber sein Kennzeichen und nicht die Artikelnummer.
"""

from app import models


def _fahrzeug(client, admin_headers, db_session, kennzeichen="HN-DRK 4711"):
    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "fahrzeuge").first()
    typ = client.post("/api/v1/types", json={"name": f"MTW {kennzeichen}", "category_id": kat.id},
                      headers=admin_headers).json()["id"]
    r = client.post("/api/v1/articles",
                    json={"category_id": kat.id, "type_id": typ, "is_vehicle": True,
                          "license_plate": kennzeichen}, headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_artikelliste_findet_das_kennzeichen(client, admin_headers, db_session):
    fz = _fahrzeug(client, admin_headers, db_session)
    r = client.get("/api/v1/articles?q=HN-DRK", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert [a["id"] for a in r.json()["items"]] == [fz["id"]]


def test_kennzeichen_auch_ohne_trennzeichen(client, admin_headers, db_session):
    """„HNDRK4711" soll „HN-DRK 4711" finden - Trennzeichen fallen beim Tippen
    als Erstes weg."""
    fz = _fahrzeug(client, admin_headers, db_session)
    r = client.get("/api/v1/articles?q=HNDRK4711", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert [a["id"] for a in r.json()["items"]] == [fz["id"]]


def test_globale_suche_findet_das_fahrzeug_als_artikel(client, admin_headers, db_session):
    fz = _fahrzeug(client, admin_headers, db_session, "HN-DRK 1234")
    r = client.get("/api/v1/search?q=HN-DRK%201234", headers=admin_headers)
    assert r.status_code == 200, r.text
    treffer = r.json()["results"]["articles"]
    assert fz["id"] in [a["id"] for a in treffer], r.json()["results"]


def test_suche_findet_auch_fahrgestellnummer_und_schluesselangaben(client, admin_headers,
                                                                   db_session):
    fz = _fahrzeug(client, admin_headers, db_session, "HN-DRK 9999")
    client.put(f"/api/v1/articles/{fz['id']}", json={"vin": "WDB1234567890"},
               headers=admin_headers)
    r = client.get("/api/v1/articles?q=WDB123", headers=admin_headers)
    assert [a["id"] for a in r.json()["items"]] == [fz["id"]]

    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "schluessel").first()
    typ = client.post("/api/v1/types", json={"name": "Zylinder", "category_id": kat.id},
                      headers=admin_headers).json()["id"]
    k = client.post("/api/v1/articles",
                    json={"category_id": kat.id, "type_id": typ,
                          "key_alias": "Haupteingang Pfarrheim", "key_group": "HN1"},
                    headers=admin_headers).json()
    assert [a["id"] for a in client.get("/api/v1/articles?q=Pfarrheim",
                                        headers=admin_headers).json()["items"]] == [k["id"]]
    assert [a["id"] for a in client.get("/api/v1/articles?q=HN1",
                                        headers=admin_headers).json()["items"]] == [k["id"]]


def test_volltextindex_bekommt_die_neue_spalte(db_session):
    """Bestandsinstallationen haben den Index ohne die Kennungs-Spalte. Er muss
    einmal neu aufgebaut werden, sonst findet die Suche dort nie ein Kennzeichen."""
    from sqlalchemy import text
    from app.routers.system import search

    # Index im alten Zustand nachbauen.
    db_session.execute(text("DROP TABLE IF EXISTS articles_fts"))
    for trg in ("articles_ai", "articles_au", "articles_ad"):
        db_session.execute(text(f"DROP TRIGGER IF EXISTS {trg}"))
    db_session.execute(text("""
        CREATE VIRTUAL TABLE articles_fts USING fts5(
            artikelnummer, model, size, properties, remarks,
            type_name, category_name, location_path)
    """))
    db_session.commit()
    spalten = {r[1] for r in db_session.execute(text("PRAGMA table_info(articles_fts)"))}
    assert "kennung" not in spalten

    search._init_fts(db_session)
    spalten = {r[1] for r in db_session.execute(text("PRAGMA table_info(articles_fts)"))}
    assert "kennung" in spalten
