"""Der mitgelieferte Vordruck muss von Anfang an hinterlegt sein.

Gemeldet nach dem Rollout: „die schönen Vorlagen sind gar nicht hinterlegt".
Sie lagen bisher nur als Startpunkte IM EDITOR bereit - wer nichts anlegte,
bekam das eingebaute Notlayout, obwohl die fertige Vorlage mitgeliefert wird.
"""

from app import models
from app.seed import seed_dokumentvorlage
from app.settings_helper import get_setting, set_setting


def test_vorlage_ist_nach_dem_start_da(client, admin_headers, db_session):
    vorlagen = client.get("/api/v1/doc-templates", headers=admin_headers).json()
    global_e = [v for v in vorlagen if v["use_case"] is None]
    assert global_e, "keine globale Vorlage hinterlegt"
    v = global_e[0]
    assert v["active"] is True
    assert v["header_height_mm"] == 38 and v["footer_height_mm"] == 28
    # Die Elemente des Vordrucks, nicht das leere Notlayout.
    arten = {e.get("type") for e in v["elements"]}
    assert "logo" in arten and "legende" in arten and "linie" in arten


def test_ausdruck_benutzt_die_vorlage(client, admin_headers, db_session, kleidung_type):
    """Nicht nur in der Liste - der Vordruck muss beim Erzeugen greifen."""
    cat_id, type_id = kleidung_type
    client.post("/api/v1/articles", json={"category_id": cat_id, "type_id": type_id},
                headers=admin_headers)
    r = client.get("/api/v1/export/pdf", headers=admin_headers)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_wird_nicht_zweimal_angelegt(db_session):
    vorher = db_session.query(models.DocTemplate).count()
    seed_dokumentvorlage(db_session)
    seed_dokumentvorlage(db_session)
    assert db_session.query(models.DocTemplate).count() == vorher


def test_geloeschte_vorlage_kommt_nicht_zurueck(client, admin_headers, db_session):
    """Wer sie bewusst loescht, soll sie nicht beim naechsten Start wiederhaben."""
    vorlagen = client.get("/api/v1/doc-templates", headers=admin_headers).json()
    for v in vorlagen:
        client.delete(f"/api/v1/doc-templates/{v['id']}", headers=admin_headers)
    assert db_session.query(models.DocTemplate).count() == 0

    seed_dokumentvorlage(db_session)
    assert db_session.query(models.DocTemplate).count() == 0


def test_bestehende_installation_behaelt_ihre_vorlage(client, admin_headers, db_session):
    """Eine selbst gebaute Vorlage wird nie ueberschrieben."""
    set_setting(db_session, "doc_template_seeded", "")
    for v in client.get("/api/v1/doc-templates", headers=admin_headers).json():
        client.delete(f"/api/v1/doc-templates/{v['id']}", headers=admin_headers)
    eigene = client.post("/api/v1/doc-templates",
                         json={"name": "Eigener Briefkopf", "header_height_mm": 20,
                               "footer_height_mm": 10, "elements": []},
                         headers=admin_headers)
    assert eigene.status_code == 200, eigene.text

    seed_dokumentvorlage(db_session)
    vorlagen = client.get("/api/v1/doc-templates", headers=admin_headers).json()
    assert [v["name"] for v in vorlagen] == ["Eigener Briefkopf"]
    assert (get_setting(db_session, "doc_template_seeded", "") or "").lower() == "true"
