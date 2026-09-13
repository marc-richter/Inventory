"""Bereitstellungen: vormerken, Beleg drucken, spaeter gesammelt ausgeben.

Zusammenstellen und Uebergeben fallen auseinander - die Einsatzausstattung wird
abends gepackt und am naechsten Morgen abgeholt. Ohne Vormerkung stehen die
Sachen bis dahin als verfuegbar da und werden ein zweites Mal verplant. Genau das
soll die Bereitstellung verhindern, ohne den Bestand zu verfaelschen: vorgemerkte
Artikel bleiben im Lager und behalten ihren Status, gebucht wird erst bei der
Uebergabe.
"""

import io

from pypdf import PdfReader

from app import models


def _text(rohdaten: bytes) -> str:
    return " ".join((s.extract_text() or "") for s in PdfReader(io.BytesIO(rohdaten)).pages)


def _person(client, admin_headers, vorname="Nina", nachname="Notfall"):
    return client.post("/api/v1/persons",
                       json={"first_name": vorname, "last_name": nachname},
                       headers=admin_headers).json()


def _artikel(client, admin_headers, db_session, name):
    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "kleidung").first()
    typ = client.post("/api/v1/types", json={"name": name, "category_id": kat.id},
                      headers=admin_headers).json()
    return client.post("/api/v1/articles",
                       json={"category_id": kat.id, "type_id": typ["id"], "size": "M"},
                       headers=admin_headers).json()


