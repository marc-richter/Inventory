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


# --------------------------- Schlagworte und Datum --------------------------

def test_schlagworte_und_datum_werden_gespeichert(client, admin_headers):
    d = _ablegen(client, admin_headers, "TÜV-Bericht MTW", "nachweis",
                 doc_date="2026-03-12", tags="TÜV, MTW, Werkstatt Müller")
    assert d["tags"] == ["TÜV", "MTW", "Werkstatt Müller"]
    assert d["doc_date"].startswith("2026-03-12")


def test_doppelte_schlagworte_fliegen_raus(client, admin_headers):
    """„TÜV" und „tüv" sind dasselbe Schlagwort - sonst steht beides in der
    Auswahlliste und die Suche findet nur die Hälfte."""
    d = _ablegen(client, admin_headers, "Bericht", "nachweis", tags="TÜV, tüv,  TÜV , MTW")
    assert d["tags"] == ["TÜV", "MTW"]


def test_datum_auch_deutsch_geschrieben(client, admin_headers):
    d = _ablegen(client, admin_headers, "Rechnung", "nachweis", doc_date="12.03.2026")
    assert d["doc_date"].startswith("2026-03-12")


def test_unbrauchbares_datum_wird_gemeldet(client, admin_headers):
    r = client.post("/api/v1/dokumente", files=_datei(text="x"),
                    data={"title": "Krumm", "doc_date": "letzten Dienstag"},
                    headers=admin_headers)
    assert r.status_code == 400
    assert "Datum" in r.json()["detail"]


def test_ohne_datum_geht_auch(client, admin_headers):
    d = _ablegen(client, admin_headers, "Anleitung ohne Datum", "anleitung")
    assert d["doc_date"] is None
    assert d["tags"] == []


def test_nach_schlagwort_filtern(client, admin_headers):
    _ablegen(client, admin_headers, "TÜV 2026", "nachweis", tags="TÜV")
    _ablegen(client, admin_headers, "Ölwechsel 2026", "nachweis", tags="Werkstatt")
    r = client.get("/api/v1/dokumente?tag=t%C3%BCv", headers=admin_headers)
    assert r.status_code == 200
    assert [x["title"] for x in r.json()] == ["TÜV 2026"]


def test_suche_findet_auch_schlagworte(client, admin_headers):
    _ablegen(client, admin_headers, "Bericht A", "nachweis", tags="Winterreifen")
    _ablegen(client, admin_headers, "Bericht B", "nachweis", tags="Sommerreifen")
    r = client.get("/api/v1/dokumente?q=winter", headers=admin_headers)
    assert [x["title"] for x in r.json()] == ["Bericht A"]


def test_schlagwort_katalog_mit_anzahl(client, admin_headers):
    _ablegen(client, admin_headers, "A", "nachweis", tags="TÜV, MTW")
    _ablegen(client, admin_headers, "B", "nachweis", tags="tüv")
    liste = client.get("/api/v1/dokumente/tags", headers=admin_headers).json()
    nach_tag = {t["tag"]: t["anzahl"] for t in liste}
    # Beide Schreibweisen zählen auf ein Schlagwort; angezeigt wird die häufigste.
    assert nach_tag.get("TÜV") == 2
    assert nach_tag.get("MTW") == 1
    assert liste[0]["tag"] == "TÜV"     # häufigstes zuerst


def test_sortierung_nach_datum_zeigt_den_letzten_bericht_oben(client, admin_headers):
    _ablegen(client, admin_headers, "TÜV 2022", "nachweis", doc_date="2022-03-01", tags="TÜV")
    _ablegen(client, admin_headers, "TÜV 2026", "nachweis", doc_date="2026-03-12", tags="TÜV")
    _ablegen(client, admin_headers, "TÜV 2024", "nachweis", doc_date="2024-03-05", tags="TÜV")
    r = client.get("/api/v1/dokumente?tag=T%C3%9CV&sortierung=datum", headers=admin_headers)
    assert [x["title"] for x in r.json()] == ["TÜV 2026", "TÜV 2024", "TÜV 2022"]


