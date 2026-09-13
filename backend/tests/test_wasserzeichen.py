"""Monochrome Wasserzeichen.

Ein Wasserzeichen hat genau eine Aufgabe: auf einem Stapel Ausdrucke soll man
das richtige Blatt sehen, ohne zu lesen. Daraus folgen die Zusicherungen hier:

* Jedes mitgelieferte Motiv muss tatsaechlich etwas zeichnen - ein Motiv, das
  nichts malt, faellt sonst erst auf dem Papier auf.
* Der Text muss vollstaendig lesbar bleiben. Das Wasserzeichen gehoert HINTER
  den Inhalt; liegt es davor, sind die Mengenangaben eingefaerbt.
* Deckkraft und Groesse muessen begrenzt sein. Ein Wasserzeichen mit 90 %
  Deckkraft ist kein Wasserzeichen mehr.
* Ein einzelner Lagerort muss ein eigenes Motiv bekommen koennen, ohne dass
  dafuer eine eigene Dokumentvorlage noetig waere.
"""

import io

import pytest
from pypdf import PdfReader

from app import models, wasserzeichen
from app.config import BRANDING_DIR


def _text(rohdaten: bytes) -> str:
    leser = PdfReader(io.BytesIO(rohdaten))
    return " ".join((seite.extract_text() or "") for seite in leser.pages)


def _png(farbe=(20, 20, 20, 255), groesse=(40, 40)) -> bytes:
    from PIL import Image
    puffer = io.BytesIO()
    Image.new("RGBA", groesse, farbe).save(puffer, format="PNG")
    return puffer.getvalue()


def _lagerort(client, admin_headers):
    st = client.post("/api/v1/storage-nodes", json={"name": "Gerätehaus", "level": "standort"},
                     headers=admin_headers).json()
    tasche = client.post("/api/v1/storage-nodes",
                         json={"name": "Sanitätstasche", "level": "tasche", "parent_id": st["id"]},
                         headers=admin_headers).json()
    return st, tasche


def _vorlage(client, admin_headers, marke=None):
    katalog = client.get("/api/v1/doc-templates/use-cases", headers=admin_headers).json()
    v = katalog["vordruck"]
    r = client.post("/api/v1/doc-templates", json={
        "use_case": "content_list", "name": "Vordruck", "active": True,
        "header_height_mm": v["header_height_mm"], "footer_height_mm": v["footer_height_mm"],
        "elements": v["elements"], "watermark": marke or {},
    }, headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


# --- Die Motive -------------------------------------------------------------

def test_die_gewuenschten_motive_sind_da(client, admin_headers):
    d = client.get("/api/v1/wasserzeichen", headers=admin_headers).json()
    keys = {m["key"] for m in d["motive"]}
    for erwartet in ("blutstropfen", "schneeflocke", "blutdruckmanschette",
                     "infusionsbeutel", "nadeln", "pflaster"):
        assert erwartet in keys
    assert all(m.get("label") for m in d["motive"])
    assert {p["key"] for p in d["positionen"]} >= {"mitte", "kachel"}


@pytest.mark.parametrize("motiv", [m["key"] for m in wasserzeichen.MOTIVE])
def test_jedes_motiv_zeichnet_wirklich_etwas(motiv):
    """Ein Motiv, das nichts malt, faellt sonst erst auf dem Papier auf."""
    leer = wasserzeichen.seite_pdf({"art": ""}, 595, 842)
    voll = wasserzeichen.seite_pdf({"art": "motiv", "motiv": motiv}, 595, 842)
    assert len(voll) > len(leer) + 120, f"{motiv} zeichnet nichts"


def test_unbekanntes_motiv_faellt_auf_den_standard_zurueck():
    w = wasserzeichen.normalisieren({"art": "motiv", "motiv": "einhorn"})
    assert w["motiv"] == "blutstropfen"


def test_deckkraft_und_groesse_sind_begrenzt():
    w = wasserzeichen.normalisieren({"art": "motiv", "deckkraft": 95, "groesse_mm": 5000})
    assert w["deckkraft"] <= 60
    assert w["groesse_mm"] <= 400
    w = wasserzeichen.normalisieren({"art": "motiv", "deckkraft": 0, "groesse_mm": 1})
    assert w["deckkraft"] >= 1
    assert w["groesse_mm"] >= 10


def test_unsinnige_farbe_wird_ersetzt():
    assert wasserzeichen.normalisieren({"farbe": "rot; DROP TABLE"})["farbe"] == "#999999"


def test_ohne_art_ist_nichts_aktiv():
    assert not wasserzeichen.ist_aktiv({})
    assert not wasserzeichen.ist_aktiv({"art": "bild", "datei": "gibtsnicht.png"})
    assert wasserzeichen.ist_aktiv({"art": "motiv"})


# --- Im fertigen Ausdruck ---------------------------------------------------

def test_wasserzeichen_der_vorlage_landet_auf_dem_blatt(client, admin_headers):
    _st, tasche = _lagerort(client, admin_headers)
    ohne = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/pdf", headers=admin_headers).content
    _vorlage(client, admin_headers, {"art": "motiv", "motiv": "blutstropfen",
                                     "farbe": "#c8102e", "deckkraft": 9})
    mit = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/pdf", headers=admin_headers).content
    assert len(mit) > len(ohne)


def test_der_text_bleibt_vollstaendig_lesbar(client, admin_headers):
    """Das Wasserzeichen liegt hinter dem Inhalt - nicht darueber."""
    _st, tasche = _lagerort(client, admin_headers)
    _vorlage(client, admin_headers, {"art": "motiv", "motiv": "pflaster", "deckkraft": 20})
    roh = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/pdf?format=a4quer",
                     headers=admin_headers).content
    text = _text(roh)
    for angabe in ("Inhaltsliste", "Sanitätstasche", "Gerätehaus", "Bezeichnung", "Differenz"):
        assert angabe in text
    assert len(PdfReader(io.BytesIO(roh)).pages) == 1


