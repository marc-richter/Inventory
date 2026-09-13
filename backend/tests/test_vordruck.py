"""Der Vordruck: ein Blatt, zwei Lagen.

Geprueft wird dreierlei:

1. Dieselbe Vorlage muss im Hoch- UND im Querformat dieselben Elemente zeigen.
   Frueher lagen dafuer zwei getrennte Entwuerfe vor, und dem querformatigen
   fehlten Lagerortangabe und Legende - genau das soll nicht wieder passieren.
2. Die Platzhalter muessen mit echten Werten gefuellt werden. Ein Ausdruck, auf
   dem "{version}" steht, ist ein Fehler und kein Layout.
3. Die Farblegende muss etwas bedeuten: eine Zeile wird nur eingefaerbt, wenn
   fuer den Artikeltyp tatsaechlich eine Pruefart der passenden Art gilt.
"""

import io

import pytest
from pypdf import PdfReader

from app import models, pdf_layout
from app.routers.inventory.inhaltslisten import pruefart_je_typ


def _text_der_seiten(rohdaten: bytes):
    leser = PdfReader(io.BytesIO(rohdaten))
    return [(seite.extract_text() or "") for seite in leser.pages]


def _seitenmasse(rohdaten: bytes):
    leser = PdfReader(io.BytesIO(rohdaten))
    kasten = leser.pages[0].mediabox
    return float(kasten.width), float(kasten.height)


