"""Der Volltextindex muss mitziehen, wenn sich ein Verweis ändert.

Im Index stehen nicht nur die Felder des Artikels, sondern auch die Namen von
Typ, Materialklasse und Lagerort. Wurde einer davon umbenannt, stand im Index
weiter der alte Name: die Suche fand den neuen nicht und den alten noch. Das
fällt niemandem auf, denn ein veralteter Index meldet sich nicht - er findet
einfach das Falsche.
"""

import pytest
from sqlalchemy import text

from app import models
from app.routers.system import search


@pytest.fixture(autouse=True)
def index(db_session):
    """Den Volltextindex in der Testdatenbank anlegen.

    Im Betrieb macht das der Serverstart ueber die Datei-Datenbank; die Tests
    arbeiten auf einer eigenen Sitzung, in der es ihn sonst gar nicht gaebe -
    und genau dann laeuft die Suche stillschweigend ueber den Ersatzweg, statt
    den Index zu pruefen.
    """
    search._init_fts(db_session)
    return db_session


def _index_text(db_session, article_id):
    zeile = db_session.execute(text(
        "SELECT type_name, category_name, location_path, kennung "
        "FROM articles_fts WHERE rowid = :id"), {"id": article_id}).fetchone()
    return " | ".join(x or "" for x in (zeile or ()))


def _artikel(client, admin_headers, db_session, name_typ="Einsatzjacke"):
    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "kleidung").first()
    typ = client.post("/api/v1/types", json={"name": name_typ, "category_id": kat.id},
                      headers=admin_headers).json()
    knoten = client.post("/api/v1/storage-nodes",
                         json={"name": "Gerätehaus", "level": "standort"},
                         headers=admin_headers).json()
    art = client.post("/api/v1/articles",
                      json={"category_id": kat.id, "type_id": typ["id"],
                            "storage_node_id": knoten["id"]}, headers=admin_headers).json()
    return art, typ, knoten, kat


def test_typ_umbenennen_zieht_den_index_nach(client, admin_headers, db_session):
    art, typ, _knoten, _kat = _artikel(client, admin_headers, db_session)
    assert "Einsatzjacke" in _index_text(db_session, art["id"])

    r = client.put(f"/api/v1/types/{typ['id']}", json={"name": "Wetterschutzjacke"},
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    drin = _index_text(db_session, art["id"])
    assert "Wetterschutzjacke" in drin
    assert "Einsatzjacke" not in drin


def test_lagerort_umbenennen_zieht_den_index_nach(client, admin_headers, db_session):
    art, _typ, knoten, _kat = _artikel(client, admin_headers, db_session)
    assert "Gerätehaus" in _index_text(db_session, art["id"])

    r = client.put(f"/api/v1/storage-nodes/{knoten['id']}", json={"name": "Feuerwache"},
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    drin = _index_text(db_session, art["id"])
    assert "Feuerwache" in drin
    assert "Gerätehaus" not in drin


def test_materialklasse_umbenennen_zieht_den_index_nach(client, admin_headers, db_session):
    """Mitgelieferte Klassen lassen sich nicht umbenennen - also eine eigene."""
    kat = client.post("/api/v1/categories", json={"name": "Zelte"},
                      headers=admin_headers).json()
    typ = client.post("/api/v1/types", json={"name": "SG 20", "category_id": kat["id"]},
                      headers=admin_headers).json()
    art = client.post("/api/v1/articles",
                      json={"category_id": kat["id"], "type_id": typ["id"]},
                      headers=admin_headers).json()
    assert "Zelte" in _index_text(db_session, art["id"])

    r = client.put(f"/api/v1/categories/{kat['id']}", json={"name": "Unterkunft"},
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    drin = _index_text(db_session, art["id"])
    assert "Unterkunft" in drin
    assert "Zelte" not in drin


def test_suche_findet_den_neuen_namen(client, admin_headers, db_session):
    """Nicht nur die Indexzeile - die Suche selbst muss es finden."""
    art, typ, _knoten, _kat = _artikel(client, admin_headers, db_session, "Einsatzjacke")
    client.put(f"/api/v1/types/{typ['id']}", json={"name": "Wetterschutzjacke"},
               headers=admin_headers)
    r = client.get("/api/v1/search?q=Wetterschutzjacke", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert art["id"] in [a["id"] for a in r.json()["results"]["articles"]]


def test_index_bleibt_bei_einer_zeile_je_artikel(client, admin_headers, db_session):
    """Nachführen heißt löschen und neu schreiben - nicht zweimal schreiben."""
    art, typ, _knoten, _kat = _artikel(client, admin_headers, db_session)
    for name in ("Jacke A", "Jacke B", "Jacke C"):
        client.put(f"/api/v1/types/{typ['id']}", json={"name": name}, headers=admin_headers)
    anzahl = db_session.execute(text(
        "SELECT count(*) FROM articles_fts WHERE rowid = :id"), {"id": art["id"]}).fetchone()[0]
    assert anzahl == 1


def test_neu_aufbauen_stellt_den_index_wieder_her(client, admin_headers, db_session):
    art, _typ, _knoten, _kat = _artikel(client, admin_headers, db_session)
    db_session.execute(text("DELETE FROM articles_fts"))
    db_session.commit()
    assert _index_text(db_session, art["id"]) == ""

    r = client.post("/api/v1/search/reindex", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["artikel"] >= 1
    assert "Einsatzjacke" in _index_text(db_session, art["id"])


def test_fehlende_trigger_werden_beim_start_ergaenzt(client, admin_headers, db_session):
    """Bestandsinstallationen haben die neuen Trigger noch nicht - der Start
    ergänzt sie, ohne den ganzen Index neu zu bauen."""
    art, typ, _knoten, _kat = _artikel(client, admin_headers, db_session)
    for trg in ("article_types_fts_au", "categories_fts_au", "storage_nodes_fts_au"):
        db_session.execute(text(f"DROP TRIGGER IF EXISTS {trg}"))
    db_session.commit()

    search._init_fts(db_session)
    trigger = {r[0] for r in db_session.execute(text(
        "SELECT name FROM sqlite_master WHERE type='trigger'"))}
    assert {"article_types_fts_au", "categories_fts_au", "storage_nodes_fts_au"} <= trigger

    # Und die Nachführung greift ab sofort.
    client.put(f"/api/v1/types/{typ['id']}", json={"name": "Nachgezogen"},
               headers=admin_headers)
    assert "Nachgezogen" in _index_text(db_session, art["id"])
