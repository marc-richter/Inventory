"""Die Migration gegen eine Datenbank im Zustand VOR 1.102.0/1.103.0.

Das ist der riskanteste Teil des Umbaus: eine Spalte wird umbenannt, mehrere
Tabellen kommen dazu, und bestehende Abteilungs-Zuordnungen werden uebernommen.
Geht das schief, steht der Verein vor einer kaputten Datenbank - und merkt es
erst, wenn etwas fehlt.

Vorgehen: die Testdatenbank wird aus dem AKTUELLEN Schema erzeugt, mit Bestand
gefuellt und danach gezielt auf den alten Stand zurueckgebaut. So stimmt alles
Uebrige garantiert; nur die geaenderten Stellen sind alt, und genau die soll die
Migration richten.
"""

import os
import sqlite3
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models

# Spalten und Tabellen, die es vor 1.102.0 noch nicht gab.
NEUE_SPALTEN = {
    "articles": ["key_alias", "key_group", "is_container", "key_ring_id", "warden_id",
                 "warden_group_id"],
    "article_maintenance": ["interval_months", "interval_km"],
    "storage_nodes": ["label_width_mm", "label_height_mm", "watermark"],
    "categories": ["system_key", "active", "has_locks"],
    "custom_field_defs": ["system_key"],
    "users": ["telegram_consent_at"],
    # 1.103.0: Pruefarten unterscheiden Funktion und Verfall (Farblegende),
    # Vorlagen und Lagerorte koennen ein Wasserzeichen tragen.
    "maintenance_types": ["kind"],
    "doc_templates": ["watermark", "background_landscape_filename", "background_landscape_kind"],
}
NEUE_TABELLEN = ["person_organizations", "vehicle_tires", "change_events",
                 "bereitstellungen", "bereitstellung_positionen",
                 # 1.112.0: Schluesselbuende
                 "key_rings",
                 # 1.113.0: Dokumente an Artikeln
                 "documents", "document_links"]


def _spalte_entfernen(cur, tabelle, spalte):
    """Entfernt eine Spalte, an der ein Fremdschluessel haengt.

    SQLite verweigert ALTER TABLE ... DROP COLUMN, sobald die Spalte in einer
    Fremdschluessel-Klausel vorkommt ("unknown column in foreign key
    definition"). Fuer den Rueckbau auf einen alten Stand wird die Tabelle
    deshalb ohne diese Spalte neu aufgebaut. Der Primaerschluessel bleibt dabei
    erhalten - ohne ihn bekaemen neue Zeilen keine Nummer, und der Rueckbau
    bildete gar nicht mehr ab, was auf einem echten Server steht.
    """
    cur.execute(f"PRAGMA table_info({tabelle})")
    behalten = [r for r in cur.fetchall() if r[1] != spalte]
    felder = []
    for _cid, name, typ, notnull, default, pk in behalten:
        teil = f'"{name}" {typ or "BLOB"}'
        if pk:
            teil += " NOT NULL PRIMARY KEY"
        elif notnull:
            teil += " NOT NULL"
        if default is not None:
            teil += f" DEFAULT {default}"
        felder.append(teil)
    namen = ", ".join(f'"{r[1]}"' for r in behalten)
    cur.execute(f"CREATE TABLE {tabelle}__rueckbau ({', '.join(felder)})")
    cur.execute(f"INSERT INTO {tabelle}__rueckbau ({namen}) SELECT {namen} FROM {tabelle}")
    cur.execute(f"DROP TABLE {tabelle}")
    cur.execute(f"ALTER TABLE {tabelle}__rueckbau RENAME TO {tabelle}")