@pytest.fixture
def vordruck_aktiv(client, admin_headers):
    """Legt den mitgelieferten Vordruck als Vorlage fuer Inhaltslisten an."""
    katalog = client.get("/api/v1/doc-templates/use-cases", headers=admin_headers).json()
    vordruck = katalog["vordruck"]
    r = client.post("/api/v1/doc-templates", json={
        "use_case": "content_list", "name": "Vordruck", "active": True,
        "header_height_mm": vordruck["header_height_mm"],
        "footer_height_mm": vordruck["footer_height_mm"],
        "elements": vordruck["elements"],
    }, headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


def _lagerort(client, admin_headers):
    st = client.post("/api/v1/storage-nodes",
                     json={"name": "Gerätehaus", "level": "standort"},
                     headers=admin_headers).json()
    fahrzeug = client.post("/api/v1/storage-nodes",
                           json={"name": "KTW 1", "level": "fahrzeug", "parent_id": st["id"]},
                           headers=admin_headers).json()
    tasche = client.post("/api/v1/storage-nodes",
                         json={"name": "Seitentasche links", "level": "tasche",
                               "parent_id": fahrzeug["id"]},
                         headers=admin_headers).json()
    return st, fahrzeug, tasche


# --- Platzhalter ------------------------------------------------------------

def test_katalog_nennt_alle_platzhalter_mit_erklaerung(client, admin_headers):
    d = client.get("/api/v1/doc-templates/use-cases", headers=admin_headers).json()
    keys = {p["key"] for p in d["platzhalter"]}
    # Genau die Angaben, die auf dem Vordruck bisher unspezifisch waren.
    for erwartet in ("version", "titel", "lagername", "fahrzeug", "standort",
                     "organisation", "adresse1", "stand", "dateiname", "seite"):
        assert erwartet in keys
    assert all(p.get("hint") for p in d["platzhalter"]), "jeder Platzhalter braucht eine Erklärung"


def test_die_legende_steht_als_ein_block_im_vordruck(client, admin_headers):
    """Eine Legende, nicht zwei einzelne Farbfelder: nur so stehen die Kästchen
    in einer Spalte. Rechtsbündig einzeln gesetzt würden sich die Textenden
    ausrichten und die Kästchen um den Längenunterschied der Wörter versetzen."""
    d = client.get("/api/v1/doc-templates/use-cases", headers=admin_headers).json()
    legenden = [e for e in d["vordruck"]["elements"] if e.get("type") == "legende"]
    assert len(legenden) == 1
    texte = [e["text"] for e in legenden[0]["eintraege"]]
    assert texte == ["Verfall prüfen", "Funktion prüfen"]
    assert not [e for e in d["vordruck"]["elements"] if e.get("type") == "farbfeld"]


def test_legende_wird_gezeichnet(client, admin_headers, vordruck_aktiv):
    _st, _fz, tasche = _lagerort(client, admin_headers)
    text = " ".join(_text_der_seiten(client.get(
        f"/api/v1/inhaltslisten/{tasche['id']}/pdf?format=a4quer",
        headers=admin_headers).content))
    assert "Verfall prüfen" in text and "Funktion prüfen" in text


def test_leere_legende_bricht_nichts(client, admin_headers, db_session):
    """Ein Element ohne Einträge darf das Dokument nicht verhindern."""
    from app import models, pdf_layout
    t = models.DocTemplate(use_case="content_list", name="Leer", active=True,
                           header_height_mm=20, footer_height_mm=20,
                           elements=[{"region": "footer", "type": "legende", "x": 15, "y": 10,
                                      "eintraege": []}])
    db_session.add(t)
    db_session.commit()
    st = client.post("/api/v1/storage-nodes", json={"name": "L", "level": "standort"},
                     headers=admin_headers).json()
    assert client.get(f"/api/v1/inhaltslisten/{st['id']}/pdf",
                      headers=admin_headers).status_code == 200


def test_jeder_platzhalter_im_vordruck_ist_bekannt(client, admin_headers):
    """Ein Tippfehler im Vordruck wuerde sonst als leerer Text durchgehen."""
    import re
    d = client.get("/api/v1/doc-templates/use-cases", headers=admin_headers).json()
    bekannt = {p["key"] for p in d["platzhalter"]}
    for el in d["vordruck"]["elements"]:
        for name in re.findall(r"\{([a-z0-9_]+)\}", el.get("text") or ""):
            assert name in bekannt, f"unbekannter Platzhalter {{{name}}} im Vordruck"


def test_standardwerte_fuellen_version_und_stand(db_session):
    werte = pdf_layout.standardwerte(db_session, "content_list")
    assert werte["version"] and werte["version"] != "{version}"
    assert len(werte["stand"].split(".")) == 3
    assert werte["dateiname"].endswith(".pdf")


def test_werte_des_builders_gehen_vor(db_session):
    werte = pdf_layout.standardwerte(db_session, "content_list",
                                     lagername="Tasche 3", fahrzeug="", dateiname="x.pdf")
    assert werte["lagername"] == "Tasche 3"
    assert werte["fahrzeug"] == ""          # leer bleibt leer, nichts wird erfunden
    assert werte["dateiname"] == "x.pdf"


# --- Hoch und Quer sind dasselbe Blatt --------------------------------------

def test_inhaltsliste_quer_zeigt_dieselben_angaben_wie_hoch(
        client, admin_headers, vordruck_aktiv):
    _st, _fz, tasche = _lagerort(client, admin_headers)

    hoch = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/pdf?format=a4",
                      headers=admin_headers)
    quer = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/pdf?format=a4quer",
                      headers=admin_headers)
    assert hoch.status_code == 200 and quer.status_code == 200

    t_hoch = " ".join(_text_der_seiten(hoch.content))
    t_quer = " ".join(_text_der_seiten(quer.content))
    for angabe in ("Inhaltsliste", "Seitentasche links", "KTW 1", "Gerätehaus",
                   "Verfall prüfen", "Funktion prüfen", "Stand", "Version"):
        assert angabe in t_hoch, f"{angabe} fehlt im Hochformat"
        assert angabe in t_quer, f"{angabe} fehlt im Querformat"

    # Wirklich gedreht - und nicht etwa zweimal dasselbe Format.
    b_hoch, h_hoch = _seitenmasse(hoch.content)
    b_quer, h_quer = _seitenmasse(quer.content)
    assert h_hoch > b_hoch and b_quer > h_quer


