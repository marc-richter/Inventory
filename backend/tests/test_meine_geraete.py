"""Die Liste des Gerätewarts: wofür bin ich zuständig, was steht an."""

import datetime as dt

from app import models, security


def _fahrzeug(client, admin_headers, db_session, kennzeichen):
    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "fahrzeuge").first()
    typ = client.post("/api/v1/types", json={"name": f"MTW {kennzeichen}",
                                             "category_id": kat.id},
                      headers=admin_headers).json()["id"]
    return client.post("/api/v1/articles",
                       json={"category_id": kat.id, "type_id": typ, "is_vehicle": True,
                             "license_plate": kennzeichen}, headers=admin_headers).json()


def _termin(db_session, article_id, name, tage):
    art = models.MaintenanceType(name=name, interval_months=12)
    db_session.add(art)
    db_session.commit()
    db_session.add(models.ArticleMaintenance(
        article_id=article_id, mtype_id=art.id, active=True,
        due_date=dt.datetime.utcnow() + dt.timedelta(days=tage)))
    db_session.commit()
    return art


def test_leere_liste_ohne_zustaendigkeit(client, admin_headers, db_session):
    _fahrzeug(client, admin_headers, db_session, "HN-X 1")
    r = client.get("/api/v1/maintenance/meine-geraete", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["artikel"] == []


def test_eigene_zustaendigkeit_erscheint(client, admin_headers, db_session):
    admin = db_session.query(models.User).filter(models.User.username == "admin").first()
    fz = _fahrzeug(client, admin_headers, db_session, "HN-X 2")
    client.put(f"/api/v1/articles/{fz['id']}", json={"warden_id": admin.id},
               headers=admin_headers)
    _termin(db_session, fz["id"], "Hauptuntersuchung X2", 10)

    d = client.get("/api/v1/maintenance/meine-geraete", headers=admin_headers).json()
    zeile = [a for a in d["artikel"] if a["article_id"] == fz["id"]][0]
    assert zeile["license_plate"] == "HN-X 2"
    assert zeile["ueber_gruppe"] is False
    assert zeile["naechster"]["mtype_name"] == "Hauptuntersuchung X2"
    assert zeile["naechster"]["overdue"] is False
    assert d["faellig"] >= 1


def test_zustaendigkeit_ueber_eine_gruppe(client, admin_headers, db_session):
    """„Fahrzeugwarte" als Gruppe - wer drin ist, sieht das Fahrzeug."""
    admin = db_session.query(models.User).filter(models.User.username == "admin").first()
    gruppe = client.post("/api/v1/groups", json={"name": "Fahrzeugwarte"},
                         headers=admin_headers).json()
    client.post(f"/api/v1/groups/{gruppe['id']}/members", json={"user_id": admin.id},
                headers=admin_headers)
    fz = _fahrzeug(client, admin_headers, db_session, "HN-X 3")
    r = client.put(f"/api/v1/articles/{fz['id']}", json={"warden_group_id": gruppe["id"]},
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["warden_group_name"] == "Fahrzeugwarte"

    d = client.get("/api/v1/maintenance/meine-geraete", headers=admin_headers).json()
    zeile = [a for a in d["artikel"] if a["article_id"] == fz["id"]][0]
    assert zeile["ueber_gruppe"] is True
    assert zeile["gruppe"] == "Fahrzeugwarte"


def test_ueberfaelliges_steht_oben(client, admin_headers, db_session):
    admin = db_session.query(models.User).filter(models.User.username == "admin").first()
    spaet = _fahrzeug(client, admin_headers, db_session, "HN-X 4")
    frueh = _fahrzeug(client, admin_headers, db_session, "HN-X 5")
    ohne = _fahrzeug(client, admin_headers, db_session, "HN-X 6")
    for fz in (spaet, frueh, ohne):
        client.put(f"/api/v1/articles/{fz['id']}", json={"warden_id": admin.id},
                   headers=admin_headers)
    _termin(db_session, spaet["id"], "HU spät", 200)
    _termin(db_session, frueh["id"], "HU überfällig", -5)

    d = client.get("/api/v1/maintenance/meine-geraete", headers=admin_headers).json()
    reihenfolge = [a["article_id"] for a in d["artikel"]]
    assert reihenfolge.index(frueh["id"]) < reihenfolge.index(spaet["id"])
    # Ohne Termin ganz ans Ende - gehört dazu, ist aber nicht dringend.
    assert reihenfolge[-1] == ohne["id"]
    assert d["ueberfaellig"] == 1


def test_andere_sehen_es_nicht(client, admin_headers, db_session):
    admin = db_session.query(models.User).filter(models.User.username == "admin").first()
    fz = _fahrzeug(client, admin_headers, db_session, "HN-X 7")
    client.put(f"/api/v1/articles/{fz['id']}", json={"warden_id": admin.id},
               headers=admin_headers)

    anderer = models.User(username="wart2", roles=["verwalter"], active=True,
                          password_hash=security.hash_secret("egal1234"))
    db_session.add(anderer)
    db_session.commit()
    token = client.post("/api/v1/auth/login",
                        json={"username": "wart2", "password": "egal1234"}).json()["access_token"]
    d = client.get("/api/v1/maintenance/meine-geraete",
                   headers={"Authorization": f"Bearer {token}"}).json()
    assert [a["article_id"] for a in d["artikel"]] == []