@pytest.fixture
def alte_datenbank(tmp_path, monkeypatch):
    """Eine gefuellte Datenbank im Zustand vor 1.102.0."""
    pfad = tmp_path / "alt.db"
    motor = create_engine(f"sqlite:///{pfad}")
    models.Base.metadata.create_all(bind=motor)

    Sitzung = sessionmaker(bind=motor)
    db = Sitzung()
    db.add_all([
        models.Category(id=1, name="Kleidung", key_system=False),
        models.Category(id=2, name="Schlüssel", key_system=True),
        models.Category(id=3, name="Eigene Klasse des Vereins"),
        models.Category(id=4, name="Fahrzeuge"),
        models.Organization(id=1, name="Bereitschaft"),
        models.Organization(id=2, name="Jugendrotkreuz"),
    ])
    db.commit()
    db.add_all([
        models.ArticleType(id=1, category_id=1, name="Einsatzjacke"),
        models.Person(id=1, first_name="Anna", last_name="Alt", organization_id=1),
        models.Person(id=2, first_name="Bert", last_name="Bestand", organization_id=2),
        models.Person(id=3, first_name="Cara", last_name="Ohne"),
        models.StorageNode(id=1, level="standort", name="Gerätehaus"),
        models.StatusDef(key="zu_waschen", label="Zu waschen", sort_order=50,
                         is_builtin=False, active=True, category_ids=[],
                         issue_policy="confirm"),
    ])
    db.commit()
    db.add(models.Article(id=1, artikelnummer="2024-0001", category_id=1, type_id=1,
                          storage_node_id=1, is_vehicle=True))
    db.commit()
    db.add_all([
        models.StorageNode(id=2, parent_id=1, level="fahrzeug", name="MTW", node_article_id=1),
        models.IssueRecord(id=1, article_id=1, person_id=1),
    ])
    db.commit()
    db.close()
    motor.dispose()

    # --- auf den alten Stand zurueckbauen --------------------------------
    conn = sqlite3.connect(str(pfad))
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys=OFF")
    cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")
    for (index_name,) in cur.fetchall():
        cur.execute(f"DROP INDEX IF EXISTS {index_name}")
    cur.execute("ALTER TABLE storage_nodes RENAME COLUMN node_article_id TO vehicle_article_id")
    for tabelle in NEUE_TABELLEN:
        cur.execute(f"DROP TABLE IF EXISTS {tabelle}")
    # container_issue_id zeigt per Fremdschluessel auf dieselbe Tabelle - SQLite
    # laesst die Spalte nicht einzeln fallen, also Tabelle neu aufbauen.
    # Mit Primaerschluessel neu aufbauen: "CREATE TABLE AS SELECT" erzeugt eine
    # Tabelle OHNE Schluessel. Neue Zeilen bekaemen dann keine Nummer, und der
    # Rueckbau bildete gar nicht mehr ab, was auf einem echten Server steht -
    # jede Zusicherung darauf waere wertlos.
    cur.executescript("""
    CREATE TABLE ir_alt (
      id INTEGER NOT NULL PRIMARY KEY,
      article_id INTEGER NOT NULL,
      person_id INTEGER,
      recipient_name_freetext VARCHAR(128),
      issue_date DATETIME,
      expected_return_date DATETIME,
      return_date DATETIME,
      condition_at_return TEXT,
      notes TEXT,
      deposit_amount VARCHAR(32),
      deposit_returned BOOLEAN,
      issued_by_user_id INTEGER,
      returned_by_user_id INTEGER
    );
    INSERT INTO ir_alt SELECT id, article_id, person_id, recipient_name_freetext,
      issue_date, expected_return_date, return_date, condition_at_return, notes,
      deposit_amount, deposit_returned, issued_by_user_id, returned_by_user_id
      FROM issue_records;
    DROP TABLE issue_records;
    ALTER TABLE ir_alt RENAME TO issue_records;
    """)
    for tabelle, spalten in NEUE_SPALTEN.items():
        for spalte in spalten:
            try:
                cur.execute(f"ALTER TABLE {tabelle} DROP COLUMN {spalte}")
            except sqlite3.OperationalError:
                # An der Spalte haengt ein Fremdschluessel - dann muss die
                # Tabelle neu aufgebaut werden (siehe _spalte_entfernen).
                _spalte_entfernen(cur, tabelle, spalte)
    conn.commit()
    conn.close()
    return pfad


def _start_nachspielen(pfad):
    """migrate -> create_all -> seed, wie beim Start des Servers."""
    import app.config as config
    import app.migrate as migrate

    alt = config.DB_PATH
    migrate.DB_PATH = pfad
    try:
        migrate.run_migrations()
    finally:
        migrate.DB_PATH = alt

    motor = create_engine(f"sqlite:///{pfad}")
    models.Base.metadata.create_all(bind=motor)
    Sitzung = sessionmaker(bind=motor)
    db = Sitzung()
    from app.seed import seed
    seed(db)
    return motor, db