def test_platzhalter_bleiben_nicht_stehen(client, admin_headers, vordruck_aktiv):
    _st, _fz, tasche = _lagerort(client, admin_headers)
    for format in ("a4", "a4quer", "a5", "a5quer"):
        r = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/pdf?format={format}",
                       headers=admin_headers)
        text = " ".join(_text_der_seiten(r.content))
        assert "{" not in text, f"ungefüllter Platzhalter im Format {format}"


def test_version_steht_auf_dem_ausdruck(client, admin_headers, vordruck_aktiv):
    from app.config import get_app_version
    _st, _fz, tasche = _lagerort(client, admin_headers)
    r = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/pdf?format=a4quer",
                   headers=admin_headers)
    assert get_app_version() in " ".join(_text_der_seiten(r.content))


def test_dateiname_nennt_den_lagerort(client, admin_headers):
    _st, _fz, tasche = _lagerort(client, admin_headers)
    r = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/pdf", headers=admin_headers)
    assert "seitentasche-links" in r.headers["content-disposition"]


def test_umlaute_im_lagerort_brechen_den_download_nicht(client, admin_headers):
    """Der Dateiname steht in einer HTTP-Kopfzeile, und die vertraegt nur ASCII.
    Ein Lagerort namens „Sanitätstasche" hatte den Abruf sonst abbrechen lassen."""
    st = client.post("/api/v1/storage-nodes",
                     json={"name": "Sanitätstasche groß/Süd", "level": "standort"},
                     headers=admin_headers).json()
    r = client.get(f"/api/v1/inhaltslisten/{st['id']}/pdf", headers=admin_headers)
    assert r.status_code == 200
    kopf = r.headers["content-disposition"]
    assert kopf.isascii(), kopf
    assert "sanitaetstasche-gross" in kopf
    assert client.get(f"/api/v1/inhaltslisten/{st['id']}/schildchen",
                      headers=admin_headers).status_code == 200


def test_ohne_vorlage_steht_alles_trotzdem_drauf(client, admin_headers):
    """Auch ohne Vordruck darf keine der Angaben fehlen - sonst haengt der
    Informationsgehalt eines Ausdrucks davon ab, ob jemand eine Vorlage angelegt
    hat."""
    _st, _fz, tasche = _lagerort(client, admin_headers)
    r = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/pdf?format=a4quer",
                   headers=admin_headers)
    text = " ".join(_text_der_seiten(r.content))
    for angabe in ("Inhaltsliste", "Seitentasche links", "KTW 1", "Stand", "Version"):
        assert angabe in text


def test_vorschau_gibt_es_in_beiden_lagen(client, admin_headers, vordruck_aktiv):
    for format, quer in (("a4", False), ("a4quer", True)):
        r = client.get(f"/api/v1/doc-templates/preview?use_case=content_list&format={format}",
                       headers=admin_headers)
        assert r.status_code == 200
        breite, hoehe = _seitenmasse(r.content)
        assert (breite > hoehe) is quer
        assert "{" not in " ".join(_text_der_seiten(r.content))


# --- Die Legende bedeutet etwas ---------------------------------------------

def test_pruefart_folgt_der_zuordnung(client, admin_headers, db_session):
    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "sonstiges").first()
    typ = client.post("/api/v1/types", json={"name": "Kompresse", "category_id": kat.id},
                      headers=admin_headers).json()
    # Ohne Zuweisung: keine Farbe.
    assert pruefart_je_typ(db_session, [typ["id"]])[typ["id"]] == ""

    art = models.MaintenanceType(name="Haltbarkeit Kompressen", kind="verfall",
                                 interval_months=6)
    db_session.add(art)
    db_session.flush()
    db_session.add(models.MaintenanceAssignment(mtype_id=art.id, article_type_id=typ["id"],
                                                mode="include"))
    db_session.commit()
    assert pruefart_je_typ(db_session, [typ["id"]])[typ["id"]] == "verfall"


