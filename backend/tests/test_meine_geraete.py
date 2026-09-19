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
    client.put(f"/api/v1/articles/{fz['id']}", json={"warden_user_ids": [admin.id]},
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
    r = client.put(f"/api/v1/articles/{fz['id']}", json={"warden_group_ids": [gruppe["id"]]},
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    assert [w["name"] for w in r.json()["warden_list"]] == ["Fahrzeugwarte"]

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
        client.put(f"/api/v1/articles/{fz['id']}", json={"warden_user_ids": [admin.id]},
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
    client.put(f"/api/v1/articles/{fz['id']}", json={"warden_user_ids": [admin.id]},
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


# --------------------------- Mehrere Zuständige -----------------------------

def _gruppe(client, admin_headers, name, mitglieder=()):
    g = client.post("/api/v1/groups", json={"name": name}, headers=admin_headers).json()
    for uid in mitglieder:
        client.post(f"/api/v1/groups/{g['id']}/members", json={"user_id": uid},
                    headers=admin_headers)
    return g


def test_mehrere_personen_und_gruppen_gleichzeitig(client, admin_headers, db_session):
    """Hauptverantwortlicher, Vertreter und die Gruppe der Fahrzeugwarte -
    alles an einem Fahrzeug."""
    admin = db_session.query(models.User).filter(models.User.username == "admin").first()
    vertreter = models.User(username="vertreter", roles=["verwalter"], active=True,
                            password_hash=security.hash_secret("egal1234"))
    db_session.add(vertreter)
    db_session.commit()
    g1 = _gruppe(client, admin_headers, "Fahrzeugwarte M")
    g2 = _gruppe(client, admin_headers, "Zugführer M")

    fz = _fahrzeug(client, admin_headers, db_session, "HN-M 1")
    r = client.put(f"/api/v1/articles/{fz['id']}",
                   json={"warden_user_ids": [admin.id, vertreter.id],
                         "warden_group_ids": [g1["id"], g2["id"]]}, headers=admin_headers)
    assert r.status_code == 200, r.text
    liste = r.json()["warden_list"]
    assert len(liste) == 4
    # Personen zuerst, dann Gruppen - der Hauptverantwortliche steht oben.
    assert [w["art"] for w in liste] == ["person", "person", "gruppe", "gruppe"]
    assert {w["name"] for w in liste if w["art"] == "gruppe"} == \
        {"Fahrzeugwarte M", "Zugführer M"}


def test_einzelne_zustaendigkeit_entfernen_laesst_die_anderen_stehen(
        client, admin_headers, db_session):
    admin = db_session.query(models.User).filter(models.User.username == "admin").first()
    g = _gruppe(client, admin_headers, "Fahrzeugwarte N")
    fz = _fahrzeug(client, admin_headers, db_session, "HN-M 2")
    client.put(f"/api/v1/articles/{fz['id']}",
               json={"warden_user_ids": [admin.id], "warden_group_ids": [g["id"]]},
               headers=admin_headers)

    # Nur die Personen neu setzen - die Gruppe bleibt unberührt.
    r = client.put(f"/api/v1/articles/{fz['id']}", json={"warden_user_ids": []},
                   headers=admin_headers)
    assert [w["name"] for w in r.json()["warden_list"]] == ["Fahrzeugwarte N"]


def test_alle_zustaendigen_werden_benachrichtigt(client, admin_headers, db_session):
    """Wer nicht in der Liste steht, bekommt keine Erinnerung - also müssen alle
    hinein, Personen wie Gruppenmitglieder."""
    from app import telegram

    admin = db_session.query(models.User).filter(models.User.username == "admin").first()
    mitglied = models.User(username="gruppenmitglied", roles=["verwalter"], active=True,
                           password_hash=security.hash_secret("egal1234"))
    db_session.add(mitglied)
    db_session.commit()
    g = _gruppe(client, admin_headers, "Fahrzeugwarte O", [mitglied.id])
    fz = _fahrzeug(client, admin_headers, db_session, "HN-M 3")
    client.put(f"/api/v1/articles/{fz['id']}",
               json={"warden_user_ids": [admin.id], "warden_group_ids": [g["id"]]},
               headers=admin_headers)

    artikel = db_session.get(models.Article, fz["id"])
    empfaenger = []
    for eintrag in artikel.warden_list:
        if eintrag["art"] == "person":
            empfaenger.append(eintrag["id"])
        else:
            empfaenger.extend(m.user_id for m in db_session.query(models.UserGroupMember)
                              .filter(models.UserGroupMember.group_id == eintrag["id"]).all())
    assert set(empfaenger) == {admin.id, mitglied.id}


def test_liste_zeigt_auch_gemischte_zustaendigkeit(client, admin_headers, db_session):
    admin = db_session.query(models.User).filter(models.User.username == "admin").first()
    g = _gruppe(client, admin_headers, "Fahrzeugwarte P", [admin.id])
    fz = _fahrzeug(client, admin_headers, db_session, "HN-M 4")
    client.put(f"/api/v1/articles/{fz['id']}",
               json={"warden_user_ids": [admin.id], "warden_group_ids": [g["id"]]},
               headers=admin_headers)

    d = client.get("/api/v1/maintenance/meine-geraete", headers=admin_headers).json()
    zeile = [a for a in d["artikel"] if a["article_id"] == fz["id"]][0]
    # Persönlich benannt UND über die Gruppe - die persönliche Nennung gewinnt.
    assert zeile["ueber_gruppe"] is False
    assert len(zeile["zustaendige"]) == 2


def test_artikel_erscheint_nur_einmal_trotz_zweier_wege(client, admin_headers, db_session):
    admin = db_session.query(models.User).filter(models.User.username == "admin").first()
    g = _gruppe(client, admin_headers, "Fahrzeugwarte Q", [admin.id])
    fz = _fahrzeug(client, admin_headers, db_session, "HN-M 5")
    client.put(f"/api/v1/articles/{fz['id']}",
               json={"warden_user_ids": [admin.id], "warden_group_ids": [g["id"]]},
               headers=admin_headers)
    d = client.get("/api/v1/maintenance/meine-geraete", headers=admin_headers).json()
    assert [a["article_id"] for a in d["artikel"]].count(fz["id"]) == 1


def test_alte_einzelspalten_werden_uebernommen(db_session):
    """Bestandsinstallationen hatten je eine Spalte - die Werte dürfen nicht
    verloren gehen."""
    from sqlalchemy import inspect, text
    from app.seed import uebernimm_alte_zustaendigkeiten
    from app.settings_helper import set_setting

    spalten = {c["name"] for c in inspect(db_session.get_bind()).get_columns("articles")}
    if "warden_id" not in spalten:
        # Frische Datenbank ohne die alten Spalten - nichts zu übernehmen.
        set_setting(db_session, "wardens_migriert", "")
        uebernimm_alte_zustaendigkeiten(db_session)
        return

    admin = db_session.query(models.User).filter(models.User.username == "admin").first()
    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "fahrzeuge").first()
    typ = models.ArticleType(category_id=kat.id, name="MTW alt")
    db_session.add(typ)
    db_session.commit()
    artikel = models.Article(artikelnummer="2026-ALT01", category_id=kat.id, type_id=typ.id)
    db_session.add(artikel)
    db_session.commit()
    db_session.execute(text("UPDATE articles SET warden_id = :u WHERE id = :a"),
                       {"u": admin.id, "a": artikel.id})
    db_session.commit()

    set_setting(db_session, "wardens_migriert", "")
    uebernimm_alte_zustaendigkeiten(db_session)
    db_session.refresh(artikel)
    assert [w["id"] for w in artikel.warden_list] == [admin.id]