def _bereitstellung(client, admin_headers, person, artikel):
    r = client.post("/api/v1/bereitstellungen", json={
        "person_id": person["id"], "note": "Einsatzausstattung",
        "article_ids": [a["id"] for a in artikel]}, headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


# --- Anlegen und Vormerken ---------------------------------------------------

def test_anlegen_vergibt_einen_scanbaren_code(client, admin_headers, db_session):
    person = _person(client, admin_headers)
    a = _artikel(client, admin_headers, db_session, "Einsatzjacke V")
    b = _bereitstellung(client, admin_headers, person, [a])
    assert b["code"].startswith("BS-")
    assert b["status"] == "offen"
    assert len(b["positionen"]) == 1
    assert b["positionen"][0]["artikelnummer"] == a["artikelnummer"]

    gefunden = client.get(f"/api/v1/bereitstellungen/by-code/{b['code']}",
                          headers=admin_headers).json()
    assert gefunden["id"] == b["id"]


def test_vorgemerkte_artikel_bleiben_verfuegbar(client, admin_headers, db_session):
    """Sie liegen ja noch im Lager - der Bestand darf nicht verfaelscht werden."""
    person = _person(client, admin_headers)
    a = _artikel(client, admin_headers, db_session, "Hose V")
    _bereitstellung(client, admin_headers, person, [a])
    d = client.get(f"/api/v1/articles/{a['id']}", headers=admin_headers).json()
    assert d["status"] == "verfuegbar"


def test_ein_artikel_steht_nur_auf_einer_offenen_bereitstellung(client, admin_headers, db_session):
    eine = _person(client, admin_headers, "Anna", "Erste")
    andere = _person(client, admin_headers, "Bodo", "Zweiter")
    a = _artikel(client, admin_headers, db_session, "Helm V")
    b1 = _bereitstellung(client, admin_headers, eine, [a])

    r = client.post("/api/v1/bereitstellungen",
                    json={"person_id": andere["id"], "article_ids": [a["id"]]},
                    headers=admin_headers)
    assert r.status_code == 400
    assert b1["code"] in r.json()["detail"]
    assert "Anna" in r.json()["detail"]


def test_abbrechen_gibt_die_artikel_wieder_frei(client, admin_headers, db_session):
    eine = _person(client, admin_headers, "Cara", "Dritte")
    andere = _person(client, admin_headers, "Dirk", "Vierter")
    a = _artikel(client, admin_headers, db_session, "Weste V")
    b = _bereitstellung(client, admin_headers, eine, [a])

    assert client.post(f"/api/v1/bereitstellungen/{b['id']}/abbrechen",
                       headers=admin_headers).json()["status"] == "abgebrochen"
    r = client.post("/api/v1/bereitstellungen",
                    json={"person_id": andere["id"], "article_ids": [a["id"]]},
                    headers=admin_headers)
    assert r.status_code == 200, r.text


def test_positionen_hinzufuegen_und_entfernen(client, admin_headers, db_session):
    person = _person(client, admin_headers)
    a1 = _artikel(client, admin_headers, db_session, "Teil eins")
    a2 = _artikel(client, admin_headers, db_session, "Teil zwei")
    b = _bereitstellung(client, admin_headers, person, [a1])

    b = client.post(f"/api/v1/bereitstellungen/{b['id']}/positionen",
                    json={"article_ids": [a2["id"]]}, headers=admin_headers).json()
    assert len(b["positionen"]) == 2
    # Zweimal dasselbe aendert nichts.
    b = client.post(f"/api/v1/bereitstellungen/{b['id']}/positionen",
                    json={"article_ids": [a2["id"]]}, headers=admin_headers).json()
    assert len(b["positionen"]) == 2

    pos = b["positionen"][0]["id"]
    b = client.delete(f"/api/v1/bereitstellungen/{b['id']}/positionen/{pos}",
                      headers=admin_headers).json()
    assert len(b["positionen"]) == 1


# --- Der Beleg ---------------------------------------------------------------

def test_beleg_traegt_code_person_und_artikel(client, admin_headers, db_session):
    person = _person(client, admin_headers, "Erik", "Empfang")
    a1 = _artikel(client, admin_headers, db_session, "Belegteil eins")
    a2 = _artikel(client, admin_headers, db_session, "Belegteil zwei")
    b = _bereitstellung(client, admin_headers, person, [a1, a2])

    r = client.get(f"/api/v1/bereitstellungen/{b['id']}/beleg", headers=admin_headers)
    assert r.status_code == 200
    text = _text(r.content)
    assert b["code"] in text
    assert "Erik Empfang" in text
    assert a1["artikelnummer"] in text and a2["artikelnummer"] in text
    assert "Unterschrift" in text
    assert b["code"].lower() in r.headers["content-disposition"]


# --- Die Uebergabe -----------------------------------------------------------

def test_ausgeben_bucht_alles_und_schliesst_ab(client, admin_headers, db_session):
    person = _person(client, admin_headers, "Frank", "Fertig")
    a1 = _artikel(client, admin_headers, db_session, "Übergabe eins")
    a2 = _artikel(client, admin_headers, db_session, "Übergabe zwei")
    b = _bereitstellung(client, admin_headers, person, [a1, a2])

    r = client.post(f"/api/v1/bereitstellungen/{b['id']}/ausgeben", json={},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["issue_ids"]) == 2
    assert d["bereitstellung"]["status"] == "ausgegeben"
    assert d["bereitstellung"]["issued_at"]
    for a in (a1, a2):
        assert client.get(f"/api/v1/articles/{a['id']}",
                          headers=admin_headers).json()["status"] == "ausgegeben"


def test_beleg_der_uebergabe_nennt_genau_diese_artikel(client, admin_headers, db_session):
    """Die Ausgabe-Nummern aus der Uebergabe speisen das Ausgabeblatt."""
    person = _person(client, admin_headers, "Gita", "Geprüft")
    frueher = _artikel(client, admin_headers, db_session, "Schon länger da")
    client.post("/api/v1/issues/issue",
                json={"article_id": frueher["id"], "person_id": person["id"]},
                headers=admin_headers)
    a = _artikel(client, admin_headers, db_session, "Jetzt übergeben")
    b = _bereitstellung(client, admin_headers, person, [a])
    d = client.post(f"/api/v1/bereitstellungen/{b['id']}/ausgeben", json={},
                    headers=admin_headers).json()

    ids = ",".join(str(i) for i in d["issue_ids"])
    text = _text(client.get(
        f"/api/v1/receipts/generate?person_id={person['id']}&kind=issue&issue_ids={ids}",
        headers=admin_headers).content)
    assert a["artikelnummer"] in text
    assert frueher["artikelnummer"] not in text


def test_teilweise_uebergabe_laesst_die_bereitstellung_offen(client, admin_headers, db_session):
    person = _person(client, admin_headers, "Hans", "Halb")
    a1 = _artikel(client, admin_headers, db_session, "Halb eins")
    a2 = _artikel(client, admin_headers, db_session, "Halb zwei")
    b = _bereitstellung(client, admin_headers, person, [a1, a2])
    erste_pos = b["positionen"][0]["id"]

    d = client.post(f"/api/v1/bereitstellungen/{b['id']}/ausgeben",
                    json={"position_ids": [erste_pos]}, headers=admin_headers).json()
    assert len(d["issue_ids"]) == 1
    assert d["bereitstellung"]["status"] == "offen"

    rest = client.post(f"/api/v1/bereitstellungen/{b['id']}/ausgeben", json={},
                       headers=admin_headers).json()
    assert rest["bereitstellung"]["status"] == "ausgegeben"


def test_zweimal_ausgeben_geht_nicht(client, admin_headers, db_session):
    person = _person(client, admin_headers, "Ida", "Einmal")
    a = _artikel(client, admin_headers, db_session, "Nur einmal")
    b = _bereitstellung(client, admin_headers, person, [a])
    client.post(f"/api/v1/bereitstellungen/{b['id']}/ausgeben", json={}, headers=admin_headers)
    r = client.post(f"/api/v1/bereitstellungen/{b['id']}/ausgeben", json={},
                    headers=admin_headers)
    assert r.status_code == 400


# --- Vormerkung schuetzt vor Doppelvergabe -----------------------------------

def test_einzelausgabe_an_jemand_anderen_fragt_nach(client, admin_headers, db_session):
    """Sonst fehlt der Ausstattung morgen frueh ein Teil und niemand weiss warum."""
    vorgemerkt_fuer = _person(client, admin_headers, "Jana", "Geplant")
    jemand = _person(client, admin_headers, "Kurt", "Spontan")
    a = _artikel(client, admin_headers, db_session, "Umkämpft")
    b = _bereitstellung(client, admin_headers, vorgemerkt_fuer, [a])

    r = client.post("/api/v1/issues/issue",
                    json={"article_id": a["id"], "person_id": jemand["id"]},
                    headers=admin_headers)
    assert r.status_code == 400
    assert b["code"] in r.json()["detail"] and "Jana" in r.json()["detail"]

    # Mit Bestaetigung geht es trotzdem - die Vormerkung ist eine Warnung, kein Verbot.
    r = client.post("/api/v1/issues/issue",
                    json={"article_id": a["id"], "person_id": jemand["id"], "confirm": True},
                    headers=admin_headers)
    assert r.status_code == 200, r.text


def test_ausgabe_an_die_vorgemerkte_person_fragt_nicht_nach(client, admin_headers, db_session):
    person = _person(client, admin_headers, "Lena", "Passend")
    a = _artikel(client, admin_headers, db_session, "Passt schon")
    _bereitstellung(client, admin_headers, person, [a])
    r = client.post("/api/v1/issues/issue",
                    json={"article_id": a["id"], "person_id": person["id"]},
                    headers=admin_headers)
    assert r.status_code == 200, r.text


def test_auskunft_zum_artikel(client, admin_headers, db_session):
    person = _person(client, admin_headers, "Mara", "Merk")
    a = _artikel(client, admin_headers, db_session, "Auskunft")
    frei = _artikel(client, admin_headers, db_session, "Frei")
    b = _bereitstellung(client, admin_headers, person, [a])

    d = client.get(f"/api/v1/bereitstellungen/fuer-artikel/{a['id']}",
                   headers=admin_headers).json()
    assert d["vorgemerkt"] is True and d["code"] == b["code"] and d["person"] == "Mara Merk"
    assert client.get(f"/api/v1/bereitstellungen/fuer-artikel/{frei['id']}",
                      headers=admin_headers).json()["vorgemerkt"] is False


def test_nicht_ausgebbare_artikel_lassen_sich_nicht_vormerken(client, admin_headers, db_session):
    person = _person(client, admin_headers, "Nora", "Nein")
    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "fahrzeuge").first()
    typ = client.post("/api/v1/types", json={"name": "MTW-Typ", "category_id": kat.id},
                      headers=admin_headers).json()
    a = client.post("/api/v1/articles",
                    json={"category_id": kat.id, "type_id": typ["id"], "issuable_override": False},
                    headers=admin_headers).json()
    r = client.post("/api/v1/bereitstellungen",
                    json={"person_id": person["id"], "article_ids": [a["id"]]},
                    headers=admin_headers)
    assert r.status_code == 400
