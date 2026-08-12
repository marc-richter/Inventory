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
        if _table_exists(cur, "storage_nodes"):
            if not _column_exists(cur, "storage_nodes", "vehicle_article_id"):
                cur.execute("ALTER TABLE storage_nodes ADD COLUMN vehicle_article_id INTEGER")
            if not _column_exists(cur, "storage_nodes", "code"):
                cur.execute("ALTER TABLE storage_nodes ADD COLUMN code TEXT")
                cur.execute("UPDATE storage_nodes SET code = 'LO' || id WHERE code IS NULL OR code = ''")
        if _table_exists(cur, "categories"):
            if not _column_exists(cur, "categories", "parent_id"):
                cur.execute("ALTER TABLE categories ADD COLUMN parent_id INTEGER")
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
