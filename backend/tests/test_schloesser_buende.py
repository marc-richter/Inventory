"""Schloesser am Fahrzeug und Schluesselbuende.

Zwei Dinge, die in der Wirklichkeit zusammengehoeren: ein Fahrzeug hat mehrere
Schloesser (Fahrertuer, Heckklappe, Geraeteraeume), und die Schluessel dafuer
haengen an einem Bund, der als Ganzes ausgegeben wird.
"""

from app import models


# --------------------------- Hilfen -----------------------------------------

def _kategorie(db_session, system_key):
    return db_session.query(models.Category).filter(
        models.Category.system_key == system_key).first()


def _typ(client, admin_headers, kat_id, name):
    r = client.post("/api/v1/types", json={"name": name, "category_id": kat_id},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _fahrzeug(client, admin_headers, db_session, kennzeichen="HN-DRK 123"):
    kat = _kategorie(db_session, "fahrzeuge")
    typ = _typ(client, admin_headers, kat.id, f"MTW {kennzeichen}")
    r = client.post("/api/v1/articles", json={
        "category_id": kat.id, "type_id": typ, "is_vehicle": True,
        "license_plate": kennzeichen,
    }, headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


def _schluessel(client, admin_headers, db_session, alias="", nr=""):
    kat = _kategorie(db_session, "schluessel")
    typ = _typ(client, admin_headers, kat.id, f"Zylinder {alias or nr}")
    r = client.post("/api/v1/articles", json={
        "category_id": kat.id, "type_id": typ, "key_alias": alias, "key_serial": nr,
    }, headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------- Schloesser am Fahrzeug -------------------------

def test_fahrzeugklasse_bringt_das_schloesser_kennzeichen_mit(db_session):
    assert _kategorie(db_session, "fahrzeuge").has_locks is True
    assert _kategorie(db_session, "behaelter").has_locks is True
    # Kleidung hat keine Schloesser - sonst stuende die Karte ueberall.
    assert _kategorie(db_session, "kleidung").has_locks is False


def test_fahrzeug_kann_mehrere_schloesser_haben(client, admin_headers, db_session):
    fz = _fahrzeug(client, admin_headers, db_session)
    for name in ("Fahrertür", "Heckklappe", "Geräteraum 1", "Zündschloss"):
        r = client.post(f"/api/v1/keys/artikel/{fz['id']}/schloesser",
                        json={"name": name}, headers=admin_headers)
        assert r.status_code == 200, r.text

    r = client.get(f"/api/v1/keys/artikel/{fz['id']}/schloesser", headers=admin_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["erlaubt"] is True
    assert [s["name"] for s in d["schloesser"]] == \
        ["Fahrertür", "Geräteraum 1", "Heckklappe", "Zündschloss"]
    # Alle vier gehoeren zu EINER Anlage - der des Fahrzeugs.
    assert len({s["id"] for s in d["schloesser"]}) == 4
    assert d["object_name"] == "HN-DRK 123"


def test_klasse_ohne_kennzeichen_bekommt_keine_schloesser(client, admin_headers, db_session):
    kat = _kategorie(db_session, "kleidung")
    typ = _typ(client, admin_headers, kat.id, "Einsatzjacke")
    art = client.post("/api/v1/articles", json={"category_id": kat.id, "type_id": typ},
                      headers=admin_headers).json()
    r = client.post(f"/api/v1/keys/artikel/{art['id']}/schloesser",
                    json={"name": "Reißverschluss"}, headers=admin_headers)
    assert r.status_code == 400
    assert "Schlösser" in r.json()["detail"]
    # Gelesen werden darf trotzdem - die Oberflaeche fragt einfach immer.
    r = client.get(f"/api/v1/keys/artikel/{art['id']}/schloesser", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["erlaubt"] is False
    assert r.json()["schloesser"] == []


def test_kennzeichen_laesst_sich_je_klasse_umstellen(client, admin_headers, db_session):
    kat = _kategorie(db_session, "kleidung")
    r = client.put(f"/api/v1/categories/{kat.id}/schloesser", json={"issuable": True},
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["has_locks"] is True
    r = client.put(f"/api/v1/categories/{kat.id}/schloesser", json={"issuable": False},
                   headers=admin_headers)
    assert r.json()["has_locks"] is False


def test_schluessel_oeffnet_ein_fahrzeugschloss(client, admin_headers, db_session):
    fz = _fahrzeug(client, admin_headers, db_session)
    schloss = client.post(f"/api/v1/keys/artikel/{fz['id']}/schloesser",
                          json={"name": "Fahrertür"}, headers=admin_headers).json()
    k = _schluessel(client, admin_headers, db_session, alias="MTW Fahrer")
    r = client.put(f"/api/v1/keys/article/{k['id']}/locks",
                   json={"lock_ids": [schloss["id"]]}, headers=admin_headers)
    assert r.status_code == 200, r.text

    r = client.get(f"/api/v1/keys/artikel/{fz['id']}/schloesser", headers=admin_headers)
    eintrag = r.json()["schloesser"][0]
    assert [s["artikelnummer"] for s in eintrag["schluessel"]] == [k["artikelnummer"]]

    # Und andersherum: am Schluessel steht, was er oeffnet.
    art = client.get(f"/api/v1/articles/{k['id']}", headers=admin_headers).json()
    assert [l["name"] for l in art["locks"]] == ["Fahrertür"]


def test_schloesser_eines_fahrzeugs_haengen_nicht_am_standort(client, admin_headers, db_session):
    """Ein Geraeteraum im Fahrzeug gehoert zur Anlage des Fahrzeugs.

    Sonst stuende er im Schliessplan unter dem Standort - und waere dort falsch,
    sobald das Fahrzeug wegfaehrt.
    """
    standort = client.post("/api/v1/storage-nodes",
                           json={"name": "Gerätehaus", "level": "standort"},
                           headers=admin_headers).json()
    fz = _fahrzeug(client, admin_headers, db_session, kennzeichen="HN-DRK 456")
    knoten = client.post(f"/api/v1/articles/{fz['id']}/vehicle-node",
                         json={"parent_id": standort["id"]}, headers=admin_headers)
    assert knoten.status_code == 200, knoten.text
    fz_knoten = knoten.json()

    raum = client.post("/api/v1/storage-nodes",
                       json={"name": "Geräteraum 1", "level": "schrank",
                             "parent_id": fz_knoten["id"]},
                       headers=admin_headers).json()
    r = client.put(f"/api/v1/keys/nodes/{raum['id']}/lock", json={"issuable": True},
                   headers=admin_headers)
    assert r.status_code == 200, r.text

    # Die Schliessung liegt in der Anlage des Fahrzeugs, nicht in der des Standorts.
    d = client.get(f"/api/v1/keys/artikel/{fz['id']}/schloesser", headers=admin_headers).json()
    assert [s["name"] for s in d["schloesser"]] == ["Geräteraum 1"]
    objekte = client.get("/api/v1/keys/objects", headers=admin_headers).json()
    standort_objekt = [o for o in objekte if o["storage_node_id"] == standort["id"]]
    assert standort_objekt == [] or standort_objekt[0]["locks"] == []


# --------------------------- Schluesselbuende -------------------------------

def test_bund_anlegen_und_schluessel_anhaengen(client, admin_headers, db_session):
    a = _schluessel(client, admin_headers, db_session, alias="Haustür")
    b = _schluessel(client, admin_headers, db_session, alias="Garage")
    r = client.post("/api/v1/keys/rings",
                    json={"name": "Gerätehaus komplett", "article_ids": [a["id"], b["id"]]},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["name"] == "Gerätehaus komplett"
    assert d["code"] == "SB-0001"          # fortlaufend, ohne Zutun
    assert d["schluessel_anzahl"] == 2
    assert {k["key_alias"] for k in d["keys"]} == {"Haustür", "Garage"}

    # Der naechste Bund bekommt die naechste Nummer.
    zweiter = client.post("/api/v1/keys/rings", json={"name": "MTW"},
                          headers=admin_headers).json()
    assert zweiter["code"] == "SB-0002"


def test_schluessel_haengt_an_hoechstens_einem_bund(client, admin_headers, db_session):
    k = _schluessel(client, admin_headers, db_session, alias="Haustür")
    eins = client.post("/api/v1/keys/rings", json={"name": "Bund A", "article_ids": [k["id"]]},
                       headers=admin_headers).json()
    zwei = client.post("/api/v1/keys/rings", json={"name": "Bund B"},
                       headers=admin_headers).json()
    r = client.post(f"/api/v1/keys/rings/{zwei['id']}/keys/{k['id']}", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["schluessel_anzahl"] == 1
    # Am ersten Bund haengt er nicht mehr - wie in Wirklichkeit.
    assert client.get(f"/api/v1/keys/rings/{eins['id']}",
                      headers=admin_headers).json()["schluessel_anzahl"] == 0


def test_nur_schluessel_duerfen_an_einen_bund(client, admin_headers, db_session):
    fz = _fahrzeug(client, admin_headers, db_session, kennzeichen="HN-DRK 789")
    bund = client.post("/api/v1/keys/rings", json={"name": "Bund"},
                       headers=admin_headers).json()
    r = client.post(f"/api/v1/keys/rings/{bund['id']}/keys/{fz['id']}", headers=admin_headers)
    assert r.status_code == 400


def test_bund_zeigt_was_er_insgesamt_oeffnet(client, admin_headers, db_session):
    fz = _fahrzeug(client, admin_headers, db_session, kennzeichen="HN-DRK 111")
    tuer = client.post(f"/api/v1/keys/artikel/{fz['id']}/schloesser",
                       json={"name": "Fahrertür"}, headers=admin_headers).json()
    heck = client.post(f"/api/v1/keys/artikel/{fz['id']}/schloesser",
                       json={"name": "Heckklappe"}, headers=admin_headers).json()
    a = _schluessel(client, admin_headers, db_session, alias="Zündung")
    b = _schluessel(client, admin_headers, db_session, alias="Heck")
    client.put(f"/api/v1/keys/article/{a['id']}/locks", json={"lock_ids": [tuer["id"]]},
               headers=admin_headers)
    client.put(f"/api/v1/keys/article/{b['id']}/locks", json={"lock_ids": [heck["id"]]},
               headers=admin_headers)
    bund = client.post("/api/v1/keys/rings",
                       json={"name": "MTW Fahrer", "article_ids": [a["id"], b["id"]]},
                       headers=admin_headers).json()
    assert sorted(l["name"] for l in bund["oeffnet"]) == ["Fahrertür", "Heckklappe"]


def test_bund_wird_als_ganzes_ausgegeben_und_zurueckgenommen(client, admin_headers, db_session):
    person = client.post("/api/v1/persons",
                         json={"first_name": "Erika", "last_name": "Muster"},
                         headers=admin_headers).json()
    a = _schluessel(client, admin_headers, db_session, alias="Haustür")
    b = _schluessel(client, admin_headers, db_session, alias="Garage")
    bund = client.post("/api/v1/keys/rings",
                       json={"name": "Gerätehaus", "article_ids": [a["id"], b["id"]]},
                       headers=admin_headers).json()

    r = client.post(f"/api/v1/keys/rings/{bund['id']}/ausgeben",
                    json={"person_id": person["id"]}, headers=admin_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["vollstaendig"] is True
    assert len(d["ausgegeben"]) == 2
    # Jeder Schluessel hat einen eigenen Vorgang - damit laesst sich ueber genau
    # diese Uebergabe ein Ausgabeblatt drucken.
    assert len(d["issue_ids"]) == 2
    assert d["ring"]["holder"] == "Erika Muster"
    assert d["ring"]["vollstaendig_da"] is True

    for aid in (a["id"], b["id"]):
        assert client.get(f"/api/v1/articles/{aid}",
                          headers=admin_headers).json()["status"] == "ausgegeben"

    r = client.post(f"/api/v1/keys/rings/{bund['id']}/zuruecknehmen", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert len(r.json()["zurueck"]) == 2
    for aid in (a["id"], b["id"]):
        assert client.get(f"/api/v1/articles/{aid}",
                          headers=admin_headers).json()["status"] == "verfuegbar"


def test_ausgabeblatt_ueber_die_bundausgabe(client, admin_headers, db_session):
    """Die Nummern aus der Bundausgabe fuehren direkt zum Beleg."""
    person = client.post("/api/v1/persons",
                         json={"first_name": "Erika", "last_name": "Muster"},
                         headers=admin_headers).json()
    a = _schluessel(client, admin_headers, db_session, alias="Haustür")
    bund = client.post("/api/v1/keys/rings",
                       json={"name": "Gerätehaus", "article_ids": [a["id"]]},
                       headers=admin_headers).json()
    d = client.post(f"/api/v1/keys/rings/{bund['id']}/ausgeben",
                    json={"person_id": person["id"]}, headers=admin_headers).json()
    ids = ",".join(str(i) for i in d["issue_ids"])
    r = client.get(f"/api/v1/receipts/generate?person_id={person['id']}&kind=issue"
                   f"&issue_ids={ids}", headers=admin_headers)
    assert r.status_code == 200, r.text[:400]


def test_bund_meldet_wenn_ein_schluessel_nicht_mitgeht(client, admin_headers, db_session):
    person = client.post("/api/v1/persons",
                         json={"first_name": "Erika", "last_name": "Muster"},
                         headers=admin_headers).json()
    a = _schluessel(client, admin_headers, db_session, alias="Haustür")
    b = _schluessel(client, admin_headers, db_session, alias="Verloren")
    # "Verloren" ist ein gesperrter Status - dieser Schluessel bleibt da.
    r = client.put(f"/api/v1/articles/{b['id']}/status",
                   json={"status": "schluessel_verloren", "condition_note": "beim Einsatz verloren"},
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    bund = client.post("/api/v1/keys/rings",
                       json={"name": "Gerätehaus", "article_ids": [a["id"], b["id"]]},
                       headers=admin_headers).json()
    d = client.post(f"/api/v1/keys/rings/{bund['id']}/ausgeben",
                    json={"person_id": person["id"]}, headers=admin_headers).json()
    assert d["vollstaendig"] is False
    assert d["ausgegeben"] == [a["artikelnummer"]]
    assert d["probleme"][0]["artikelnummer"] == b["artikelnummer"]
    # Der Bund ist auseinandergerissen - und genau das steht da.
    assert d["ring"]["vollstaendig_da"] is False
    assert d["ring"]["holder"] is None


def test_bund_aufloesen_laesst_die_schluessel_stehen(client, admin_headers, db_session):
    a = _schluessel(client, admin_headers, db_session, alias="Haustür")
    bund = client.post("/api/v1/keys/rings",
                       json={"name": "Gerätehaus", "article_ids": [a["id"]]},
                       headers=admin_headers).json()
    assert client.delete(f"/api/v1/keys/rings/{bund['id']}",
                         headers=admin_headers).status_code == 200
    art = client.get(f"/api/v1/articles/{a['id']}", headers=admin_headers).json()
    assert art["key_ring_id"] is None
    assert art["status"] == "verfuegbar"


def test_bund_ist_ueber_seinen_code_auffindbar(client, admin_headers, db_session):
    bund = client.post("/api/v1/keys/rings", json={"name": "Gerätehaus"},
                       headers=admin_headers).json()
    r = client.get(f"/api/v1/keys/rings/by-code/{bund['code']}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["id"] == bund["id"]


def test_bund_steht_am_schluessel_und_in_der_ausgabeliste(client, admin_headers, db_session):
    person = client.post("/api/v1/persons",
                         json={"first_name": "Erika", "last_name": "Muster"},
                         headers=admin_headers).json()
    a = _schluessel(client, admin_headers, db_session, alias="Haustür")
    bund = client.post("/api/v1/keys/rings",
                       json={"name": "Gerätehaus", "article_ids": [a["id"]]},
                       headers=admin_headers).json()
    art = client.get(f"/api/v1/articles/{a['id']}", headers=admin_headers).json()
    assert art["key_ring_id"] == bund["id"]
    assert art["key_ring_name"] == "Gerätehaus"

    client.post(f"/api/v1/keys/rings/{bund['id']}/ausgeben",
                json={"person_id": person["id"]}, headers=admin_headers)
    liste = client.get("/api/v1/keys/issued", headers=admin_headers).json()
    zeile = [z for z in liste if z["article_id"] == a["id"]][0]
    assert zeile["key_ring_name"] == "Gerätehaus"
    assert zeile["holder"] == "Erika Muster"


# --------------------------- Eine Anlage je Artikel -------------------------

def _anlagen_des_fahrzeugs(client, admin_headers, article_id):
    return [o for o in client.get("/api/v1/keys/objects", headers=admin_headers).json()
            if o["vehicle_article_id"] == article_id]


def test_ein_fahrzeug_hat_genau_eine_schliessanlage(client, admin_headers, db_session):
    """Egal auf welchem Weg man Schlösser anlegt - es ist dieselbe Anlage.

    Der gemeldete Fall: erst ein Schloss in der Artikelansicht, dann das
    Fahrzeug als Lagerort aktiviert. Danach gab es zwei gleichnamige Anlagen im
    Schließplan, und die Karte am Fahrzeug zeigte nur die halben Schlösser.
    """
    fz = _fahrzeug(client, admin_headers, db_session, kennzeichen="HN-DRK 2001")
    client.post(f"/api/v1/keys/artikel/{fz['id']}/schloesser",
                json={"name": "Fahrertür"}, headers=admin_headers)
    assert len(_anlagen_des_fahrzeugs(client, admin_headers, fz["id"])) == 1

    # Fahrzeug wird NACHTRÄGLICH zum Lagerort.
    standort = client.post("/api/v1/storage-nodes",
                           json={"name": "Gerätehaus 2001", "level": "standort"},
                           headers=admin_headers).json()
    client.post(f"/api/v1/articles/{fz['id']}/vehicle-node",
                json={"parent_id": standort["id"]}, headers=admin_headers)
    client.post(f"/api/v1/keys/artikel/{fz['id']}/schloesser",
                json={"name": "Heckklappe"}, headers=admin_headers)

    anlagen = _anlagen_des_fahrzeugs(client, admin_headers, fz["id"])
    assert len(anlagen) == 1, [a["name"] for a in anlagen]
    assert sorted(l["name"] for l in anlagen[0]["locks"]) == ["Fahrertür", "Heckklappe"]

    # Und die Karte am Fahrzeug zeigt beide.
    d = client.get(f"/api/v1/keys/artikel/{fz['id']}/schloesser",
                   headers=admin_headers).json()
    assert sorted(s["name"] for s in d["schloesser"]) == ["Fahrertür", "Heckklappe"]


def test_schloss_ueber_den_schliessplan_erscheint_am_fahrzeug(client, admin_headers,
                                                              db_session):
    """Was der Administrator in den Einstellungen anlegt, steht auch am Artikel."""
    fz = _fahrzeug(client, admin_headers, db_session, kennzeichen="HN-DRK 2002")
    client.post(f"/api/v1/keys/artikel/{fz['id']}/schloesser",
                json={"name": "Fahrertür"}, headers=admin_headers)
    anlage = _anlagen_des_fahrzeugs(client, admin_headers, fz["id"])[0]

    r = client.post(f"/api/v1/keys/objects/{anlage['id']}/locks",
                    json={"name": "Geräteraum 1"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    d = client.get(f"/api/v1/keys/artikel/{fz['id']}/schloesser",
                   headers=admin_headers).json()
    assert sorted(s["name"] for s in d["schloesser"]) == ["Fahrertür", "Geräteraum 1"]


def test_bestehende_doppelte_anlagen_werden_zusammengefuehrt(db_session):
    """Bestandsinstallationen haben die Doppel schon - der Start räumt sie weg."""
    from app.seed import repariere_schliessanlagen

    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "fahrzeuge").first()
    typ = models.ArticleType(category_id=kat.id, name="MTW Doppelt")
    db_session.add(typ)
    db_session.commit()
    artikel = models.Article(artikelnummer="2026-D0001", category_id=kat.id,
                             type_id=typ.id, is_vehicle=True, license_plate="HN-DRK 3003")
    db_session.add(artikel)
    db_session.commit()
    knoten = models.StorageNode(level="fahrzeug", name="HN-DRK 3003",
                               node_article_id=artikel.id)
    db_session.add(knoten)
    db_session.commit()

    alt = models.LockObject(name="HN-DRK 3003", vehicle_article_id=artikel.id)
    neu = models.LockObject(name="HN-DRK 3003", storage_node_id=knoten.id,
                            vehicle_article_id=artikel.id)
    db_session.add_all([alt, neu])
    db_session.commit()
    db_session.add_all([
        models.Lock(object_id=alt.id, name="Fahrertür"),
        models.Lock(object_id=neu.id, name="Heckklappe"),
    ])
    db_session.commit()

    repariere_schliessanlagen(db_session)

    uebrig = db_session.query(models.LockObject).filter(
        models.LockObject.vehicle_article_id == artikel.id).all()
    assert len(uebrig) == 1
    # Beide Schlösser sind erhalten geblieben - nichts geht verloren.
    namen = sorted(l.name for l in db_session.query(models.Lock).filter(
        models.Lock.object_id == uebrig[0].id).all())
    assert namen == ["Fahrertür", "Heckklappe"]
    # Und der Knoten hängt an der überlebenden Anlage.
    assert uebrig[0].storage_node_id == knoten.id


def test_reparatur_traegt_fehlende_verknuepfung_nach(db_session):
    """Alte Anlagen kennen die Artikel-Verknüpfung nicht; ohne sie findet die
    Karte am Fahrzeug ihre eigenen Schlösser nicht."""
    from app.seed import repariere_schliessanlagen

    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "fahrzeuge").first()
    typ = models.ArticleType(category_id=kat.id, name="MTW Alt")
    db_session.add(typ)
    db_session.commit()
    artikel = models.Article(artikelnummer="2026-D0002", category_id=kat.id,
                             type_id=typ.id, is_vehicle=True, license_plate="HN-DRK 4004")
    db_session.add(artikel)
    db_session.commit()
    knoten = models.StorageNode(level="fahrzeug", name="HN-DRK 4004",
                               node_article_id=artikel.id)
    db_session.add(knoten)
    db_session.commit()
    db_session.add(models.LockObject(name="HN-DRK 4004", storage_node_id=knoten.id))
    db_session.commit()

    repariere_schliessanlagen(db_session)
    obj = db_session.query(models.LockObject).filter(
        models.LockObject.storage_node_id == knoten.id).first()
    assert obj.vehicle_article_id == artikel.id


def test_reparatur_ist_wiederholbar(db_session):
    """Bei jedem Start - ohne Doppel darf sie nichts anfassen."""
    from app.seed import repariere_schliessanlagen
    vorher = db_session.query(models.LockObject).count()
    repariere_schliessanlagen(db_session)
    repariere_schliessanlagen(db_session)
    assert db_session.query(models.LockObject).count() == vorher