def _spalten(pfad, tabelle):
    conn = sqlite3.connect(str(pfad))
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({tabelle})")}
    finally:
        conn.close()


def test_bestand_bleibt_unversehrt(alte_datenbank):
    motor, db = _start_nachspielen(alte_datenbank)
    try:
        assert db.query(models.Article).count() == 1
        assert db.get(models.Article, 1).artikelnummer == "2024-0001"
        # Die drei angelegten Personen sind noch da. (Es koennen mehr sein: legt
        # der Start einen Administrator an, bekommt der eine eigene Person.)
        namen = {f"{p.first_name} {p.last_name}" for p in db.query(models.Person).all()}
        assert {"Anna Alt", "Bert Bestand", "Cara Ohne"} <= namen
        assert db.query(models.IssueRecord).count() == 1
    finally:
        db.close(); motor.dispose()


def test_eigene_kategorie_bleibt_und_wird_keine_systemklasse(alte_datenbank):
    motor, db = _start_nachspielen(alte_datenbank)
    try:
        eigene = db.query(models.Category).filter(
            models.Category.name == "Eigene Klasse des Vereins").first()
        assert eigene is not None
        assert eigene.system_key is None      # bleibt loeschbar
        assert eigene.active is True
    finally:
        db.close(); motor.dispose()


def test_kleidung_wird_uebernommen_nicht_verdoppelt(alte_datenbank):
    motor, db = _start_nachspielen(alte_datenbank)
    try:
        treffer = db.query(models.Category).filter(models.Category.name == "Kleidung").all()
        assert len(treffer) == 1
        assert treffer[0].id == 1                      # die BESTEHENDE
        assert treffer[0].system_key == "kleidung"
        assert db.get(models.ArticleType, 1).category_id == 1
    finally:
        db.close(); motor.dispose()


def test_lagerort_spalte_umbenannt_werte_erhalten(alte_datenbank):
    motor, db = _start_nachspielen(alte_datenbank)
    try:
        assert db.get(models.StorageNode, 2).node_article_id == 1
        assert db.get(models.Article, 1).vehicle_node_id == 2
        spalten = _spalten(alte_datenbank, "storage_nodes")
        assert "node_article_id" in spalten
        assert "vehicle_article_id" not in spalten
    finally:
        db.close(); motor.dispose()


def test_schloesser_kennzeichen_kommt_einmalig_an_die_richtigen_klassen(alte_datenbank):
    """Bestandsklassen bekommen das Kennzeichen "Schloesser" beim Update.

    Auf einer alten Datenbank hat die Klasse "Fahrzeuge" noch gar keine Kennung
    (system_key vergibt erst seed()). Ginge die Migration nur ueber die Kennung,
    stuende die Funktion beim Verein nach dem Update nicht zur Verfuegung und
    niemand wuesste, warum.
    """
    motor, db = _start_nachspielen(alte_datenbank)
    try:
        fahrzeuge = db.get(models.Category, 4)
        assert fahrzeuge.name == "Fahrzeuge"
        assert fahrzeuge.has_locks is True
        assert fahrzeuge.system_key == "fahrzeuge"        # von seed() nachgezogen
        # Und nur dort - nicht bei Kleidung, Schluesseln oder der eigenen Klasse.
        assert db.get(models.Category, 1).has_locks is False
        assert db.get(models.Category, 2).has_locks is False
        assert db.get(models.Category, 3).has_locks is False
    finally:
        db.close(); motor.dispose()


def test_schluesselbuende_lassen_sich_nach_dem_update_anlegen(alte_datenbank):
    """Die neue Tabelle ist da, und ein Bestandsartikel darf daran haengen."""
    motor, db = _start_nachspielen(alte_datenbank)
    try:
        bund = models.KeyRing(name="Gerätehaus", code="SB-0001")
        db.add(bund)
        db.commit()
        artikel = db.get(models.Article, 1)
        artikel.key_ring_id = bund.id
        db.commit()
        db.refresh(bund)
        assert [a.id for a in bund.keys] == [1]
        assert db.get(models.Article, 1).key_ring_name == "Gerätehaus"
    finally:
        db.close(); motor.dispose()


