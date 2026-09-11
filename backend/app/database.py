from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
from .config import DATABASE_URL

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    pool_pre_ping=True,
    pool_recycle=3600,
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    """Bei jeder neuen SQLite-Verbindung sinnvolle Pragmas setzen:
    - WAL: mehrere Nutzer koennen gleichzeitig lesen, waehrend einer schreibt
      (wichtig, wenn mehrere Helfer bei der Inventur parallel scannen).
    - synchronous=NORMAL: gute Balance aus Datensicherheit und Tempo im WAL-Modus.
    - busy_timeout: kurze Schreibsperren werden abgewartet statt sofort zu scheitern.
    - foreign_keys=ON: referentielle Integritaet auch in SQLite durchsetzen.
    - cache_size: mehr Speicher fuer Cache (negativ = KB, -32768 = 32MB).
    - page_size: 4096 Bytes (Standard, gut fuer SSD/SD-Karten).
    - mmap_size: Memory-mapped I/O fuer schnelleres Lesen (256MB).
    - temp_store: temporaere Tabellen im RAM.
    - journal_size_limit: WAL-Datei groesse begrenzen.
    - auto_vacuum: inkrementell, um Fragmentierung zu vermeiden.
    Nur fuer SQLite ausfuehren; bei anderen Datenbanken wirkungslos ueberspringen."""
    try:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA foreign_keys=ON")
        # Performance-Optimierungen fuer Raspberry Pi (SD-Karte, wenig RAM)
        cur.execute("PRAGMA cache_size=-32768")      # 32 MB Cache
        cur.execute("PRAGMA page_size=4096")         # 4KB Pages (Standard)
        cur.execute("PRAGMA mmap_size=268435456")    # 256 MB mmap
        cur.execute("PRAGMA temp_store=MEMORY")      # Temp-Tabellen im RAM
        cur.execute("PRAGMA journal_size_limit=67108864")  # 64 MB WAL-Limit
        cur.execute("PRAGMA auto_vacuum=INCREMENTAL")      # Inkrementelles Vacuum
        cur.execute("PRAGMA optimize")               # Statistiken aktualisieren
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