def test_lagerort_schlaegt_die_vorlage(client, admin_headers, db_session):
    """Die Sanitaetstasche bekommt ihr eigenes Motiv, ohne eigene Vorlage."""
    _st, tasche = _lagerort(client, admin_headers)
    _vorlage(client, admin_headers, {"art": "motiv", "motiv": "blutstropfen"})
    r = client.put(f"/api/v1/storage-nodes/{tasche['id']}",
                   json={"watermark": {"art": "motiv", "motiv": "blutdruckmanschette",
                                       "deckkraft": 12}}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["watermark"]["motiv"] == "blutdruckmanschette"

    from app import pdf_layout
    node = db_session.get(models.StorageNode, tasche["id"])
    assert pdf_layout.wasserzeichen_fuer(db_session, "content_list",
                                         node.watermark)["motiv"] == "blutdruckmanschette"
    # Leeren heisst: wieder das der Vorlage.
    client.put(f"/api/v1/storage-nodes/{tasche['id']}", json={"watermark": {}},
               headers=admin_headers)
    db_session.expire_all()
    node = db_session.get(models.StorageNode, tasche["id"])
    assert pdf_layout.wasserzeichen_fuer(db_session, "content_list",
                                         node.watermark)["motiv"] == "blutstropfen"


def test_schildchen_bekommt_das_wasserzeichen_auch(client, admin_headers):
    _st, tasche = _lagerort(client, admin_headers)
    ohne = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/schildchen",
                      headers=admin_headers).content
    client.put(f"/api/v1/storage-nodes/{tasche['id']}",
               json={"watermark": {"art": "motiv", "motiv": "schneeflocke"}},
               headers=admin_headers)
    mit = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/schildchen",
                     headers=admin_headers).content
    assert len(mit) > len(ohne)
    assert "Sanitätstasche" in _text(mit)


def test_ohne_wasserzeichen_bleibt_alles_wie_es_war(client, admin_headers):
    _st, tasche = _lagerort(client, admin_headers)
    a = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/pdf", headers=admin_headers)
    b = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/pdf", headers=admin_headers)
    assert a.status_code == 200 and len(a.content) == len(b.content)