def test_dokumente_lassen_sich_nach_dem_update_zuordnen(alte_datenbank):
    """Die neuen Tabellen sind da, und ein Bestandsartikel darf ein Dokument tragen."""
    motor, db = _start_nachspielen(alte_datenbank)
    try:
        dok = models.Document(title="Pflege Einsatzjacke", art="pflege",
                              filename="pflege_abc12345.pdf", size_bytes=1234)
        db.add(dok)
        db.commit()
        db.add(models.DocumentLink(document_id=dok.id, category_id=1))
        db.add(models.DocumentLink(document_id=dok.id, article_id=1))
        db.commit()
        db.refresh(dok)
        assert len(dok.links) == 2
        # Mit dem Dokument verschwinden auch seine Zuordnungen.
        db.delete(dok)
        db.commit()
        assert db.query(models.DocumentLink).count() == 0
    finally:
        db.close(); motor.dispose()


def test_geraetewart_laesst_sich_nach_dem_update_setzen(alte_datenbank):
    """Bestandsartikel bekommen die Spalte fuer den Zustaendigen nachtraeglich."""
    motor, db = _start_nachspielen(alte_datenbank)
    try:
        benutzer = models.User(username="wart", roles=["verwalter"], active=True,
                               password_hash="x")
        db.add(benutzer)
        db.commit()
        artikel = db.get(models.Article, 1)
        artikel.warden_id = benutzer.id
        db.commit()
        assert db.get(models.Article, 1).warden_id == benutzer.id
        assert db.get(models.Article, 1).warden_name == "wart"
    finally:
        db.close(); motor.dispose()


def test_belegspalte_kommt_bei_zwischenstaenden_dazu(tmp_path):
    """Wer von 1.113/1.114 kommt, hat document_links schon - aber ohne die
    Spalte fuer den Vorgang. Die Tabelle steht deshalb nicht im Rueckbau oben;
    dieser Fall wird hier eigens nachgestellt."""
    import pathlib
    import app.migrate as migrate
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    pfad = tmp_path / "zwischenstand.db"
    motor = create_engine(f"sqlite:///{pfad}")
    models.Base.metadata.create_all(bind=motor)
    db = sessionmaker(bind=motor)()
    db.add(models.Document(id=1, title="TÜV-Bericht", filename="t.pdf"))
    db.commit()
    db.add(models.DocumentLink(id=1, document_id=1))
    db.commit()
    db.close()
    motor.dispose()

    conn = sqlite3.connect(str(pfad))
    cur = conn.cursor()
    # An der Spalte haengt ein Fremdschluessel - SQLite verweigert DROP COLUMN,
    # also die Tabelle ohne sie neu aufbauen (siehe _spalte_entfernen).
    _spalte_entfernen(cur, "document_links", "log_entry_id")
    conn.commit()
    conn.close()
    assert "log_entry_id" not in _spalten(pfad, "document_links")

    alt = migrate.DB_PATH
    migrate.DB_PATH = pathlib.Path(pfad)
    try:
        migrate.run_migrations()
    finally:
        migrate.DB_PATH = alt
    assert "log_entry_id" in _spalten(pfad, "document_links")


def test_abteilungen_werden_uebernommen(alte_datenbank):
    motor, db = _start_nachspielen(alte_datenbank)
    try:
        assert db.query(models.PersonOrganization).count() == 2
        assert db.get(models.Person, 1).organization_ids == [1]
        assert db.get(models.Person, 2).organization_ids == [2]
        assert db.get(models.Person, 3).organization_ids == []
    finally:
        db.close(); motor.dispose()


def test_kleidungsstatus_wird_auf_kleidung_eingeschraenkt(alte_datenbank):
    motor, db = _start_nachspielen(alte_datenbank)
    try:
        st = db.query(models.StatusDef).filter(models.StatusDef.key == "zu_waschen").first()
        assert st.category_ids == [1]
    finally:
        db.close(); motor.dispose()


