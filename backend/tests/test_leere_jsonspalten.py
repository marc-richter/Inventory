"""Nachtraeglich hinzugefuegte JSON-Spalten duerfen keinen Serverfehler ausloesen.

Der Fall, der es in den Betrieb geschafft hat: ``ALTER TABLE ... ADD COLUMN``
setzt bei allen bereits vorhandenen Zeilen NULL - SQLite kennt keinen
nachtraeglichen Standardwert. Das Ausgabeschema erwartet aber eine Liste oder
ein Objekt. Ergebnis war ein 500 auf ``/storage-nodes``; damit liess sich der
Lagerort-Baum nicht laden, und weil die Artikelmaske ihn braucht, kamen dort
auch neu angelegte Lagerorte nicht an.

Getestet wird beides: dass ein NULL nicht mehr zum Serverfehler fuehrt, und dass
die Migration vorhandene NULL-Werte aufraeumt.
"""

import sqlite3

import pytest
from sqlalchemy import text

from app import models


def _auf_null_setzen(db_session, tabelle, spalte, bedingung="1=1"):
    """Spalte roh auf NULL setzen - so, wie sie nach einer Migration dasteht."""
    db_session.execute(text(f"UPDATE {tabelle} SET {spalte} = NULL WHERE {bedingung}"))
    db_session.flush()


def test_lagerortbaum_laedt_auch_mit_leerem_wasserzeichen(client, admin_headers, db_session):
    r = client.post("/api/v1/storage-nodes", json={"name": "Gerätehaus", "level": "standort"},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    _auf_null_setzen(db_session, "storage_nodes", "watermark")

    r = client.get("/api/v1/storage-nodes", headers=admin_headers)
    assert r.status_code == 200, r.text[:400]
    assert r.json()[0]["watermark"] == {}


def test_lagerort_laesst_sich_danach_anlegen_und_zuweisen(client, admin_headers, db_session,
                                                          kleidung_type):
    """Der eigentliche Schaden: ohne Baum kam in der Artikelmaske kein Lagerort an."""
    cat_id, type_id = kleidung_type
    standort = client.post("/api/v1/storage-nodes", json={"name": "Gerätehaus", "level": "standort"},
                           headers=admin_headers).json()
    _auf_null_setzen(db_session, "storage_nodes", "watermark")

    r = client.post("/api/v1/storage-nodes", json={"name": "Lager", "parent_id": standort["id"]},
                    headers=admin_headers)
    assert r.status_code == 200, r.text[:400]
    neu = r.json()["id"]

    art = client.post("/api/v1/articles",
                      json={"category_id": cat_id, "type_id": type_id, "storage_node_id": neu},
                      headers=admin_headers)
    assert art.status_code == 200, art.text[:400]
    assert art.json()["storage_node_id"] == neu

    geaendert = client.put(f"/api/v1/articles/{art.json()['id']}",
                           json={"storage_node_id": standort["id"]}, headers=admin_headers)
    assert geaendert.status_code == 200, geaendert.text[:400]
    assert geaendert.json()["storage_node_id"] == standort["id"]


@pytest.mark.parametrize("tabelle,spalte,pfad,leer", [
    ("storage_nodes", "watermark", "/api/v1/storage-nodes", {}),
    ("doc_templates", "watermark", "/api/v1/doc-templates", {}),
    ("doc_templates", "elements", "/api/v1/doc-templates", []),
    ("documents", "tags", "/api/v1/dokumente", []),
    ("users", "revoked_capabilities", "/api/v1/users", []),
    ("persons", "sizes", "/api/v1/persons", {}),
    ("custom_field_defs", "options", "/api/v1/custom-fields", []),
    ("status_defs", "category_ids", "/api/v1/statuses", []),
])
def test_leere_jsonspalte_liefert_keinen_serverfehler(client, admin_headers, db_session,
                                                      tabelle, spalte, pfad, leer):
    """Jede dieser Spalten kam per Migration dazu und ist bei Altzeilen NULL."""
    # Mindestens eine Zeile anlegen, damit es etwas zu serialisieren gibt.
    if tabelle == "storage_nodes":
        client.post("/api/v1/storage-nodes", json={"name": "Ort", "level": "standort"},
                    headers=admin_headers)
    elif tabelle == "doc_templates":
        # Eine globale Vorlage bringt das Programm schon mit; reicht als Zeile.
        if not client.get("/api/v1/doc-templates", headers=admin_headers).json():
            client.post("/api/v1/doc-templates", json={"name": "Vordruck"},
                        headers=admin_headers)
    elif tabelle == "documents":
        import io
        from reportlab.pdfgen import canvas
        puffer = io.BytesIO()
        c = canvas.Canvas(puffer)
        c.drawString(80, 800, "x")
        c.save()
        client.post("/api/v1/dokumente",
                    files={"file": ("a.pdf", io.BytesIO(puffer.getvalue()), "application/pdf")},
                    data={"title": "A"}, headers=admin_headers)
    elif tabelle == "persons":
        client.post("/api/v1/persons", json={"first_name": "Anna", "last_name": "Alt"},
                    headers=admin_headers)
    elif tabelle == "custom_field_defs":
        kat = db_session.query(models.Category).first()
        client.post("/api/v1/custom-fields",
                    json={"label": "Farbe", "field_type": "text", "category_id": kat.id},
                    headers=admin_headers)

    _auf_null_setzen(db_session, tabelle, spalte)
    r = client.get(pfad, headers=admin_headers)
    assert r.status_code == 200, f"{pfad} -> {r.status_code}: {r.text[:300]}"
    daten = r.json()
    zeilen = daten if isinstance(daten, list) else daten.get("items", [])
    for zeile in zeilen:
        if spalte in zeile:
            assert zeile[spalte] == leer


def test_migration_raeumt_vorhandene_nullwerte_weg(tmp_path, monkeypatch):
    """Die Migration fasst auch Spalten an, die laengst existieren - genau die
    Datenbanken sind betroffen, nicht die frisch angelegten."""
    import pathlib
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.migrate as migrate

    pfad = tmp_path / "alt.db"
    motor = create_engine(f"sqlite:///{pfad}")
    models.Base.metadata.create_all(bind=motor)
    db = sessionmaker(bind=motor)()
    db.add(models.StorageNode(id=1, level="standort", name="Gerätehaus"))
    db.commit()
    db.close()
    motor.dispose()

    conn = sqlite3.connect(str(pfad))
    conn.execute("UPDATE storage_nodes SET watermark = NULL")
    conn.commit()
    conn.close()

    alt = migrate.DB_PATH
    migrate.DB_PATH = pathlib.Path(pfad)
    try:
        migrate.run_migrations()
    finally:
        migrate.DB_PATH = alt

    conn = sqlite3.connect(str(pfad))
    wert = conn.execute("SELECT watermark FROM storage_nodes WHERE id = 1").fetchone()[0]
    conn.close()
    assert wert == "{}"