def test_verfall_geht_vor_funktion(client, admin_headers, db_session):
    """Auf Papier hat eine Zeile eine Farbe. Was ablaeuft, ist das Dringendere."""
    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "sonstiges").first()
    typ = client.post("/api/v1/types", json={"name": "Sauerstoffflasche", "category_id": kat.id},
                      headers=admin_headers).json()
    for name, art_kind in (("Funktionsprüfung Flasche", "funktion"),
                           ("TÜV Flasche", "verfall")):
        art = models.MaintenanceType(name=name, kind=art_kind, interval_months=12)
        db_session.add(art)
        db_session.flush()
        db_session.add(models.MaintenanceAssignment(mtype_id=art.id,
                                                    article_type_id=typ["id"], mode="include"))
    db_session.commit()
    assert pruefart_je_typ(db_session, [typ["id"]])[typ["id"]] == "verfall"


def test_zeile_traegt_die_pruefart(client, admin_headers, db_session):
    st = client.post("/api/v1/storage-nodes", json={"name": "Lager A", "level": "standort"},
                     headers=admin_headers).json()
    kat = db_session.query(models.Category).filter(
        models.Category.system_key == "sonstiges").first()
    typ = client.post("/api/v1/types", json={"name": "Rettungsdecke", "category_id": kat.id},
                      headers=admin_headers).json()
    client.post("/api/v1/stats/min-stock-rules",
                json={"type_id": typ["id"], "node_id": st["id"], "min_stock": 2, "size": ""},
                headers=admin_headers)
    art = models.MaintenanceType(name="Haltbarkeit Decke", kind="verfall", interval_months=12)
    db_session.add(art)
    db_session.flush()
    db_session.add(models.MaintenanceAssignment(mtype_id=art.id, article_type_id=typ["id"],
                                                mode="include"))
    db_session.commit()

    d = client.get(f"/api/v1/inhaltslisten/{st['id']}", headers=admin_headers).json()
    assert d["rows"][0]["pruefart"] == "verfall"
    assert {l["key"] for l in d["legende"]} == {"verfall", "funktion"}


