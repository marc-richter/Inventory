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

        if _table_exists(cur, "status_defs"):
            if not _column_exists(cur, "status_defs", "require_note"):
                cur.execute("ALTER TABLE status_defs ADD COLUMN require_note BOOLEAN DEFAULT 0")
            if not _column_exists(cur, "status_defs", "allow_image"):
                cur.execute("ALTER TABLE status_defs ADD COLUMN allow_image BOOLEAN DEFAULT 0")

        conn.commit()
    finally:
        conn.close()
