"""Schluessel: sprechender Name (Alias) und Schliessgruppe."""

from app import models


def _schluessel_kategorie(db_session):
    return db_session.query(models.Category).filter(
        models.Category.system_key == "schluessel").first()


def _typ(client, admin_headers, db_session):
    kat = _schluessel_kategorie(db_session)
    r = client.post("/api/v1/types", json={"name": "Zylinderschlüssel", "category_id": kat.id},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    return kat.id, r.json()["id"]


def test_alias_und_gruppe_werden_gespeichert(client, admin_headers, db_session):
    cat_id, type_id = _typ(client, admin_headers, db_session)
    r = client.post("/api/v1/articles", json={
        "category_id": cat_id, "type_id": type_id,
        "key_serial": "AB-4711",
        "key_alias": "Haupteingang Pfarrheim",
        "key_group": "HN1",
    }, headers=admin_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["key_alias"] == "Haupteingang Pfarrheim"
    assert d["key_group"] == "HN1"
    assert d["is_key"] is True
    # Der Alias tritt NEBEN die Nummer, nicht an ihre Stelle.
    assert d["artikelnummer"]


def test_alias_und_gruppe_sind_aenderbar(client, admin_headers, db_session):
    cat_id, type_id = _typ(client, admin_headers, db_session)
    art = client.post("/api/v1/articles", json={"category_id": cat_id, "type_id": type_id},
                      headers=admin_headers).json()
    r = client.put(f"/api/v1/articles/{art['id']}",
                   json={"key_alias": "Nebeneingang", "key_group": "HN2"},
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["key_alias"] == "Nebeneingang"
    assert r.json()["key_group"] == "HN2"


def test_beide_felder_sind_freiwillig(client, admin_headers, db_session):
    cat_id, type_id = _typ(client, admin_headers, db_session)
    r = client.post("/api/v1/articles", json={"category_id": cat_id, "type_id": type_id},
                    headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["key_alias"] == ""
    assert r.json()["key_group"] == ""


def test_schliessplan_pdf_laesst_sich_erzeugen(client, admin_headers, db_session):
    """Der Schliessplan war ueber die Oberflaeche nicht zu oeffnen - hier wird der
    Endpunkt selbst geprueft, damit ein solcher Ausfall auffaellt."""
    cat_id, type_id = _typ(client, admin_headers, db_session)
    art = client.post("/api/v1/articles", json={
        "category_id": cat_id, "type_id": type_id,
        "key_serial": "S-1", "key_alias": "Tor", "key_group": "HN1"}, headers=admin_headers).json()

    obj = client.post("/api/v1/keys/objects", json={"name": "Gerätehaus"}, headers=admin_headers)
    assert obj.status_code == 200, obj.text
    schliessung = client.post(f"/api/v1/keys/objects/{obj.json()['id']}/locks",
                              json={"name": "Haupttür"}, headers=admin_headers)
    assert schliessung.status_code == 200, schliessung.text
    zuordnung = client.put(f"/api/v1/keys/article/{art['id']}/locks",
                           json={"lock_ids": [schliessung.json()["id"]]}, headers=admin_headers)
    assert zuordnung.status_code == 200, zuordnung.text

    r = client.get("/api/v1/keys/export/pdf", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:4] == b"%PDF"

    r2 = client.get(f"/api/v1/keys/export/pdf?object_id={obj.json()['id']}&with_holders=true",
                    headers=admin_headers)
    assert r2.status_code == 200
    assert r2.content[:4] == b"%PDF"


def test_ausgabeliste_zeigt_alias_und_gruppe(client, admin_headers, db_session):
    cat_id, type_id = _typ(client, admin_headers, db_session)
    art = client.post("/api/v1/articles", json={
        "category_id": cat_id, "type_id": type_id,
        "key_alias": "Werkstatt", "key_group": "WS"}, headers=admin_headers).json()
    person = client.post("/api/v1/persons", json={"first_name": "Ute", "last_name": "Schlüssel"},
                         headers=admin_headers).json()
    client.post("/api/v1/issues/issue", json={"article_id": art["id"], "person_id": person["id"]},
                headers=admin_headers)

    rows = client.get("/api/v1/keys/issued", headers=admin_headers).json()
    treffer = [r for r in rows if r["article_id"] == art["id"]]
    assert treffer, rows
    assert treffer[0]["key_alias"] == "Werkstatt"
    assert treffer[0]["key_group"] == "WS"
