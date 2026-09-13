"""Das Ausgabeblatt (Empfangsbestaetigung) - besonders bei der Sammelausgabe.

Bei der Sammelausgabe liess sich bisher kein Beleg erzeugen: die Antwort nannte
die angelegten Ausgabevorgaenge nicht, und der Beleg konnte sich nur auf "alles,
was die Person heute bekommen hat" beziehen. Auf einer Empfangsbestaetigung, die
jemand unterschreibt, gehoert aber genau das, was gerade uebergeben wurde.
"""

import io

import pytest
from pypdf import PdfReader

from app import models


def _text(rohdaten: bytes) -> str:
    return " ".join((s.extract_text() or "") for s in PdfReader(io.BytesIO(rohdaten)).pages)


def _person(client, admin_headers, vorname="Anna", nachname="Ausgabe"):
    r = client.post("/api/v1/persons", json={"first_name": vorname, "last_name": nachname},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


def _artikel(client, admin_headers, db_session, name):
    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "kleidung").first()
    typ = client.post("/api/v1/types", json={"name": name, "category_id": kat.id},
                      headers=admin_headers).json()
    r = client.post("/api/v1/articles",
                    json={"category_id": kat.id, "type_id": typ["id"], "size": "L"},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_sammelausgabe_nennt_die_ausgabevorgaenge(client, admin_headers, db_session):
    """Ohne diese Nummern kann die Oberflaeche kein Blatt ueber genau diese
    Uebergabe anbieten."""
    person = _person(client, admin_headers)
    a1 = _artikel(client, admin_headers, db_session, "Einsatzjacke B")
    a2 = _artikel(client, admin_headers, db_session, "Einsatzhose B")

    r = client.post("/api/v1/issues/batch", json={
        "person_id": person["id"],
        "items": [{"article_id": a1["id"]}, {"article_id": a2["id"]}],
    }, headers=admin_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["issued"] == 2
    assert len(d["issue_ids"]) == 2
    for eintrag in d["results"]:
        assert eintrag["issue_record_id"] in d["issue_ids"]


def test_ausgabeblatt_fuehrt_genau_diese_uebergabe_auf(client, admin_headers, db_session):
    person = _person(client, admin_headers, "Bert", "Beleg")
    frueher = _artikel(client, admin_headers, db_session, "Früher ausgegeben")
    neu1 = _artikel(client, admin_headers, db_session, "Jetzt Jacke")
    neu2 = _artikel(client, admin_headers, db_session, "Jetzt Hose")

    client.post("/api/v1/issues/issue",
                json={"article_id": frueher["id"], "person_id": person["id"]},
                headers=admin_headers)
    d = client.post("/api/v1/issues/batch", json={
        "person_id": person["id"],
        "items": [{"article_id": neu1["id"]}, {"article_id": neu2["id"]}],
    }, headers=admin_headers).json()
    ids = ",".join(str(i) for i in d["issue_ids"])

    beleg = client.get(
        f"/api/v1/receipts/generate?person_id={person['id']}&kind=issue&issue_ids={ids}",
        headers=admin_headers)
    assert beleg.status_code == 200
    text = _text(beleg.content)
    assert neu1["artikelnummer"] in text and neu2["artikelnummer"] in text
    # Der frueher ausgegebene Artikel steht NICHT im Empfangsteil - er wurde ja
    # nicht gerade uebergeben.
    kopfteil = text.split("Bereits")[0]
    assert frueher["artikelnummer"] not in kopfteil


def test_ohne_angabe_bleibt_es_beim_bisherigen_verhalten(client, admin_headers, db_session):
    """Wer den Beleg aus der Personenakte zieht, bekommt wie bisher alles von heute."""
    person = _person(client, admin_headers, "Cara", "Chronik")
    a1 = _artikel(client, admin_headers, db_session, "Heute eins")
    a2 = _artikel(client, admin_headers, db_session, "Heute zwei")
    for a in (a1, a2):
        client.post("/api/v1/issues/issue",
                    json={"article_id": a["id"], "person_id": person["id"]},
                    headers=admin_headers)
    text = _text(client.get(f"/api/v1/receipts/generate?person_id={person['id']}&kind=issue",
                            headers=admin_headers).content)
    assert a1["artikelnummer"] in text and a2["artikelnummer"] in text


def test_digitale_unterschrift_bezieht_sich_auf_die_uebergabe(client, admin_headers, db_session):
    person = _person(client, admin_headers, "Dora", "Digital")
    a1 = _artikel(client, admin_headers, db_session, "Signiert eins")
    a2 = _artikel(client, admin_headers, db_session, "Signiert zwei")
    d = client.post("/api/v1/issues/batch", json={
        "person_id": person["id"],
        "items": [{"article_id": a1["id"]}, {"article_id": a2["id"]}],
    }, headers=admin_headers).json()

    r = client.post("/api/v1/receipts/digital", json={
        "person_id": person["id"], "kind": "issue", "copies": 2,
        "issue_ids": d["issue_ids"][:1],
    }, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["signed"] is True

    abgelegt = client.get(f"/api/v1/receipts?person_id={person['id']}",
                          headers=admin_headers).json()
    assert len(abgelegt) == 1
    datei = client.get(f"/api/v1/receipts/{abgelegt[0]['id']}/file", headers=admin_headers)
    assert datei.status_code == 200
    text = _text(datei.content)
    assert a1["artikelnummer"] in text


def test_unsinnige_vorgangsnummern_werden_ignoriert(client, admin_headers, db_session):
    """Ein Beleg darf an einer krummen Angabe nicht scheitern - er faellt dann auf
    den Tagesstand zurueck, statt gar nichts zu liefern."""
    person = _person(client, admin_headers, "Emil", "Egal")
    a = _artikel(client, admin_headers, db_session, "Irgendwas E")
    client.post("/api/v1/issues/issue",
                json={"article_id": a["id"], "person_id": person["id"]}, headers=admin_headers)
    r = client.get(
        f"/api/v1/receipts/generate?person_id={person['id']}&kind=issue&issue_ids=abc,,-1",
        headers=admin_headers)
    assert r.status_code == 200
    assert a["artikelnummer"] in _text(r.content)


def test_fremde_vorgaenge_landen_nicht_auf_dem_blatt(client, admin_headers, db_session):
    """Es werden nur Vorgaenge DIESER Person beruecksichtigt."""
    eine = _person(client, admin_headers, "Frida", "Eins")
    andere = _person(client, admin_headers, "Gustav", "Zwei")
    a1 = _artikel(client, admin_headers, db_session, "Gehört Frida")
    a2 = _artikel(client, admin_headers, db_session, "Gehört Gustav")
    v1 = client.post("/api/v1/issues/issue",
                     json={"article_id": a1["id"], "person_id": eine["id"]},
                     headers=admin_headers).json()
    v2 = client.post("/api/v1/issues/issue",
                     json={"article_id": a2["id"], "person_id": andere["id"]},
                     headers=admin_headers).json()
    text = _text(client.get(
        f"/api/v1/receipts/generate?person_id={eine['id']}&kind=issue"
        f"&issue_ids={v1['id']},{v2['id']}", headers=admin_headers).content)
    assert a1["artikelnummer"] in text
    assert a2["artikelnummer"] not in text
