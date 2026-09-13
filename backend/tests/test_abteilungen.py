"""Personen in mehreren Abteilungen und die Zustaendigkeit der Materialverwalter."""

from app import models
from app.security import hash_secret
from app.zustaendigkeit import sichtbare_abteilungen


def _abteilung(client, admin_headers, name):
    r = client.post("/api/v1/organizations", json={"name": name}, headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


def _artikel(client, admin_headers, db_session, org_id=None, name="Testartikel"):
    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "sonstiges").first()
    typ = client.post("/api/v1/types", json={"name": name, "category_id": kat.id},
                      headers=admin_headers).json()
    return client.post("/api/v1/articles",
                       json={"category_id": kat.id, "type_id": typ["id"],
                             "organization_id": org_id},
                       headers=admin_headers).json()


def _verwalter(client, db_session, name, org_id=None):
    db_session.add(models.User(username=name, roles=["verwalter"], active=True,
                               password_hash=hash_secret("egal1234")))
    db_session.commit()
    u = db_session.query(models.User).filter(models.User.username == name).first()
    if org_id is not None:
        db_session.add(models.MaterialManager(user_id=u.id, organization_id=org_id))
        db_session.commit()
    token = client.post("/api/v1/auth/login",
                        json={"username": name, "password": "egal1234"}).json()["access_token"]
    return u, {"Authorization": f"Bearer {token}"}


# --- Mehrere Abteilungen je Person ------------------------------------------

def test_person_kann_mehreren_abteilungen_angehoeren(client, admin_headers):
    a = _abteilung(client, admin_headers, "Bereitschaft Nord")
    b = _abteilung(client, admin_headers, "Jugendrotkreuz Nord")

    p = client.post("/api/v1/persons",
                    json={"first_name": "Mia", "last_name": "Mehrfach",
                          "organization_id": a["id"], "organization_ids": [b["id"]]},
                    headers=admin_headers)
    assert p.status_code == 200, p.text

    geladen = client.get(f"/api/v1/persons/{p.json()['id']}", headers=admin_headers).json()
    assert geladen["organization_id"] == a["id"]           # Haupt-Abteilung
    assert set(geladen["organization_ids"]) == {a["id"], b["id"]}
    assert geladen["organization_names"][0] == "Bereitschaft Nord"


def test_haupt_abteilung_ist_immer_dabei(client, admin_headers):
    a = _abteilung(client, admin_headers, "Haupt A")
    b = _abteilung(client, admin_headers, "Neben B")
    p = client.post("/api/v1/persons",
                    json={"first_name": "Udo", "last_name": "Haupt", "organization_id": a["id"]},
                    headers=admin_headers).json()
    # Nur die Neben-Abteilung schicken - die Haupt-Abteilung darf nicht verlorengehen.
    client.put(f"/api/v1/persons/{p['id']}", json={"organization_ids": [b["id"]]},
               headers=admin_headers)
    geladen = client.get(f"/api/v1/persons/{p['id']}", headers=admin_headers).json()
    assert set(geladen["organization_ids"]) == {a["id"], b["id"]}


def test_abteilung_laesst_sich_wieder_entfernen(client, admin_headers):
    a = _abteilung(client, admin_headers, "Bleibt")
    b = _abteilung(client, admin_headers, "Geht wieder")
    p = client.post("/api/v1/persons",
                    json={"first_name": "Eva", "last_name": "Wechsel",
                          "organization_id": a["id"], "organization_ids": [b["id"]]},
                    headers=admin_headers).json()
    client.put(f"/api/v1/persons/{p['id']}", json={"organization_ids": []}, headers=admin_headers)
    geladen = client.get(f"/api/v1/persons/{p['id']}", headers=admin_headers).json()
    assert geladen["organization_ids"] == [a["id"]]


# --- Zustaendigkeit der Materialverwalter -----------------------------------

def test_ohne_zustaendigkeit_sieht_der_verwalter_alles(client, admin_headers, db_session):
    org = _abteilung(client, admin_headers, "Irgendeine")
    _artikel(client, admin_headers, db_session, org["id"], "Frei sichtbar")
    _u, kopf = _verwalter(client, db_session, "verw_offen")
    assert sichtbare_abteilungen(db_session, _u) is None

    liste = client.get("/api/v1/articles", headers=kopf).json()
    assert liste["total"] >= 1


def test_mit_zustaendigkeit_nur_die_eigene_abteilung(client, admin_headers, db_session):
    meine = _abteilung(client, admin_headers, "Meine Abteilung")
    fremde = _abteilung(client, admin_headers, "Fremde Abteilung")
    eigener = _artikel(client, admin_headers, db_session, meine["id"], "Eigenes Material")
    fremder = _artikel(client, admin_headers, db_session, fremde["id"], "Fremdes Material")

    _u, kopf = _verwalter(client, db_session, "verw_eng", meine["id"])
    assert sichtbare_abteilungen(db_session, _u) == [meine["id"]]

    ids = [a["id"] for a in client.get("/api/v1/articles?limit=500", headers=kopf).json()["items"]]
    assert eigener["id"] in ids
    assert fremder["id"] not in ids

    # Auch der Einzelabruf ist dicht - sonst waere die Liste nur Kosmetik.
    assert client.get(f"/api/v1/articles/{fremder['id']}", headers=kopf).status_code == 404
    assert client.get(f"/api/v1/articles/{eigener['id']}", headers=kopf).status_code == 200
    assert client.get(f"/api/v1/articles/by-number/{fremder['artikelnummer']}",
                      headers=kopf).status_code == 404


def test_material_ohne_abteilung_bleibt_sichtbar(client, admin_headers, db_session):
    meine = _abteilung(client, admin_headers, "Zustaendig hier")
    ohne = _artikel(client, admin_headers, db_session, None, "Noch nicht zugeordnet")
    _u, kopf = _verwalter(client, db_session, "verw_ohne", meine["id"])
    ids = [a["id"] for a in client.get("/api/v1/articles?limit=500", headers=kopf).json()["items"]]
    assert ohne["id"] in ids


def test_personen_bleiben_fuer_alle_sichtbar(client, admin_headers, db_session):
    """Material wird abteilungsuebergreifend ausgegeben - wer nur die eigenen Leute
    saehe, koennte die Ausgabe nicht mehr erledigen."""
    meine = _abteilung(client, admin_headers, "Verwalter-Abteilung")
    fremde = _abteilung(client, admin_headers, "Andere Abteilung")
    client.post("/api/v1/persons",
                json={"first_name": "Fremde", "last_name": "Person", "organization_id": fremde["id"]},
                headers=admin_headers)
    _u, kopf = _verwalter(client, db_session, "verw_personen", meine["id"])

    personen = client.get("/api/v1/persons", headers=kopf).json()
    assert any(p["last_name"] == "Person" for p in personen)


def test_admin_sieht_immer_alles(client, admin_headers, db_session):
    fremde = _abteilung(client, admin_headers, "Nur Admin")
    artikel = _artikel(client, admin_headers, db_session, fremde["id"], "Admin-Sicht")
    db_session.add(models.MaterialManager(
        user_id=db_session.query(models.User).filter(models.User.username == "admin").first().id,
        organization_id=fremde["id"]))
    db_session.commit()
    assert client.get(f"/api/v1/articles/{artikel['id']}", headers=admin_headers).status_code == 200