def test_neue_tabellen_und_spalten_sind_da(alte_datenbank):
    motor, db = _start_nachspielen(alte_datenbank)
    try:
        conn = sqlite3.connect(str(alte_datenbank))
        vorhandene = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        for tabelle in NEUE_TABELLEN:
            assert tabelle in vorhandene, tabelle
        for tabelle, spalten in NEUE_SPALTEN.items():
            assert set(spalten) <= _spalten(alte_datenbank, tabelle), tabelle
    finally:
        db.close(); motor.dispose()


def test_zweiter_start_aendert_nichts(alte_datenbank):
    """Der Abgleich laeuft bei JEDEM Start - er darf nichts doppelt anlegen."""
    motor, db = _start_nachspielen(alte_datenbank)
    try:
        from app.seed import seed
        zaehle = lambda: (db.query(models.Category).count(),
                          db.query(models.CustomFieldDef).count(),
                          db.query(models.StatusDef).count(),
                          db.query(models.PersonOrganization).count(),
                          db.query(models.MaintenanceType).count())
        vorher = zaehle()
        seed(db)
        db.expire_all()
        assert zaehle() == vorher
    finally:
        db.close(); motor.dispose()


def test_entfernte_abteilungszuordnung_kommt_nicht_zurueck(alte_datenbank):
    """Nimmt der Administrator eine Zuordnung heraus, darf sie der naechste Start
    nicht wieder anlegen."""
    motor, db = _start_nachspielen(alte_datenbank)
    try:
        from app.seed import backfill_person_organizations
        db.query(models.PersonOrganization).filter(
            models.PersonOrganization.person_id == 2).delete()
        db.commit()
        assert backfill_person_organizations(db) == 0
        assert db.query(models.PersonOrganization).count() == 1
    finally:
        db.close(); motor.dispose()


def test_pruefarten_bekommen_eine_art(alte_datenbank):
    """Die Farblegende der Inhaltslisten braucht die Unterscheidung. Eine alte
    Datenbank kennt sie nicht - nach der Migration muss jede Art eine haben, und
    bestehende Arten duerfen nicht stillschweigend auf Verfall landen."""
    assert "kind" not in _spalten(alte_datenbank, "maintenance_types")
    motor, db = _start_nachspielen(alte_datenbank)
    try:
        assert "kind" in _spalten(alte_datenbank, "maintenance_types")
        arten = db.query(models.MaintenanceType).all()
        assert arten
        assert all((a.kind or "") in ("funktion", "verfall") for a in arten)
        assert any(a.kind == "verfall" for a in arten)
    finally:
        db.close()
        motor.dispose()


def test_wasserzeichen_spalten_kommen_dazu(alte_datenbank):
    """Ohne die Spalte laeuft beim ersten Ausdruck alles auf einen Fehler."""
    for tabelle in ("doc_templates", "storage_nodes"):
        assert "watermark" not in _spalten(alte_datenbank, tabelle)
    motor, db = _start_nachspielen(alte_datenbank)
    try:
        for tabelle in ("doc_templates", "storage_nodes"):
            assert "watermark" in _spalten(alte_datenbank, tabelle)
        # Bestandsdaten haben keins - und drucken damit wie bisher.
        knoten = db.query(models.StorageNode).first()
        assert not (knoten.watermark or {})
    finally:
        db.close()
        motor.dispose()


def test_nach_dem_update_laesst_sich_weiter_ausgeben(alte_datenbank):
    """Der Rueckbau muss eine ECHTE Datenbank ergeben, nicht nur eine mit den
    richtigen Spalten: neue Ausgaben brauchen einen Primaerschluessel. Ohne ihn
    faellt es erst im Betrieb auf - und jede andere Zusicherung dieses Moduls
    stuende auf einer Datenbank, die es so nie gibt."""
    motor, db = _start_nachspielen(alte_datenbank)
    try:
        artikel = db.query(models.Article).first()
        person = db.query(models.Person).first()
        rec = models.IssueRecord(article_id=artikel.id, person_id=person.id)
        db.add(rec)
        db.commit()
        assert rec.id, "neuer Ausgabe-Datensatz bekam keine Nummer"
        db.refresh(rec)
        assert rec.article_id == artikel.id
    finally:
        db.close()
        motor.dispose()
