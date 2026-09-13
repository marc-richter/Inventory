"""Behaelter: Artikel, die zugleich Lagerort sind.

Geprueft wird vor allem, dass Inhalt und Behaelter zusammenbleiben - beim
Umlagern, beim Ausgeben, beim Zuruecknehmen und bei der Inventur.
"""

from app import models
from app.behaelter import inhalt, knoten_von, teilbaum_ids


def _klasse(db_session, system_key):
    return db_session.query(models.Category).filter(
        models.Category.system_key == system_key).first()


def _typ(client, admin_headers, db_session, system_key, name):
    kat = _klasse(db_session, system_key)
    r = client.post("/api/v1/types", json={"name": name, "category_id": kat.id},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    return kat.id, r.json()["id"]


def _kiste(client, admin_headers, db_session, name="Notfallkiste", parent_node=None):
    cat_id, type_id = _typ(client, admin_headers, db_session, "behaelter", f"Kiste-{name}")
    art = client.post("/api/v1/articles", json={"category_id": cat_id, "type_id": type_id,
                                                "model": name}, headers=admin_headers).json()
    r = client.post(f"/api/v1/articles/{art['id']}/container-node",
                    json={"parent_id": parent_node}, headers=admin_headers)
    assert r.status_code == 200, r.text
    return art, r.json()


def _inhalt_artikel(client, admin_headers, db_session, node_id, anzahl=3):
    cat_id, type_id = _typ(client, admin_headers, db_session, "sonstiges", f"Inhalt-{node_id}")
    out = []
    for _ in range(anzahl):
        a = client.post("/api/v1/articles", json={"category_id": cat_id, "type_id": type_id,
                                                  "storage_node_id": node_id},
                        headers=admin_headers).json()
        out.append(a)
    return out


def _raum(client, admin_headers, name="Lagerraum"):
    st = client.post("/api/v1/storage-nodes", json={"name": f"{name}-Standort", "level": "standort"},
                     headers=admin_headers).json()
    raum = client.post("/api/v1/storage-nodes",
                       json={"name": name, "level": "raum", "parent_id": st["id"]},
                       headers=admin_headers).json()
    return st, raum


# --- Grundlagen -------------------------------------------------------------

def test_artikel_der_klasse_behaelter_gilt_als_behaelter(client, admin_headers, db_session):
    art, node = _kiste(client, admin_headers, db_session)
    geladen = db_session.get(models.Article, art["id"])
    assert geladen.is_container is True
    assert node["level"] == "behaelter"
    assert node["node_article_id"] == art["id"]


def test_artikel_anderer_klasse_per_kennzeichen(client, admin_headers, db_session):
    cat_id, type_id = _typ(client, admin_headers, db_session, "sonstiges", "Rollwagen")
    art = client.post("/api/v1/articles", json={"category_id": cat_id, "type_id": type_id,
                                                "is_container": True}, headers=admin_headers).json()
    assert art["is_container"] is True
    r = client.post(f"/api/v1/articles/{art['id']}/container-node", json={},
                    headers=admin_headers)
    assert r.status_code == 200, r.text


def test_ohne_kennzeichen_kein_lagerort(client, admin_headers, db_session):
    cat_id, type_id = _typ(client, admin_headers, db_session, "sonstiges", "Kein Behälter")
    art = client.post("/api/v1/articles", json={"category_id": cat_id, "type_id": type_id},
                      headers=admin_headers).json()
    r = client.post(f"/api/v1/articles/{art['id']}/container-node", json={}, headers=admin_headers)
    assert r.status_code == 400


def test_kiste_in_kiste_in_kiste(client, admin_headers, db_session):
    _st, raum = _raum(client, admin_headers, "Verschachtelt")
    aussen, aussen_node = _kiste(client, admin_headers, db_session, "Aussen", raum["id"])
    mitte, mitte_node = _kiste(client, admin_headers, db_session, "Mitte", aussen_node["id"])
    innen, innen_node = _kiste(client, admin_headers, db_session, "Innen", mitte_node["id"])
    teile = _inhalt_artikel(client, admin_headers, db_session, innen_node["id"], 2)

    db_session.expire_all()
    aussen_art = db_session.get(models.Article, aussen["id"])
    ids = {a.id for a in inhalt(db_session, aussen_art)}
    # Alles aus den inneren Kisten zaehlt zum Inhalt der aeusseren.
    assert {mitte["id"], innen["id"]} <= ids
    assert {t["id"] for t in teile} <= ids


def test_behaelter_kann_nicht_in_sich_selbst(client, admin_headers, db_session):
    _art, node = _kiste(client, admin_headers, db_session, "Selbstbezug")
    r = client.post(f"/api/v1/articles/{_art['id']}/container-node",
                    json={"parent_id": node["id"]}, headers=admin_headers)
    assert r.status_code == 400 and "sich selbst" in r.json()["detail"]


def test_inhaltsabfrage(client, admin_headers, db_session):
    _art, node = _kiste(client, admin_headers, db_session, "Abfrage")
    _inhalt_artikel(client, admin_headers, db_session, node["id"], 4)
    r = client.get(f"/api/v1/articles/{_art['id']}/container-content", headers=admin_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["is_container"] is True and d["count"] == 4
    assert len(d["items"]) == 4


# --- Ausgabe ----------------------------------------------------------------

def test_kisteninhalt_geht_mit_hinaus(client, admin_headers, db_session):
    art, node = _kiste(client, admin_headers, db_session, "Ausgabe")
    teile = _inhalt_artikel(client, admin_headers, db_session, node["id"], 3)
    person = client.post("/api/v1/persons", json={"first_name": "Kai", "last_name": "Kiste"},
                         headers=admin_headers).json()

    r = client.post("/api/v1/issues/issue",
                    json={"article_id": art["id"], "person_id": person["id"]},
                    headers=admin_headers)
    assert r.status_code == 200, r.text

    db_session.expire_all()
    # Kein Artikel darf noch als verfuegbar dastehen.
    for t in teile:
        geladen = db_session.get(models.Article, t["id"])
        assert geladen.status == "ausgegeben", t["artikelnummer"]
        assert geladen.current_location

    kiste_rec = db_session.query(models.IssueRecord).filter(
        models.IssueRecord.article_id == art["id"]).first()
    assert kiste_rec.container_item_count == 3
    assert kiste_rec.container_complete is True


def test_ausgabeliste_zeigt_nur_die_kiste(client, admin_headers, db_session):
    art, node = _kiste(client, admin_headers, db_session, "Liste")
    _inhalt_artikel(client, admin_headers, db_session, node["id"], 5)
    person = client.post("/api/v1/persons", json={"first_name": "Lea", "last_name": "Liste"},
                         headers=admin_headers).json()
    client.post("/api/v1/issues/issue", json={"article_id": art["id"], "person_id": person["id"]},
                headers=admin_headers)

    offen = client.get("/api/v1/issues/open", headers=admin_headers).json()
    eintraege = [o for o in offen if o["person_id"] == person["id"]]
    assert len(eintraege) == 1, eintraege
    assert eintraege[0]["article_id"] == art["id"]
    assert eintraege[0]["is_container"] is True
    assert eintraege[0]["container_item_count"] == 5
    assert eintraege[0]["container_complete"] is True


def test_unvollstaendige_kiste_wird_vermerkt(client, admin_headers, db_session):
    art, node = _kiste(client, admin_headers, db_session, "Unvollstaendig")
    teile = _inhalt_artikel(client, admin_headers, db_session, node["id"], 3)
    andere = client.post("/api/v1/persons", json={"first_name": "Tom", "last_name": "Vorab"},
                         headers=admin_headers).json()
    # Ein Stueck ist schon woanders unterwegs.
    client.post("/api/v1/issues/issue",
                json={"article_id": teile[0]["id"], "person_id": andere["id"]},
                headers=admin_headers)

    person = client.post("/api/v1/persons", json={"first_name": "Nora", "last_name": "Nachher"},
                         headers=admin_headers).json()
    client.post("/api/v1/issues/issue", json={"article_id": art["id"], "person_id": person["id"]},
                headers=admin_headers)

    db_session.expire_all()
    kiste_rec = db_session.query(models.IssueRecord).filter(
        models.IssueRecord.article_id == art["id"]).first()
    assert kiste_rec.container_item_count == 2
    assert kiste_rec.container_complete is False


def test_ruecknahme_nimmt_den_inhalt_mit(client, admin_headers, db_session):
    art, node = _kiste(client, admin_headers, db_session, "Rueckgabe")
    teile = _inhalt_artikel(client, admin_headers, db_session, node["id"], 3)
    person = client.post("/api/v1/persons", json={"first_name": "Rita", "last_name": "Rueck"},
                         headers=admin_headers).json()
    rec = client.post("/api/v1/issues/issue",
                      json={"article_id": art["id"], "person_id": person["id"]},
                      headers=admin_headers).json()

    r = client.post(f"/api/v1/issues/{rec['id']}/return", json={}, headers=admin_headers)
    assert r.status_code == 200, r.text

    db_session.expire_all()
    for t in teile:
        assert db_session.get(models.Article, t["id"]).status == "verfuegbar"
    assert db_session.get(models.Article, art["id"]).status == "verfuegbar"
    offen = db_session.query(models.IssueRecord).filter(
        models.IssueRecord.return_date.is_(None)).count()
    assert offen == 0


def test_einzelnes_stueck_darf_separat_ausgegeben_werden(client, admin_headers, db_session):
    art, node = _kiste(client, admin_headers, db_session, "Einzeln")
    teile = _inhalt_artikel(client, admin_headers, db_session, node["id"], 2)
    person = client.post("/api/v1/persons", json={"first_name": "Sam", "last_name": "Single"},
                         headers=admin_headers).json()
    r = client.post("/api/v1/issues/issue",
                    json={"article_id": teile[0]["id"], "person_id": person["id"]},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    db_session.expire_all()
    assert db_session.get(models.Article, art["id"]).status == "verfuegbar"


# --- Inventur ---------------------------------------------------------------

def _inventur(client, admin_headers):
    c = client.post("/api/v1/inventory/campaigns",
                    json={"name": "Behälter-Inventur", "scope_type": "full"},
                    headers=admin_headers)
    assert c.status_code == 200, c.text
    cid = c.json()["id"]
    gestartet = client.post(f"/api/v1/inventory/campaigns/{cid}/status?action=start",
                            headers=admin_headers)
    assert gestartet.status_code == 200, gestartet.text
    return cid


def test_kiste_scannen_haengt_sie_in_den_raum(client, admin_headers, db_session):
    _st, raum = _raum(client, admin_headers, "Scanraum")
    art, node = _kiste(client, admin_headers, db_session, "Scannen")
    teile = _inhalt_artikel(client, admin_headers, db_session, node["id"], 3)
    cid = _inventur(client, admin_headers)

    r = client.post(f"/api/v1/inventory/campaigns/{cid}/scan",
                    json={"article_ids": [art["id"]], "storage_node_id": raum["id"]},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["behaelter"][0]["inhalt"] == 3

    db_session.expire_all()
    # Die Kiste liegt jetzt im Raum ...
    assert db_session.get(models.Article, art["id"]).storage_node_id == raum["id"]
    assert knoten_von(db_session, db_session.get(models.Article, art["id"])).parent_id == raum["id"]
    # ... ihr Inhalt aber weiterhin IN der Kiste.
    for t in teile:
        assert db_session.get(models.Article, t["id"]).storage_node_id == node["id"]


def test_kiste_als_ganzes_bestaetigen(client, admin_headers, db_session):
    _st, raum = _raum(client, admin_headers, "Ganzraum")
    art, node = _kiste(client, admin_headers, db_session, "AlsGanzes")
    teile = _inhalt_artikel(client, admin_headers, db_session, node["id"], 4)
    cid = _inventur(client, admin_headers)

    r = client.post(f"/api/v1/inventory/campaigns/{cid}/scan",
                    json={"article_ids": [art["id"]], "storage_node_id": raum["id"],
                          "container_confirm_contents": True},
                    headers=admin_headers)
    assert r.status_code == 200, r.text

    gefunden = {f.article_id for f in db_session.query(models.InventoryFound).filter(
        models.InventoryFound.campaign_id == cid).all()}
    assert art["id"] in gefunden
    for t in teile:
        assert t["id"] in gefunden


def test_ohne_bestaetigung_gilt_nur_die_kiste_als_geprueft(client, admin_headers, db_session):
    _st, raum = _raum(client, admin_headers, "Einzelraum")
    art, node = _kiste(client, admin_headers, db_session, "Einzelpruefung")
    teile = _inhalt_artikel(client, admin_headers, db_session, node["id"], 4)
    cid = _inventur(client, admin_headers)

    client.post(f"/api/v1/inventory/campaigns/{cid}/scan",
                json={"article_ids": [art["id"]], "storage_node_id": raum["id"],
                      "container_confirm_contents": False},
                headers=admin_headers)

    gefunden = {f.article_id for f in db_session.query(models.InventoryFound).filter(
        models.InventoryFound.campaign_id == cid).all()}
    assert art["id"] in gefunden
    for t in teile:
        assert t["id"] not in gefunden


# --- Hilfsfunktionen --------------------------------------------------------

def test_teilbaum_bricht_nicht_bei_tiefe_ab(client, admin_headers, db_session):
    _st, raum = _raum(client, admin_headers, "Tief")
    eltern = raum["id"]
    for i in range(6):
        _a, n = _kiste(client, admin_headers, db_session, f"Ebene{i}", eltern)
        eltern = n["id"]
    ids = teilbaum_ids(db_session, raum["id"])
    assert len(ids) >= 7