def test_pruefart_laesst_sich_pflegen(client, admin_headers):
    r = client.post("/api/v1/maintenance/types",
                    json={"name": "Ablaufkontrolle", "kind": "verfall", "interval_months": 6},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "verfall"
    geaendert = client.put(f"/api/v1/maintenance/types/{r.json()['id']}",
                           json={"kind": "funktion"}, headers=admin_headers)
    assert geaendert.json()["kind"] == "funktion"
    # Unsinn faellt auf den Normalfall zurueck, statt eine kaputte Farbe zu erzeugen.
    unsinn = client.put(f"/api/v1/maintenance/types/{r.json()['id']}",
                        json={"kind": "lila"}, headers=admin_headers)
    assert unsinn.json()["kind"] == "funktion"


def test_mitgelieferte_pruefarten_haben_eine_art(db_session):
    arten = db_session.query(models.MaintenanceType).all()
    assert arten, "die Systemprüfarten sollten vorhanden sein"
    assert all((a.kind or "") in ("funktion", "verfall") for a in arten)
    assert any(a.kind == "verfall" for a in arten), "ohne Verfall-Art bleibt Gelb tot"


# --- Briefkopf: Logo und Schriftzug -----------------------------------------

SVG_LOGO = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <rect x="40" y="10" width="20" height="80" fill="#e3000f"/>
  <rect x="10" y="40" width="80" height="20" fill="#e3000f"/>
</svg>"""


def _logo_hinterlegen(db_session, inhalt: bytes, name: str):
    from app.config import BRANDING_DIR
    from app.settings_helper import set_setting
    BRANDING_DIR.mkdir(parents=True, exist_ok=True)
    (BRANDING_DIR / name).write_bytes(inhalt)
    set_setting(db_session, "logo_filename", name)
    db_session.commit()
    return BRANDING_DIR / name


def _png_logo() -> bytes:
    from PIL import Image
    puffer = io.BytesIO()
    Image.new("RGBA", (120, 120), (227, 0, 15, 255)).save(puffer, format="PNG")
    return puffer.getvalue()


def test_svg_logo_landet_im_pdf(client, admin_headers, db_session, vordruck_aktiv):
    """Ein SVG-Logo liess sich hochladen, fehlte im Ausdruck aber stillschweigend.

    Das ist der unangenehmste Fehlertyp: nichts bricht, es ist nur nichts da.
    """
    from app import pdf_layout
    _st, _fz, tasche = _lagerort(client, admin_headers)
    ohne = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/pdf",
                      headers=admin_headers).content
    pfad = _logo_hinterlegen(db_session, SVG_LOGO.encode("utf-8"), "logo.svg")
    try:
        pdf_layout._SVG_ZEICHNUNGEN.clear()
        art, _quelle, verhaeltnis = pdf_layout._logo_quelle(db_session)
        assert art == "svg" and verhaeltnis
        mit = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/pdf",
                         headers=admin_headers).content
        assert len(mit) > len(ohne) + 200, "das SVG-Logo wurde nicht gezeichnet"
    finally:
        pfad.unlink(missing_ok=True)


def test_png_logo_landet_im_pdf(client, admin_headers, db_session, vordruck_aktiv):
    _st, _fz, tasche = _lagerort(client, admin_headers)
    ohne = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/pdf",
                      headers=admin_headers).content
    pfad = _logo_hinterlegen(db_session, _png_logo(), "logo.png")
    try:
        mit = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/pdf",
                         headers=admin_headers).content
        assert len(mit) > len(ohne) + 200
    finally:
        pfad.unlink(missing_ok=True)


def test_logo_status_meldet_ein_unbrauchbares_logo(client, admin_headers, db_session):
    from app import pdf_layout
    assert client.get("/api/v1/settings/logo/status",
                      headers=admin_headers).json()["vorhanden"] is False
    pfad = _logo_hinterlegen(db_session, b"<svg>kaputt", "logo.svg")
    try:
        pdf_layout._SVG_ZEICHNUNGEN.clear()
        d = client.get("/api/v1/settings/logo/status", headers=admin_headers).json()
        assert d["vorhanden"] is True and d["in_pdf"] is False
        assert "PNG" in d["hinweis"]
    finally:
        pfad.unlink(missing_ok=True)
        pdf_layout._SVG_ZEICHNUNGEN.clear()


def test_verband_und_verein_stehen_im_kopf(client, admin_headers, db_session, vordruck_aktiv):
    """Der Schriftzug neben der Bildmarke: Verband über dem Vereinsnamen."""
    from app.settings_helper import set_setting
    set_setting(db_session, "org_verband", "Deutsches Rotes Kreuz")
    set_setting(db_session, "org_name", "Ortsverein Musterstadt e.V.")
    db_session.commit()
    _st, _fz, tasche = _lagerort(client, admin_headers)
    for format in ("a4", "a4quer"):
        text = " ".join(_text_der_seiten(client.get(
            f"/api/v1/inhaltslisten/{tasche['id']}/pdf?format={format}",
            headers=admin_headers).content))
        assert "Deutsches Rotes Kreuz" in text, f"Verband fehlt im Format {format}"
        assert "Ortsverein Musterstadt e.V." in text


def test_ohne_verband_bleibt_die_zeile_weg(client, admin_headers, db_session, vordruck_aktiv):
    from app.settings_helper import set_setting
    set_setting(db_session, "org_verband", "")
    db_session.commit()
    _st, _fz, tasche = _lagerort(client, admin_headers)
    text = " ".join(_text_der_seiten(client.get(
        f"/api/v1/inhaltslisten/{tasche['id']}/pdf", headers=admin_headers).content))
    assert "{verband}" not in text


# --- Eigener Vordruck als Hintergrund ---------------------------------------

def _briefpapier(breite=595, hoehe=842, text="MEIN VORDRUCK") -> bytes:
    """Ein Blatt, das so tut, als waere es der Vordruck aus dem Verein."""
    from reportlab.pdfgen import canvas as pdfcanvas
    puffer = io.BytesIO()
    c = pdfcanvas.Canvas(puffer, pagesize=(breite, hoehe))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, hoehe - 40, text)
    c.showPage()
    c.save()
    return puffer.getvalue()


def test_eigener_vordruck_liegt_hinter_dem_inhalt(client, admin_headers, vordruck_aktiv):
    """Der Kern der Sache: das eigene Blatt bleibt, das Programm druckt nur die
    veraenderlichen Angaben darauf."""
    _st, _fz, tasche = _lagerort(client, admin_headers)
    r = client.post(f"/api/v1/doc-templates/{vordruck_aktiv['id']}/background?lage=hoch",
                    files={"file": ("vordruck.pdf", _briefpapier(), "application/pdf")},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["background_kind"] == "pdf"

    text = " ".join(_text_der_seiten(client.get(
        f"/api/v1/inhaltslisten/{tasche['id']}/pdf?format=a4", headers=admin_headers).content))
    assert "MEIN VORDRUCK" in text          # das eigene Blatt
    assert "Seitentasche links" in text     # und die Angaben des Programms darauf


def test_querformat_bekommt_ein_eigenes_blatt(client, admin_headers, vordruck_aktiv):
    """Ein hochkanter Vordruck hinter einer Querformat-Liste waere breitgezogen.
    Also: eigene Datei je Lage - und ohne sie lieber gar keinen Hintergrund."""
    _st, _fz, tasche = _lagerort(client, admin_headers)
    client.post(f"/api/v1/doc-templates/{vordruck_aktiv['id']}/background?lage=hoch",
                files={"file": ("hoch.pdf", _briefpapier(text="HOCHKANT"), "application/pdf")},
                headers=admin_headers)
    quer = " ".join(_text_der_seiten(client.get(
        f"/api/v1/inhaltslisten/{tasche['id']}/pdf?format=a4quer", headers=admin_headers).content))
    assert "HOCHKANT" not in quer

    client.post(f"/api/v1/doc-templates/{vordruck_aktiv['id']}/background?lage=quer",
                files={"file": ("quer.pdf", _briefpapier(842, 595, "QUERFORMAT"), "application/pdf")},
                headers=admin_headers)
    quer = " ".join(_text_der_seiten(client.get(
        f"/api/v1/inhaltslisten/{tasche['id']}/pdf?format=a4quer", headers=admin_headers).content))
    hoch = " ".join(_text_der_seiten(client.get(
        f"/api/v1/inhaltslisten/{tasche['id']}/pdf?format=a4", headers=admin_headers).content))
    assert "QUERFORMAT" in quer and "HOCHKANT" not in quer
    assert "HOCHKANT" in hoch and "QUERFORMAT" not in hoch


def test_vordruck_wird_auf_die_seitengroesse_gebracht(client, admin_headers, vordruck_aktiv):
    """A4-Vordruck hinter einer A5-Liste: das Blatt muss mitschrumpfen, sonst
    rutscht die Liste in eine Ecke."""
    _st, _fz, tasche = _lagerort(client, admin_headers)
    client.post(f"/api/v1/doc-templates/{vordruck_aktiv['id']}/background?lage=hoch",
                files={"file": ("hoch.pdf", _briefpapier(), "application/pdf")},
                headers=admin_headers)
    roh = client.get(f"/api/v1/inhaltslisten/{tasche['id']}/pdf?format=a5",
                     headers=admin_headers).content
    seite = PdfReader(io.BytesIO(roh)).pages[0]
    assert float(seite.mediabox.width) < 500          # wirklich A5
    assert "MEIN VORDRUCK" in _text_der_seiten(roh)[0]


def test_hintergrund_laesst_sich_je_lage_wieder_entfernen(client, admin_headers, vordruck_aktiv):
    client.post(f"/api/v1/doc-templates/{vordruck_aktiv['id']}/background?lage=quer",
                files={"file": ("quer.pdf", _briefpapier(842, 595), "application/pdf")},
                headers=admin_headers)
    r = client.delete(f"/api/v1/doc-templates/{vordruck_aktiv['id']}/background?lage=quer",
                      headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["background_landscape_kind"] == ""