def test_vorschau_in_beiden_lagen(client, admin_headers):
    hoch = client.get("/api/v1/wasserzeichen/vorschau?art=motiv&motiv=nadeln",
                      headers=admin_headers)
    quer = client.get("/api/v1/wasserzeichen/vorschau?art=motiv&motiv=nadeln&quer=true",
                      headers=admin_headers)
    assert hoch.status_code == 200 and quer.status_code == 200
    kasten_h = PdfReader(io.BytesIO(hoch.content)).pages[0].mediabox
    kasten_q = PdfReader(io.BytesIO(quer.content)).pages[0].mediabox
    assert float(kasten_h.height) > float(kasten_h.width)
    assert float(kasten_q.width) > float(kasten_q.height)


# --- Eigene Motive ----------------------------------------------------------

def test_eigenes_motiv_hochladen_und_verwenden(client, admin_headers):
    r = client.post("/api/v1/wasserzeichen",
                    files={"file": ("Vereins Logo.png", _png(), "image/png")},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    datei = r.json()["datei"]
    try:
        assert datei.startswith("wm_") and "vereins_logo" in datei
        assert (BRANDING_DIR / datei).exists()
        assert any(e["datei"] == datei for e in r.json()["eigene"])

        vorschau = client.get(f"/api/v1/wasserzeichen/vorschau?art=bild&datei={datei}",
                              headers=admin_headers)
        assert vorschau.status_code == 200
        leer = wasserzeichen.seite_pdf({"art": ""}, 595, 842)
        assert len(vorschau.content) > len(leer)
    finally:
        client.delete(f"/api/v1/wasserzeichen/{datei}", headers=admin_headers)
        assert not (BRANDING_DIR / datei).exists()


def test_nur_bilddateien(client, admin_headers):
    r = client.post("/api/v1/wasserzeichen",
                    files={"file": ("liste.csv", b"a;b;c", "text/csv")},
                    headers=admin_headers)
    assert r.status_code == 400
    r = client.post("/api/v1/wasserzeichen",
                    files={"file": ("falsch.png", b"das ist kein Bild", "image/png")},
                    headers=admin_headers)
    assert r.status_code == 400


def test_geloeschtes_motiv_laesst_keinen_verweis_zurueck(client, admin_headers, db_session):
    """Sonst zeigte eine Vorlage auf eine Datei, die es nicht mehr gibt."""
    datei = client.post("/api/v1/wasserzeichen",
                        files={"file": ("tropfen.png", _png(), "image/png")},
                        headers=admin_headers).json()["datei"]
    vorlage = _vorlage(client, admin_headers, {"art": "bild", "datei": datei})
    assert vorlage["watermark"]["datei"] == datei

    client.delete(f"/api/v1/wasserzeichen/{datei}", headers=admin_headers)
    db_session.expire_all()
    t = db_session.get(models.DocTemplate, vorlage["id"])
    assert not (t.watermark or {}).get("datei")


def test_hochladen_nur_fuer_den_administrator(client, admin_headers, db_session):
    from app.security import hash_secret
    db_session.add(models.User(username="helfer", full_name="H. Elfer", roles=["lesend"],
                               password_hash=hash_secret("helfer1234"), active=True))
    db_session.commit()
    tok = client.post("/api/v1/auth/login",
                      json={"username": "helfer", "password": "helfer1234"}).json()
    kopf = {"Authorization": f"Bearer {tok['access_token']}"}
    r = client.post("/api/v1/wasserzeichen",
                    files={"file": ("x.png", _png(), "image/png")}, headers=kopf)
    assert r.status_code == 403
    # Ansehen darf er, sonst kann er die Vorschau seiner Liste nicht oeffnen.
    assert client.get("/api/v1/wasserzeichen", headers=kopf).status_code == 200


def test_fremde_dateien_lassen_sich_nicht_loeschen(client, admin_headers):
    """Der Loeschweg darf nur an die eigenen Motive kommen."""
    r = client.delete("/api/v1/wasserzeichen/logo.png", headers=admin_headers)
    assert r.status_code == 400
    r = client.delete("/api/v1/wasserzeichen/..%2F..%2Fetc%2Fpasswd", headers=admin_headers)
    assert r.status_code in (400, 404)