def test_am_artikel_steht_der_neueste_bericht_oben(client, admin_headers, db_session):
    kat = _kategorie(db_session, "fahrzeuge")
    typ = _typ(client, admin_headers, kat.id, "MTW")
    a = _artikel(client, admin_headers, kat.id, typ)
    for titel, datum in (("TÜV 2022", "2022-03-01"), ("TÜV 2026", "2026-03-12"),
                         ("TÜV 2024", "2024-03-05")):
        r = client.post(f"/api/v1/articles/{a['id']}/dokumente",
                        files=_datei(f"{titel}.pdf", titel),
                        data={"title": titel, "art": "nachweis", "doc_date": datum,
                              "tags": "TÜV"},
                        headers=admin_headers)
        assert r.status_code == 200, r.text
    liste = client.get(f"/api/v1/articles/{a['id']}/dokumente", headers=admin_headers).json()
    assert [x["title"] for x in liste] == ["TÜV 2026", "TÜV 2024", "TÜV 2022"]
    assert liste[0]["tags"] == ["TÜV"]


def test_schlagworte_nachtraeglich_aendern(client, admin_headers):
    d = _ablegen(client, admin_headers, "Bericht", "nachweis", tags="alt")
    r = client.put(f"/api/v1/dokumente/{d['id']}", json={"tags": ["TÜV", "tüv", "MTW"]},
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["tags"] == ["TÜV", "MTW"]


# --------------------------- Beleg zum Vorgang ------------------------------

def _fahrzeug_mit_vorgang(client, admin_headers, db_session):
    kat = _kategorie(db_session, "fahrzeuge")
    typ = _typ(client, admin_headers, kat.id, "MTW")
    a = client.post("/api/v1/articles",
                    json={"category_id": kat.id, "type_id": typ, "is_vehicle": True,
                          "license_plate": "HN-DRK 4711"}, headers=admin_headers).json()
    r = client.post(f"/api/v1/logbook/{a['id']}",
                    json={"kind": "wartung", "title": "Hauptuntersuchung (HU)",
                          "note": "bestanden", "entry_date": "2026-03-12T00:00:00"},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    return a, r.json()


def test_beleg_haengt_am_vorgang(client, admin_headers, db_session):
    """Welcher TÜV-Bericht gehört zu welcher HU - ohne das liegen nach fünf
    Jahren sieben Berichte am Fahrzeug und niemand weiß es."""
    a, eintrag = _fahrzeug_mit_vorgang(client, admin_headers, db_session)
    r = client.post(f"/api/v1/articles/{a['id']}/dokumente",
                    files=_datei("tuev.pdf", "TÜV-Bericht"),
                    data={"title": "TÜV-Bericht 2026", "art": "nachweis",
                          "doc_date": "2026-03-12", "tags": "TÜV",
                          "log_entry_id": str(eintrag["id"])},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["log_entry_id"] == eintrag["id"]
    assert d["vorgang"] == "Hauptuntersuchung (HU) am 12.03.2026"

    liste = client.get(f"/api/v1/articles/{a['id']}/dokumente", headers=admin_headers).json()
    assert liste[0]["vorgang"] == "Hauptuntersuchung (HU) am 12.03.2026"


def test_beleg_ohne_vorgang_bleibt_moeglich(client, admin_headers, db_session):
    a, _eintrag = _fahrzeug_mit_vorgang(client, admin_headers, db_session)
    r = client.post(f"/api/v1/articles/{a['id']}/dokumente", files=_datei(),
                    data={"title": "Rechnung", "art": "nachweis"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["vorgang"] == ""
    assert r.json()["log_entry_id"] is None


def test_fremder_vorgang_wird_abgelehnt(client, admin_headers, db_session):
    """Ein Vorgang eines anderen Fahrzeugs darf hier nicht landen."""
    a, _e = _fahrzeug_mit_vorgang(client, admin_headers, db_session)
    b, eintrag_b = _fahrzeug_mit_vorgang(client, admin_headers, db_session)
    r = client.post(f"/api/v1/articles/{a['id']}/dokumente", files=_datei(),
                    data={"title": "Falsch", "log_entry_id": str(eintrag_b["id"])},
                    headers=admin_headers)
    assert r.status_code == 400
    assert "gehört nicht zu diesem Artikel" in r.json()["detail"]
