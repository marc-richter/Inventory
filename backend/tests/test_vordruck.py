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
