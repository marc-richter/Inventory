from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import DATABASE_URL

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    """Bei jeder neuen SQLite-Verbindung sinnvolle Pragmas setzen:
    - WAL: mehrere Nutzer koennen gleichzeitig lesen, waehrend einer schreibt
      (wichtig, wenn mehrere Helfer bei der Inventur parallel scannen).
    - synchronous=NORMAL: gute Balance aus Datensicherheit und Tempo im WAL-Modus.
    - busy_timeout: kurze Schreibsperren werden abgewartet statt sofort zu scheitern.
    - foreign_keys=ON: referentielle Integritaet auch in SQLite durchsetzen.
    Nur fuer SQLite ausfuehren; bei anderen Datenbanken wirkungslos ueberspringen."""
    try:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()
    except Exception:
        # z.B. wenn kein SQLite-Backend im Einsatz ist – dann einfach ignorieren.
        pass


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
