"""Dokumente an Artikeln: zentrale Ablage, Zuordnung auf drei Ebenen."""

import io

from app import models


def _pdf(text: str = "Pflegehinweis") -> bytes:
    """Ein winziges, gueltiges PDF - echter Inhalt, keine Attrappe."""
    from reportlab.pdfgen import canvas
    puffer = io.BytesIO()
    c = canvas.Canvas(puffer)
    c.drawString(80, 800, text)
    c.save()
    return puffer.getvalue()


def _datei(name="hinweis.pdf", text="Pflegehinweis"):
    return {"file": (name, io.BytesIO(_pdf(text)), "application/pdf")}


def _kategorie(db_session, system_key):
    return db_session.query(models.Category).filter(
        models.Category.system_key == system_key).first()


def _typ(client, admin_headers, kat_id, name):
    r = client.post("/api/v1/types", json={"name": name, "category_id": kat_id},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _artikel(client, admin_headers, kat_id, typ_id):
    r = client.post("/api/v1/articles", json={"category_id": kat_id, "type_id": typ_id},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


def _ablegen(client, admin_headers, titel="Pflege Einsatzjacke", art="pflege", **felder):
    daten = {"title": titel, "art": art}
    daten.update(felder)
    r = client.post("/api/v1/dokumente", files=_datei(text=titel), data=daten,
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------- Ablage -----------------------------------------

def test_dokument_ablegen_und_wieder_lesen(client, admin_headers):
    d = _ablegen(client, admin_headers, "Pflege Einsatzjacke", "pflege",
                 stand="Stand 03/2026", note="Bei 30 Grad, kein Weichspüler")
    assert d["title"] == "Pflege Einsatzjacke"
    assert d["art_label"] == "Pflegehinweis"
    assert d["size_bytes"] > 0
    assert d["zentral"] is True
    assert d["stand"] == "Stand 03/2026"

    r = client.get("/api/v1/dokumente", headers=admin_headers)
    assert r.status_code == 200
    assert [x["id"] for x in r.json()] == [d["id"]]

    r = client.get(f"/api/v1/dokumente/{d['id']}/datei", headers=admin_headers)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"
    assert r.headers["content-type"] == "application/pdf"


def test_nur_pdf_wird_angenommen(client, admin_headers):
    r = client.post("/api/v1/dokumente",
                    files={"file": ("bild.pdf", io.BytesIO(b"\x89PNG\r\n\x1a\n irgendwas"),
                                    "application/pdf")},
                    data={"title": "Kein PDF"}, headers=admin_headers)
    assert r.status_code == 400
    assert "PDF" in r.json()["detail"]


def test_dieselbe_datei_zweimal_wird_gemeldet(client, admin_headers):
    """Wer dieselbe Datei ein zweites Mal hochlaedt, bekommt einen Hinweis statt
    einer zweiten Karteileiche. Verglichen werden die Bytes - genau das trifft den
    Fall, um den es geht: dieselbe Datei nochmal ausgewaehlt."""
    roh = _pdf("Pflege Einsatzjacke")
    r = client.post("/api/v1/dokumente",
                    files={"file": ("hinweis.pdf", io.BytesIO(roh), "application/pdf")},
                    data={"title": "Pflege Einsatzjacke", "art": "pflege"},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    r = client.post("/api/v1/dokumente",
                    files={"file": ("hinweis.pdf", io.BytesIO(roh), "application/pdf")},
                    data={"title": "Nochmal dasselbe", "art": "pflege"},
                    headers=admin_headers)
    assert r.status_code == 400
    assert "Pflege Einsatzjacke" in r.json()["detail"]
    assert "Neue Fassung" in r.json()["detail"]


def test_neue_fassung_behaelt_die_zuordnungen(client, admin_headers, db_session):
    """Der eigentliche Gewinn der Ablage: die Datei wird ersetzt, nicht die Zuordnung."""
    kat = _kategorie(db_session, "kleidung")
    d = _ablegen(client, admin_headers)
    r = client.put(f"/api/v1/dokumente/{d['id']}/zuordnungen",
                   json={"category_ids": [kat.id], "type_ids": []}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert len(r.json()["zuordnungen"]) == 1

    alte_groesse = d["size_bytes"]
    r = client.post(f"/api/v1/dokumente/{d['id']}/datei",
                    files=_datei("neu.pdf", "Pflegehinweis Fassung 2 mit mehr Text darin"),
                    data={"stand": "Stand 09/2026"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    neu = r.json()
    assert neu["stand"] == "Stand 09/2026"
    assert neu["size_bytes"] != alte_groesse or neu["original_name"] == "neu.pdf"
    # Und die Zuordnung steht noch.
    assert len(neu["zuordnungen"]) == 1
    assert neu["zuordnungen"][0]["ebene"] == "klasse"


# --------------------------- Drei Ebenen ------------------------------------

def test_dokument_an_der_klasse_gilt_fuer_alle_artikel(client, admin_headers, db_session):
    kat = _kategorie(db_session, "kleidung")
    typ = _typ(client, admin_headers, kat.id, "Einsatzjacke")
    a = _artikel(client, admin_headers, kat.id, typ)
    b = _artikel(client, admin_headers, kat.id, typ)
    d = _ablegen(client, admin_headers, "Desinfektion Kleidung", "desinfektion")
    client.put(f"/api/v1/dokumente/{d['id']}/zuordnungen",
               json={"category_ids": [kat.id]}, headers=admin_headers)

    for art in (a, b):
        r = client.get(f"/api/v1/articles/{art['id']}/dokumente", headers=admin_headers)
        assert r.status_code == 200, r.text
        assert [x["title"] for x in r.json()] == ["Desinfektion Kleidung"]
        assert r.json()[0]["herkunft"] == "klasse"
        assert r.json()[0]["herkunft_name"] == kat.name
        # Aus der Klasse laesst sich die Zuordnung am Artikel nicht loesen.
        assert r.json()[0]["link_id"] is None


def test_unterklasse_erbt_die_dokumente_der_oberklasse(client, admin_headers, db_session):
    funk = _kategorie(db_session, "funk")
    akkus = _kategorie(db_session, "funk_akkus")
    typ = _typ(client, admin_headers, akkus.id, "Akku BL-5")
    a = _artikel(client, admin_headers, akkus.id, typ)
    d = _ablegen(client, admin_headers, "Umgang mit Funkgeräten", "anleitung")
    client.put(f"/api/v1/dokumente/{d['id']}/zuordnungen",
               json={"category_ids": [funk.id]}, headers=admin_headers)

    r = client.get(f"/api/v1/articles/{a['id']}/dokumente", headers=admin_headers)
    assert [x["title"] for x in r.json()] == ["Umgang mit Funkgeräten"]
    assert r.json()[0]["herkunft_name"] == funk.name


def test_dokument_am_typ(client, admin_headers, db_session):
    kat = _kategorie(db_session, "kleidung")
    jacke = _typ(client, admin_headers, kat.id, "Einsatzjacke")
    hose = _typ(client, admin_headers, kat.id, "Einsatzhose")
    a = _artikel(client, admin_headers, kat.id, jacke)
    b = _artikel(client, admin_headers, kat.id, hose)
    d = _ablegen(client, admin_headers, "Pflege Einsatzjacke", "pflege")
    client.put(f"/api/v1/dokumente/{d['id']}/zuordnungen",
               json={"type_ids": [jacke]}, headers=admin_headers)

    assert [x["title"] for x in client.get(
        f"/api/v1/articles/{a['id']}/dokumente", headers=admin_headers).json()] \
        == ["Pflege Einsatzjacke"]
    assert client.get(f"/api/v1/articles/{b['id']}/dokumente",
                      headers=admin_headers).json() == []


def test_speziellste_ebene_gewinnt(client, admin_headers, db_session):
    """Dasselbe Dokument ueber Klasse UND Artikel: es steht einmal da, als Artikel-
    Zuordnung - sonst liesse es sich am Artikel nicht mehr loesen."""
    kat = _kategorie(db_session, "kleidung")
    typ = _typ(client, admin_headers, kat.id, "Einsatzjacke")
    a = _artikel(client, admin_headers, kat.id, typ)
    d = _ablegen(client, admin_headers)
    client.put(f"/api/v1/dokumente/{d['id']}/zuordnungen",
               json={"category_ids": [kat.id], "type_ids": [typ]}, headers=admin_headers)
    client.post(f"/api/v1/articles/{a['id']}/dokumente/{d['id']}", headers=admin_headers)

    liste = client.get(f"/api/v1/articles/{a['id']}/dokumente", headers=admin_headers).json()
    assert len(liste) == 1
    assert liste[0]["herkunft"] == "artikel"
    assert liste[0]["link_id"] is not None


# --------------------------- Eigene PDF am Artikel --------------------------

def test_eigene_pdf_am_artikel(client, admin_headers, db_session):
    kat = _kategorie(db_session, "fahrzeuge")
    typ = _typ(client, admin_headers, kat.id, "MTW")
    a = _artikel(client, admin_headers, kat.id, typ)
    r = client.post(f"/api/v1/articles/{a['id']}/dokumente",
                    files=_datei("rechnung.pdf", "Rechnung"),
                    data={"title": "Rechnung Autohaus", "art": "nachweis"},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["zentral"] is False
    assert d["herkunft"] == "artikel"

    # In der zentralen Ablage taucht sie NICHT auf - dort gehoert nur hin, was
    # wiederverwendet wird.
    assert client.get("/api/v1/dokumente", headers=admin_headers).json() == []
    assert [x["title"] for x in client.get(
        f"/api/v1/articles/{a['id']}/dokumente", headers=admin_headers).json()] \
        == ["Rechnung Autohaus"]


def test_eigene_pdf_laesst_sich_nicht_weiterverteilen(client, admin_headers, db_session):
    kat = _kategorie(db_session, "kleidung")
    typ = _typ(client, admin_headers, kat.id, "Einsatzjacke")
    a = _artikel(client, admin_headers, kat.id, typ)
    b = _artikel(client, admin_headers, kat.id, typ)
    d = client.post(f"/api/v1/articles/{a['id']}/dokumente", files=_datei(),
                    data={"title": "Nur hier"}, headers=admin_headers).json()
    r = client.post(f"/api/v1/articles/{b['id']}/dokumente/{d['id']}", headers=admin_headers)
    assert r.status_code == 400
    assert "Ablage" in r.json()["detail"]


def test_letzte_zuordnung_loesen_raeumt_die_eigene_pdf_weg(client, admin_headers, db_session):
    kat = _kategorie(db_session, "kleidung")
    typ = _typ(client, admin_headers, kat.id, "Einsatzjacke")
    a = _artikel(client, admin_headers, kat.id, typ)
    d = client.post(f"/api/v1/articles/{a['id']}/dokumente", files=_datei(),
                    data={"title": "Nur hier"}, headers=admin_headers).json()
    r = client.delete(f"/api/v1/dokumente/zuordnungen/{d['link_id']}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["dokument_geloescht"] is True
    assert db_session.get(models.Document, d["id"]) is None


def test_zuordnung_eines_zentralen_dokuments_loeschen_laesst_es_stehen(
        client, admin_headers, db_session):
    kat = _kategorie(db_session, "kleidung")
    typ = _typ(client, admin_headers, kat.id, "Einsatzjacke")
    a = _artikel(client, admin_headers, kat.id, typ)
    d = _ablegen(client, admin_headers)
    client.post(f"/api/v1/articles/{a['id']}/dokumente/{d['id']}", headers=admin_headers)
    liste = client.get(f"/api/v1/articles/{a['id']}/dokumente", headers=admin_headers).json()
    r = client.delete(f"/api/v1/dokumente/zuordnungen/{liste[0]['link_id']}",
                      headers=admin_headers)
    assert r.json()["dokument_geloescht"] is False
    assert client.get(f"/api/v1/articles/{a['id']}/dokumente",
                      headers=admin_headers).json() == []
    # In der Ablage liegt es weiter.
    assert [x["id"] for x in client.get("/api/v1/dokumente",
                                        headers=admin_headers).json()] == [d["id"]]


# --------------------------- Ablage pflegen ---------------------------------

def test_ablage_zeigt_fuer_wie_viele_artikel_ein_dokument_gilt(client, admin_headers, db_session):
    kat = _kategorie(db_session, "kleidung")
    typ = _typ(client, admin_headers, kat.id, "Einsatzjacke")
    for _ in range(3):
        _artikel(client, admin_headers, kat.id, typ)
    d = _ablegen(client, admin_headers)
    client.put(f"/api/v1/dokumente/{d['id']}/zuordnungen",
               json={"category_ids": [kat.id]}, headers=admin_headers)
    eintrag = client.get("/api/v1/dokumente", headers=admin_headers).json()[0]
    assert eintrag["artikel_anzahl"] == 3


def test_dokument_loeschen_entfernt_es_ueberall(client, admin_headers, db_session):
    kat = _kategorie(db_session, "kleidung")
    typ = _typ(client, admin_headers, kat.id, "Einsatzjacke")
    a = _artikel(client, admin_headers, kat.id, typ)
    d = _ablegen(client, admin_headers)
    client.put(f"/api/v1/dokumente/{d['id']}/zuordnungen",
               json={"category_ids": [kat.id]}, headers=admin_headers)
    assert client.delete(f"/api/v1/dokumente/{d['id']}",
                         headers=admin_headers).status_code == 200
    assert client.get(f"/api/v1/articles/{a['id']}/dokumente",
                      headers=admin_headers).json() == []
    assert db_session.query(models.DocumentLink).count() == 0


def test_inaktives_dokument_erscheint_nicht_mehr_am_artikel(client, admin_headers, db_session):
    kat = _kategorie(db_session, "kleidung")
    typ = _typ(client, admin_headers, kat.id, "Einsatzjacke")
    a = _artikel(client, admin_headers, kat.id, typ)
    d = _ablegen(client, admin_headers)
    client.put(f"/api/v1/dokumente/{d['id']}/zuordnungen",
               json={"category_ids": [kat.id]}, headers=admin_headers)
    client.put(f"/api/v1/dokumente/{d['id']}", json={"active": False}, headers=admin_headers)
    assert client.get(f"/api/v1/articles/{a['id']}/dokumente",
                      headers=admin_headers).json() == []


def test_arten_katalog(client, admin_headers):
    arten = client.get("/api/v1/dokumente/arten", headers=admin_headers).json()
    keys = [a["key"] for a in arten]
    assert "pflege" in keys and "desinfektion" in keys and "anleitung" in keys
    assert keys[-1] == "sonstiges"


def test_unbekannte_art_faellt_auf_sonstiges(client, admin_headers):
    d = _ablegen(client, admin_headers, "Irgendwas", "voellig_ausgedacht")
    assert d["art"] == "sonstiges"


def test_dokumente_liegen_im_backup(client, admin_headers, db_session, tmp_path):
    """Ohne die Dateien im Backup zeigen die Artikel nach einer Wiederherstellung
    auf PDFs, die es nicht mehr gibt."""
    from app import backup as sicherung
    from app.config import DOKUMENTE_DIR
    _ablegen(client, admin_headers, "Pflege Einsatzjacke", "pflege")
    dok = db_session.query(models.Document).first()
    assert (DOKUMENTE_DIR / dok.filename).exists()

    import zipfile
    from app.settings_helper import set_setting
    set_setting(db_session, "backup_dir", str(tmp_path))
    rec = sicherung.create_backup(db_session, kind="test")
    with zipfile.ZipFile(tmp_path / rec.filename) as zf:
        namen = zf.namelist()
    assert f"dokumente/{dok.filename}" in namen

    pruefung = sicherung.verify_backup(tmp_path / rec.filename)
    dok_check = [c for c in pruefung["checks"] if c["name"] == "has_dokumente"]
    assert dok_check and dok_check[0]["ok"] is True
