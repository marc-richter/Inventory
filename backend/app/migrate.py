"""Leichte Inline-Migration fuer SQLite, da kein vollwertiges Migrationswerkzeug
(z.B. Alembic) im Einsatz ist. Wird beim Start ausgefuehrt, BEVOR
Base.metadata.create_all() laeuft. Neue Tabellen legt create_all() ohnehin an;
hier werden nur Spalten ergaenzt, die auf bereits existierenden Tabellen fehlen.
"""
import json
import sqlite3
from .config import DB_PATH


def _column_exists(cur, table, column) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def _table_exists(cur, table) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def run_migrations():
    if not DB_PATH.exists():
        return  # frische Installation, create_all() erzeugt das aktuelle Schema direkt

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    try:
        # Fehlerhafte Volltext-Trigger entfernen.
        #
        # Frueher verwiesen die Suchindex-Trigger auf new.location_path. Das ist
        # keine Spalte der Tabelle articles, sondern eine in Python berechnete
        # Eigenschaft. SQLite prueft Trigger-Rumpfe erst beim Ausloesen - der
        # Trigger liess sich also anlegen und scheiterte danach bei JEDEM
        # Anlegen oder Aendern eines Artikels mit "no such column:
        # new.location_path". In der Oberflaeche kam das als "Datenbank
        # voruebergehend nicht verfuegbar" an. Hier werden die alten Trigger und
        # die zugehoerige Indextabelle entfernt; beides wird beim Start sauber
        # neu aufgebaut.
        try:
            cur.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger' "
                        "AND name IN ('articles_ai', 'articles_au', 'articles_ad')")
            triggers = cur.fetchall()
            if any(sql and "new.location_path" in sql for _name, sql in triggers):
                for trg in ("articles_ai", "articles_au", "articles_ad"):
                    cur.execute(f"DROP TRIGGER IF EXISTS {trg}")
                cur.execute("DROP TABLE IF EXISTS articles_fts")
                conn.commit()
        except sqlite3.Error:
            # Kein Grund, die restliche Migration scheitern zu lassen.
            conn.rollback()

        # Systemkategorien: Kennung und Ausblend-Kennzeichen nachziehen.
        if _table_exists(cur, "categories"):
            if not _column_exists(cur, "categories", "system_key"):
                cur.execute("ALTER TABLE categories ADD COLUMN system_key TEXT")
            if not _column_exists(cur, "categories", "active"):
                cur.execute("ALTER TABLE categories ADD COLUMN active BOOLEAN DEFAULT 1")
                cur.execute("UPDATE categories SET active = 1 WHERE active IS NULL")
        if _table_exists(cur, "custom_field_defs"):
            if not _column_exists(cur, "custom_field_defs", "system_key"):
                cur.execute("ALTER TABLE custom_field_defs ADD COLUMN system_key TEXT")

        if _table_exists(cur, "users"):
            if _column_exists(cur, "users", "role") and not _column_exists(cur, "users", "roles"):
                cur.execute("ALTER TABLE users ADD COLUMN roles TEXT")
                cur.execute("SELECT id, role FROM users")
                for user_id, role in cur.fetchall():
                    cur.execute(
                        "UPDATE users SET roles = ? WHERE id = ?",
                        (json.dumps([role] if role else []), user_id),
                    )
            elif not _column_exists(cur, "users", "roles"):
                cur.execute("ALTER TABLE users ADD COLUMN roles TEXT")

            if not _column_exists(cur, "users", "person_id"):
                cur.execute("ALTER TABLE users ADD COLUMN person_id INTEGER")

            if not _column_exists(cur, "users", "last_seen"):
                cur.execute("ALTER TABLE users ADD COLUMN last_seen TEXT")
            if not _column_exists(cur, "users", "telegram_chat_id"):
                cur.execute("ALTER TABLE users ADD COLUMN telegram_chat_id TEXT")
            if not _column_exists(cur, "users", "telegram_link_code"):
                cur.execute("ALTER TABLE users ADD COLUMN telegram_link_code TEXT")
            if not _column_exists(cur, "users", "reminder_days_before"):
                cur.execute("ALTER TABLE users ADD COLUMN reminder_days_before INTEGER")
            if not _column_exists(cur, "users", "revoked_capabilities"):
                cur.execute("ALTER TABLE users ADD COLUMN revoked_capabilities TEXT")

        if _table_exists(cur, "inventory_campaigns"):
            if not _column_exists(cur, "inventory_campaigns", "reminder_days_before"):
                cur.execute("ALTER TABLE inventory_campaigns ADD COLUMN reminder_days_before INTEGER DEFAULT 3")

        if _table_exists(cur, "inventory_schedules"):
            if not _column_exists(cur, "inventory_schedules", "reminder_days_before"):
                cur.execute("ALTER TABLE inventory_schedules ADD COLUMN reminder_days_before INTEGER DEFAULT 3")
            if not _column_exists(cur, "inventory_schedules", "ics_sent"):
                cur.execute("ALTER TABLE inventory_schedules ADD COLUMN ics_sent BOOLEAN DEFAULT 0")
            if not _column_exists(cur, "inventory_schedules", "weekday"):
                cur.execute("ALTER TABLE inventory_schedules ADD COLUMN weekday INTEGER")
            if not _column_exists(cur, "inventory_schedules", "week_of_month"):
                cur.execute("ALTER TABLE inventory_schedules ADD COLUMN week_of_month INTEGER")

        # Lagerort-Knoten: das Feld hiess vehicle_article_id, solange nur Fahrzeuge
        # zugleich Artikel und Lagerort sein konnten. Jetzt gilt das auch fuer
        # Behaelter (Kisten, Rucksaecke), deshalb der neutrale Name.
        if _table_exists(cur, "storage_nodes"):
            if (_column_exists(cur, "storage_nodes", "vehicle_article_id")
                    and not _column_exists(cur, "storage_nodes", "node_article_id")):
                try:
                    cur.execute("ALTER TABLE storage_nodes "
                                "RENAME COLUMN vehicle_article_id TO node_article_id")
                except sqlite3.Error:
                    # Aeltere SQLite-Fassungen koennen keine Spalte umbenennen:
                    # dann neue Spalte anlegen und Werte uebernehmen.
                    cur.execute("ALTER TABLE storage_nodes ADD COLUMN node_article_id INTEGER")
                    cur.execute("UPDATE storage_nodes SET node_article_id = vehicle_article_id")
            elif not _column_exists(cur, "storage_nodes", "node_article_id"):
                cur.execute("ALTER TABLE storage_nodes ADD COLUMN node_article_id INTEGER")

        if _table_exists(cur, "issue_records"):
            # Behaelter-Ausgabe: Inhalt haengt am Eintrag der Kiste.
            for col, ddl in (("container_issue_id", "INTEGER"),
                             ("container_item_count", "INTEGER DEFAULT 0"),
                             ("container_complete", "BOOLEAN DEFAULT 1")):
                if not _column_exists(cur, "issue_records", col):
                    cur.execute(f"ALTER TABLE issue_records ADD COLUMN {col} {ddl}")

        if _table_exists(cur, "articles"):
            if not _column_exists(cur, "articles", "is_container"):
                cur.execute("ALTER TABLE articles ADD COLUMN is_container BOOLEAN DEFAULT 0")
                cur.execute("UPDATE articles SET is_container = 0 WHERE is_container IS NULL")

        if _table_exists(cur, "articles"):
            if not _column_exists(cur, "articles", "storage_location_id"):
                cur.execute("ALTER TABLE articles ADD COLUMN storage_location_id INTEGER")
            if not _column_exists(cur, "articles", "repair_expected_return"):
                cur.execute("ALTER TABLE articles ADD COLUMN repair_expected_return TEXT")
            if not _column_exists(cur, "articles", "repair_reason"):
                cur.execute("ALTER TABLE articles ADD COLUMN repair_reason TEXT")
            if not _column_exists(cur, "articles", "model"):
                cur.execute("ALTER TABLE articles ADD COLUMN model TEXT")
            if not _column_exists(cur, "articles", "properties"):
                cur.execute("ALTER TABLE articles ADD COLUMN properties TEXT")
            if not _column_exists(cur, "articles", "current_location"):
                cur.execute("ALTER TABLE articles ADD COLUMN current_location TEXT")
            if not _column_exists(cur, "articles", "retire_reason"):
                cur.execute("ALTER TABLE articles ADD COLUMN retire_reason TEXT")
            if not _column_exists(cur, "articles", "provisional"):
                cur.execute("ALTER TABLE articles ADD COLUMN provisional BOOLEAN DEFAULT 0")
            if not _column_exists(cur, "articles", "provisional_by_id"):
                cur.execute("ALTER TABLE articles ADD COLUMN provisional_by_id INTEGER")
            if not _column_exists(cur, "articles", "review_assignee_id"):
                cur.execute("ALTER TABLE articles ADD COLUMN review_assignee_id INTEGER")
            for col in ("etage", "raum", "schrank", "fach"):
                if not _column_exists(cur, "articles", col):
                    cur.execute(f"ALTER TABLE articles ADD COLUMN {col} TEXT DEFAULT ''")
            if not _column_exists(cur, "articles", "last_inventoried_at"):
                cur.execute("ALTER TABLE articles ADD COLUMN last_inventoried_at TIMESTAMP")
            if not _column_exists(cur, "articles", "storage_node_id"):
                cur.execute("ALTER TABLE articles ADD COLUMN storage_node_id INTEGER")

        if _table_exists(cur, "storage_nodes"):
            if not _column_exists(cur, "storage_nodes", "description"):
                cur.execute("ALTER TABLE storage_nodes ADD COLUMN description TEXT DEFAULT ''")
            if not _column_exists(cur, "storage_nodes", "is_lock"):
                cur.execute("ALTER TABLE storage_nodes ADD COLUMN is_lock BOOLEAN DEFAULT 0")

        if _table_exists(cur, "storage_locations"):
            for col in ("address", "contact_name", "contact_phone", "contact_fax", "contact_email"):
                if not _column_exists(cur, "storage_locations", col):
                    cur.execute(f"ALTER TABLE storage_locations ADD COLUMN {col} TEXT DEFAULT ''")
            if not _column_exists(cur, "storage_locations", "needs_review"):
                cur.execute("ALTER TABLE storage_locations ADD COLUMN needs_review BOOLEAN DEFAULT 0")
                # Alle bereits vorhandenen (aus aelterer Version uebernommenen) Lagerorte
                # als "noch zuzuordnen" markieren, damit der Admin sie beim naechsten
                # Login der richtigen Ebene zuweisen kann.
                cur.execute("UPDATE storage_locations SET needs_review=1")

        if _table_exists(cur, "status_defs"):
            if not _column_exists(cur, "status_defs", "require_note"):
                cur.execute("ALTER TABLE status_defs ADD COLUMN require_note BOOLEAN DEFAULT 0")
            if not _column_exists(cur, "status_defs", "allow_image"):
                cur.execute("ALTER TABLE status_defs ADD COLUMN allow_image BOOLEAN DEFAULT 0")
            if not _column_exists(cur, "status_defs", "issue_policy"):
                cur.execute("ALTER TABLE status_defs ADD COLUMN issue_policy TEXT DEFAULT 'confirm'")
                # Sinnvolle Vorbelegung fuer bestehende Installationen.
                cur.execute("UPDATE status_defs SET issue_policy='direct' WHERE key='verfuegbar'")
                cur.execute("UPDATE status_defs SET issue_policy='blocked' WHERE key='ausgemustert'")
                cur.execute("UPDATE status_defs SET issue_policy='direct' WHERE key='ausgegeben'")

        if _table_exists(cur, "article_images"):
            if not _column_exists(cur, "article_images", "kind"):
                cur.execute("ALTER TABLE article_images ADD COLUMN kind TEXT DEFAULT 'normal'")

        if _table_exists(cur, "issue_records"):
            if not _column_exists(cur, "issue_records", "expected_return_date"):
                cur.execute("ALTER TABLE issue_records ADD COLUMN expected_return_date TIMESTAMP")
            if not _column_exists(cur, "issue_records", "deposit_amount"):
                cur.execute("ALTER TABLE issue_records ADD COLUMN deposit_amount TEXT DEFAULT ''")
            if not _column_exists(cur, "issue_records", "deposit_returned"):
                cur.execute("ALTER TABLE issue_records ADD COLUMN deposit_returned BOOLEAN DEFAULT 0")

        if _table_exists(cur, "receipts"):
            if not _column_exists(cur, "receipts", "article_id"):
                cur.execute("ALTER TABLE receipts ADD COLUMN article_id INTEGER")

        if _table_exists(cur, "doc_templates"):
            if not _column_exists(cur, "doc_templates", "background_filename"):
                cur.execute("ALTER TABLE doc_templates ADD COLUMN background_filename TEXT DEFAULT ''")
            if not _column_exists(cur, "doc_templates", "background_kind"):
                cur.execute("ALTER TABLE doc_templates ADD COLUMN background_kind TEXT DEFAULT ''")

        if _table_exists(cur, "lock_objects"):
            if not _column_exists(cur, "lock_objects", "storage_node_id"):
                cur.execute("ALTER TABLE lock_objects ADD COLUMN storage_node_id INTEGER")
        if _table_exists(cur, "locks"):
            if not _column_exists(cur, "locks", "storage_node_id"):
                cur.execute("ALTER TABLE locks ADD COLUMN storage_node_id INTEGER")

        if _table_exists(cur, "article_types"):
            if not _column_exists(cur, "article_types", "min_stock"):
                cur.execute("ALTER TABLE article_types ADD COLUMN min_stock INTEGER DEFAULT 0")

        if _table_exists(cur, "categories"):
            if not _column_exists(cur, "categories", "issuable_default"):
                cur.execute("ALTER TABLE categories ADD COLUMN issuable_default BOOLEAN DEFAULT 1")

        if _table_exists(cur, "articles"):
            if not _column_exists(cur, "articles", "issuable_override"):
                cur.execute("ALTER TABLE articles ADD COLUMN issuable_override BOOLEAN")
            if not _column_exists(cur, "articles", "is_psa"):
                cur.execute("ALTER TABLE articles ADD COLUMN is_psa BOOLEAN DEFAULT 0")
            if not _column_exists(cur, "articles", "loan_count"):
                cur.execute("ALTER TABLE articles ADD COLUMN loan_count INTEGER DEFAULT 0")
            if not _column_exists(cur, "articles", "wash_count"):
                cur.execute("ALTER TABLE articles ADD COLUMN wash_count INTEGER DEFAULT 0")
            if not _column_exists(cur, "articles", "last_inspection_at"):
                cur.execute("ALTER TABLE articles ADD COLUMN last_inspection_at TIMESTAMP")
            if not _column_exists(cur, "articles", "pending_checklist_id"):
                cur.execute("ALTER TABLE articles ADD COLUMN pending_checklist_id INTEGER")
            if not _column_exists(cur, "articles", "needs_inspection"):
                cur.execute("ALTER TABLE articles ADD COLUMN needs_inspection BOOLEAN DEFAULT 0")
                # Bestehende „zu prüfen"-Artikel als prüfpflichtig übernehmen.
                cur.execute("UPDATE articles SET needs_inspection = 1 WHERE status = 'zu_pruefen'")
            if not _column_exists(cur, "articles", "inspection_override"):
                cur.execute("ALTER TABLE articles ADD COLUMN inspection_override BOOLEAN DEFAULT 0")
            if not _column_exists(cur, "articles", "is_vehicle"):
                cur.execute("ALTER TABLE articles ADD COLUMN is_vehicle BOOLEAN DEFAULT 0")
            for col in ("license_plate", "vin"):
                if not _column_exists(cur, "articles", col):
                    cur.execute(f"ALTER TABLE articles ADD COLUMN {col} TEXT DEFAULT ''")
            if not _column_exists(cur, "articles", "first_registration"):
                cur.execute("ALTER TABLE articles ADD COLUMN first_registration TIMESTAMP")
            if not _column_exists(cur, "articles", "custom_values"):
                cur.execute("ALTER TABLE articles ADD COLUMN custom_values TEXT DEFAULT '{}'")
            if not _column_exists(cur, "articles", "model_id"):
                cur.execute("ALTER TABLE articles ADD COLUMN model_id INTEGER")
            if not _column_exists(cur, "articles", "key_type_id"):
                cur.execute("ALTER TABLE articles ADD COLUMN key_type_id INTEGER")
            if not _column_exists(cur, "articles", "key_serial"):
                cur.execute("ALTER TABLE articles ADD COLUMN key_serial TEXT DEFAULT ''")
        if _table_exists(cur, "storage_nodes"):
            # (Die Spalte heisst seit dem Behaelter-Umbau node_article_id; sie wird
            # weiter oben angelegt bzw. umbenannt.)
            for spalte in ("label_width_mm", "label_height_mm"):
                if not _column_exists(cur, "storage_nodes", spalte):
                    cur.execute(f"ALTER TABLE storage_nodes ADD COLUMN {spalte} INTEGER")
            if not _column_exists(cur, "storage_nodes", "code"):
                cur.execute("ALTER TABLE storage_nodes ADD COLUMN code TEXT")
                cur.execute("UPDATE storage_nodes SET code = 'LO' || id WHERE code IS NULL OR code = ''")
        if _table_exists(cur, "categories"):
            if not _column_exists(cur, "categories", "parent_id"):
                cur.execute("ALTER TABLE categories ADD COLUMN parent_id INTEGER")
            if not _column_exists(cur, "categories", "key_system"):
                cur.execute("ALTER TABLE categories ADD COLUMN key_system BOOLEAN DEFAULT 0")
        if _table_exists(cur, "article_types"):
            if not _column_exists(cur, "article_types", "issuable_default"):
                cur.execute("ALTER TABLE article_types ADD COLUMN issuable_default BOOLEAN")
            if not _column_exists(cur, "article_types", "is_psa_default"):
                cur.execute("ALTER TABLE article_types ADD COLUMN is_psa_default BOOLEAN DEFAULT 0")
        if _table_exists(cur, "size_fields"):
            if not _column_exists(cur, "size_fields", "options"):
                cur.execute("ALTER TABLE size_fields ADD COLUMN options TEXT DEFAULT '[]'")
        if _table_exists(cur, "inspections"):
            if not _column_exists(cur, "inspections", "maintenance_id"):
                cur.execute("ALTER TABLE inspections ADD COLUMN maintenance_id INTEGER")
            if not _column_exists(cur, "inspections", "field_values"):
                cur.execute("ALTER TABLE inspections ADD COLUMN field_values TEXT DEFAULT '{}'")
        if _table_exists(cur, "article_maintenance"):
            if not _column_exists(cur, "article_maintenance", "reminded"):
                cur.execute("ALTER TABLE article_maintenance ADD COLUMN reminded TEXT DEFAULT '[]'")
        if _table_exists(cur, "inspection_rules"):
            if not _column_exists(cur, "inspection_rules", "article_id"):
                cur.execute("ALTER TABLE inspection_rules ADD COLUMN article_id INTEGER")

        if _table_exists(cur, "damage_loss_reports"):
            for col, ddl in (
                ("incident_at", "TIMESTAMP"),
                ("incident_location", "TEXT DEFAULT ''"),
                ("is_theft", "BOOLEAN DEFAULT 0"),
                ("police_reference", "TEXT DEFAULT ''"),
                ("estimated_value", "TEXT DEFAULT ''"),
                ("witnesses", "TEXT DEFAULT ''"),
                ("reporter_contact", "TEXT DEFAULT ''"),
                ("complete", "BOOLEAN DEFAULT 0"),
            ):
                if not _column_exists(cur, "damage_loss_reports", col):
                    cur.execute(f"ALTER TABLE damage_loss_reports ADD COLUMN {col} {ddl}")

        if _table_exists(cur, "users"):
            # Einwilligung in die Telegram-Nutzung (DSGVO Art. 6 Abs. 1 lit. a).
            if not _column_exists(cur, "users", "telegram_consent_at"):
                cur.execute("ALTER TABLE users ADD COLUMN telegram_consent_at TIMESTAMP")
                # Bestehende Verknuepfungen gelten als noch nicht eingewilligt -
                # die Nutzer werden beim naechsten Besuch der Kontoseite gefragt.

        if _table_exists(cur, "articles"):
            # Schluessel: sprechender Zweitname und Schliessgruppe.
            for col, ddl in (("key_alias", "TEXT DEFAULT ''"),
                             ("key_group", "TEXT DEFAULT ''")):
                if not _column_exists(cur, "articles", col):
                    cur.execute(f"ALTER TABLE articles ADD COLUMN {col} {ddl}")

        # (Die Uebernahme der bisherigen Abteilungs-Zuordnung in
        # person_organizations steht in seed.py: die Tabelle wird erst nach dieser
        # Migration von create_all() angelegt, hier waere sie noch nicht da.)

        if _table_exists(cur, "article_maintenance"):
            # Abweichendes Intervall je Fahrzeug (HU 12 statt 24 Monate usw.).
            for col in ("interval_months", "interval_km"):
                if not _column_exists(cur, "article_maintenance", col):
                    cur.execute(f"ALTER TABLE article_maintenance ADD COLUMN {col} INTEGER")

        # Monochromes Wasserzeichen: je Dokumentvorlage und je Lagerort.
        for tabelle in ("doc_templates", "storage_nodes"):
            if _table_exists(cur, tabelle) and not _column_exists(cur, tabelle, "watermark"):
                cur.execute(f"ALTER TABLE {tabelle} ADD COLUMN watermark TEXT")

        if _table_exists(cur, "maintenance_types"):
            # Verfall- oder Funktionspruefung (Farblegende der Inhaltslisten).
            if not _column_exists(cur, "maintenance_types", "kind"):
                cur.execute("ALTER TABLE maintenance_types ADD COLUMN kind TEXT DEFAULT 'funktion'")
                cur.execute("UPDATE maintenance_types SET kind='funktion' WHERE kind IS NULL OR kind=''")

        if _table_exists(cur, "persons"):
            for col in ("size_top", "size_bottom", "size_shoes", "size_head", "size_gloves"):
                if not _column_exists(cur, "persons", col):
                    cur.execute(f"ALTER TABLE persons ADD COLUMN {col} TEXT DEFAULT ''")
            if not _column_exists(cur, "persons", "sizes"):
                cur.execute("ALTER TABLE persons ADD COLUMN sizes TEXT")
            if not _column_exists(cur, "persons", "hidden"):
                cur.execute("ALTER TABLE persons ADD COLUMN hidden BOOLEAN DEFAULT 0")

        # Indizes fuer haeufige Filter/Joins nachziehen (Performance). CREATE INDEX
        # IF NOT EXISTS ist idempotent; wirkt auf bereits bestehende Datenbanken.
        _index_stmts = [
            ("articles", "ix_articles_category_id", "category_id"),
            ("articles", "ix_articles_type_id", "type_id"),
            ("articles", "ix_articles_status", "status"),
            ("articles", "ix_articles_storage_node_id", "storage_node_id"),
            ("articles", "ix_articles_provisional", "provisional"),
            ("issue_records", "ix_issue_records_article_id", "article_id"),
            ("issue_records", "ix_issue_records_person_id", "person_id"),
        ]
        for table, ix_name, column in _index_stmts:
            if _table_exists(cur, table) and _column_exists(cur, table, column):
                cur.execute(f"CREATE INDEX IF NOT EXISTS {ix_name} ON {table} ({column})")

        conn.commit()
    finally:
        conn.close()
