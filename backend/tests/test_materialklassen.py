"""Materialklassen: Status je Klasse, Klasse wechseln, Klasse aufloesen.

Drei Dinge, die zusammengehoeren:

* Ein Status gilt nur fuer die Klassen, denen er zugeordnet ist. "Zu waschen"
  hat an einem Schluessel nichts zu suchen - und zwar auch dann nicht, wenn die
  Anfrage an der Oberflaeche vorbei kommt.
* Die Klasse eines Artikels muss sich nachtraeglich aendern lassen. Wird sie beim
  Erfassen falsch gewaehlt, war der Artikel bisher nur neu anzulegen - und verlor
  dabei seine Geschichte.
* Eine selbst angelegte Klasse muss sich aufloesen lassen. Sie mitsamt ihren
  Artikeln zu loeschen waere die schlechteste aller Moeglichkeiten; also erst
  umhaengen, dann loeschen.
"""

import pytest

from app import models


def _klasse(client, admin_headers, name, parent_id=None):
    nutzlast = {"name": name}
    if parent_id:
        nutzlast["parent_id"] = parent_id
    r = client.post("/api/v1/categories", json=nutzlast, headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


def _typ(client, admin_headers, name, category_id):
    r = client.post("/api/v1/types", json={"name": name, "category_id": category_id},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


def _artikel(client, admin_headers, category_id, type_id):
    r = client.post("/api/v1/articles",
                    json={"category_id": category_id, "type_id": type_id},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


def _status(client, admin_headers, label, category_ids):
    r = client.post("/api/v1/statuses",
                    json={"label": label, "category_ids": category_ids},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


# --- Status gehoeren zur Klasse ---------------------------------------------

def test_statusliste_zeigt_nur_die_der_klasse(client, admin_headers):
    a = _klasse(client, admin_headers, "Klasse A")
    b = _klasse(client, admin_headers, "Klasse B")
    nur_a = _status(client, admin_headers, "Nur für A", [a["id"]])
    fuer_alle = _status(client, admin_headers, "Gilt überall", [])

    keys_a = {s["key"] for s in client.get(f"/api/v1/statuses?category_id={a['id']}",
                                           headers=admin_headers).json()}
    keys_b = {s["key"] for s in client.get(f"/api/v1/statuses?category_id={b['id']}",
                                           headers=admin_headers).json()}
    assert nur_a["key"] in keys_a and nur_a["key"] not in keys_b
    assert fuer_alle["key"] in keys_a and fuer_alle["key"] in keys_b


def test_server_weist_klassenfremden_status_ab(client, admin_headers):
    """Die Pruefung darf nicht nur in der Oberflaeche stehen: sonst laesst sich
    ueber die Schnittstelle jeder Status an jedem Artikel setzen."""
    a = _klasse(client, admin_headers, "Kleidung X")
    b = _klasse(client, admin_headers, "Schlüssel X")
    typ_b = _typ(client, admin_headers, "Haustürschlüssel", b["id"])
    artikel = _artikel(client, admin_headers, b["id"], typ_b["id"])
    waschen = _status(client, admin_headers, "Zu waschen X", [a["id"]])

    r = client.put(f"/api/v1/articles/{artikel['id']}/status",
                   json={"status": waschen["key"]}, headers=admin_headers)
    assert r.status_code == 400
    assert "Materialklasse" in r.json()["detail"]


def test_status_fuer_alle_klassen_bleibt_erlaubt(client, admin_headers):
    b = _klasse(client, admin_headers, "Beliebig")
    typ = _typ(client, admin_headers, "Dings", b["id"])
    artikel = _artikel(client, admin_headers, b["id"], typ["id"])
    ueberall = _status(client, admin_headers, "Überall gültig", [])
    r = client.put(f"/api/v1/articles/{artikel['id']}/status",
                   json={"status": ueberall["key"]}, headers=admin_headers)
    assert r.status_code == 200, r.text


def test_unterklasse_erbt_die_status_ihrer_oberklasse(client, admin_headers):
    ober = _klasse(client, admin_headers, "Funkgeräte")
    unter = _klasse(client, admin_headers, "Handfunkgeräte", parent_id=ober["id"])
    typ = _typ(client, admin_headers, "HRT", unter["id"])
    artikel = _artikel(client, admin_headers, unter["id"], typ["id"])
    gesperrt = _status(client, admin_headers, "Gesperrt X", [ober["id"]])
    r = client.put(f"/api/v1/articles/{artikel['id']}/status",
                   json={"status": gesperrt["key"]}, headers=admin_headers)
    assert r.status_code == 200, r.text


# --- Klasse eines Artikels wechseln ------------------------------------------

def test_admin_stellt_die_klasse_um(client, admin_headers):
    alt = _klasse(client, admin_headers, "Falsch geraten")
    neu = _klasse(client, admin_headers, "Richtig")
    typ_alt = _typ(client, admin_headers, "Typ alt", alt["id"])
    typ_neu = _typ(client, admin_headers, "Typ neu", neu["id"])
    artikel = _artikel(client, admin_headers, alt["id"], typ_alt["id"])

    r = client.put(f"/api/v1/articles/{artikel['id']}",
                   json={"category_id": neu["id"], "type_id": typ_neu["id"]},
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["category_id"] == neu["id"]
    assert r.json()["type_id"] == typ_neu["id"]
    # Die Nummer bleibt - der Artikel ist derselbe geblieben, nur anders einsortiert.
    assert r.json()["artikelnummer"] == artikel["artikelnummer"]


def test_klasse_ohne_passenden_typ_wird_abgelehnt(client, admin_headers):
    """Ein Artikel, dessen Typ nicht zu seiner Klasse gehoert, faellt spaeter in
    jeder Auswertung auf die Fuesse."""
    alt = _klasse(client, admin_headers, "Alt 2")
    neu = _klasse(client, admin_headers, "Neu 2")
    typ_alt = _typ(client, admin_headers, "Typ alt 2", alt["id"])
    artikel = _artikel(client, admin_headers, alt["id"], typ_alt["id"])

    r = client.put(f"/api/v1/articles/{artikel['id']}",
                   json={"category_id": neu["id"]}, headers=admin_headers)
    assert r.status_code == 400
    assert "Artikeltyp" in r.json()["detail"]


def test_klassenwechsel_nur_durch_den_administrator(client, admin_headers, db_session):
    from app.security import hash_secret
    alt = _klasse(client, admin_headers, "Alt 3")
    neu = _klasse(client, admin_headers, "Neu 3")
    typ_alt = _typ(client, admin_headers, "Typ alt 3", alt["id"])
    typ_neu = _typ(client, admin_headers, "Typ neu 3", neu["id"])
    artikel = _artikel(client, admin_headers, alt["id"], typ_alt["id"])

    db_session.add(models.User(username="wart", full_name="W. Art", roles=["verwalter"],
                               password_hash=hash_secret("wart12345"), active=True))
    db_session.commit()
    tok = client.post("/api/v1/auth/login",
                      json={"username": "wart", "password": "wart12345"}).json()
    kopf = {"Authorization": f"Bearer {tok['access_token']}"}
    r = client.put(f"/api/v1/articles/{artikel['id']}",
                   json={"category_id": neu["id"], "type_id": typ_neu["id"]}, headers=kopf)
    assert r.status_code == 403
    # Alles andere darf er weiterhin aendern.
    assert client.put(f"/api/v1/articles/{artikel['id']}",
                      json={"remarks": "geprüft"}, headers=kopf).status_code == 200


# --- Klasse aufloesen --------------------------------------------------------

def test_verwendung_zeigt_was_an_der_klasse_haengt(client, admin_headers):
    k = _klasse(client, admin_headers, "Zum Auflösen")
    unter = _klasse(client, admin_headers, "Unterklasse", parent_id=k["id"])
    typ = _typ(client, admin_headers, "Irgendwas", k["id"])
    _artikel(client, admin_headers, k["id"], typ["id"])
    _artikel(client, admin_headers, k["id"], typ["id"])

    d = client.get(f"/api/v1/categories/{k['id']}/verwendung", headers=admin_headers).json()
    assert d["articles_total"] == 2
    assert len(d["articles"]) == 2
    assert d["types"][0]["name"] == "Irgendwas" and d["types"][0]["articles"] == 2
    assert [u["id"] for u in d["subcategories"]] == [unter["id"]]
    assert d["articles"][0]["artikelnummer"]


def test_loeschen_scheitert_solange_artikel_daran_haengen(client, admin_headers):
    k = _klasse(client, admin_headers, "Noch benutzt")
    typ = _typ(client, admin_headers, "T", k["id"])
    _artikel(client, admin_headers, k["id"], typ["id"])
    r = client.delete(f"/api/v1/categories/{k['id']}", headers=admin_headers)
    assert r.status_code == 400


def test_ganzen_typ_umhaengen_nimmt_die_artikel_mit(client, admin_headers):
    """Der schnelle Weg: der Typ behaelt seinen Namen und nimmt alles mit."""
    quelle = _klasse(client, admin_headers, "Quelle A")
    ziel = _klasse(client, admin_headers, "Ziel A")
    typ = _typ(client, admin_headers, "Wandertyp", quelle["id"])
    a1 = _artikel(client, admin_headers, quelle["id"], typ["id"])
    a2 = _artikel(client, admin_headers, quelle["id"], typ["id"])

    r = client.post(f"/api/v1/categories/{quelle['id']}/umhaengen",
                    json={"ziel_category_id": ziel["id"], "type_ids": [typ["id"]]},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["typen"] == 1
    assert r.json()["verbleibend_artikel"] == 0

    for a in (a1, a2):
        d = client.get(f"/api/v1/articles/{a['id']}", headers=admin_headers).json()
        assert d["category_id"] == ziel["id"]
        assert d["type_id"] == typ["id"]
    assert client.delete(f"/api/v1/categories/{quelle['id']}",
                         headers=admin_headers).status_code == 200


def test_einzelne_artikel_umhaengen_braucht_einen_zieltyp(client, admin_headers):
    quelle = _klasse(client, admin_headers, "Quelle B")
    ziel = _klasse(client, admin_headers, "Ziel B")
    typ_q = _typ(client, admin_headers, "Q-Typ", quelle["id"])
    typ_z = _typ(client, admin_headers, "Z-Typ", ziel["id"])
    a1 = _artikel(client, admin_headers, quelle["id"], typ_q["id"])
    a2 = _artikel(client, admin_headers, quelle["id"], typ_q["id"])

    ohne = client.post(f"/api/v1/categories/{quelle['id']}/umhaengen",
                       json={"ziel_category_id": ziel["id"], "article_ids": [a1["id"]]},
                       headers=admin_headers)
    assert ohne.status_code == 400
    assert "Artikeltyp" in ohne.json()["detail"]

    r = client.post(f"/api/v1/categories/{quelle['id']}/umhaengen",
                    json={"ziel_category_id": ziel["id"], "ziel_type_id": typ_z["id"],
                          "article_ids": [a1["id"]]}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["artikel"] == 1 and r.json()["verbleibend_artikel"] == 1

    erst = client.get(f"/api/v1/articles/{a1['id']}", headers=admin_headers).json()
    zweit = client.get(f"/api/v1/articles/{a2['id']}", headers=admin_headers).json()
    assert erst["category_id"] == ziel["id"] and erst["type_id"] == typ_z["id"]
    assert zweit["category_id"] == quelle["id"]        # nicht ausgewaehlt, nicht bewegt


def test_unterklassen_lassen_sich_mit_umhaengen(client, admin_headers):
    quelle = _klasse(client, admin_headers, "Quelle C")
    ziel = _klasse(client, admin_headers, "Ziel C")
    unter = _klasse(client, admin_headers, "Unter C", parent_id=quelle["id"])
    r = client.post(f"/api/v1/categories/{quelle['id']}/umhaengen",
                    json={"ziel_category_id": ziel["id"], "subcategory_ids": [unter["id"]]},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["unterklassen"] == 1 and r.json()["verbleibend_unterklassen"] == 0
    assert client.delete(f"/api/v1/categories/{quelle['id']}",
                         headers=admin_headers).status_code == 200


def test_mitgelieferte_klasse_bleibt_geschuetzt(client, admin_headers, db_session):
    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "schluessel").first()
    r = client.delete(f"/api/v1/categories/{kat.id}", headers=admin_headers)
    assert r.status_code == 400
    assert "ausblenden" in r.json()["detail"].lower() or "blenden" in r.json()["detail"].lower()


def test_umhaengen_in_dieselbe_klasse_wird_abgelehnt(client, admin_headers):
    k = _klasse(client, admin_headers, "Selbst")
    r = client.post(f"/api/v1/categories/{k['id']}/umhaengen",
                    json={"ziel_category_id": k["id"]}, headers=admin_headers)
    assert r.status_code == 400


def test_umhaengen_nur_durch_den_administrator(client, admin_headers, db_session):
    from app.security import hash_secret
    quelle = _klasse(client, admin_headers, "Quelle D")
    ziel = _klasse(client, admin_headers, "Ziel D")
    db_session.add(models.User(username="leser", full_name="L. Eser", roles=["lesend"],
                               password_hash=hash_secret("leser1234"), active=True))
    db_session.commit()
    tok = client.post("/api/v1/auth/login",
                      json={"username": "leser", "password": "leser1234"}).json()
    kopf = {"Authorization": f"Bearer {tok['access_token']}"}
    assert client.get(f"/api/v1/categories/{quelle['id']}/verwendung",
                      headers=kopf).status_code == 403
    assert client.post(f"/api/v1/categories/{quelle['id']}/umhaengen",
                       json={"ziel_category_id": ziel["id"]}, headers=kopf).status_code == 403
