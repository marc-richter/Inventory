from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, OperationalError
from pydantic import ValidationError

from .logging_config import setup_logging, get_logger
from .database import Base, engine, SessionLocal
from .migrate import run_migrations
from .seed import seed
from .scheduler import start_scheduler
from .config import get_app_version, INSTALLED_VERSION_MARKER
from .routers.auth import auth_router, telegram_router
from .routers.users import users_router, persons_router, groups_router
from .routers.articles import (
    articles_router, lookups_router, issues_router, import_router,
    export_router, labels_router, statuses_router,
)
from .routers.inventory import inventory_router, storage_nodes_router, inspection_router
from .routers.maintenance import (maintenance_router, logbook_router, reports_router,
                                  tires_router)
from .routers.keys import keys_router, printers_router, doc_templates_router
from .routers.settings import (settings_router, backup_router, custom_fields_router,
                               update_router, certificate_router)
from .routers.system import system_router, stats_router, search_router, receipts_router, requests_router
# Der Kennzahlen-Endpunkt gehoert zum optionalen Monitoring-Stack. Fehlt die
# Bibliothek, laeuft die Anwendung ohne ihn weiter - eine Zusatzfunktion darf
# das Programm nicht am Starten hindern.
try:
    from .routers.metrics_router import router as metrics_router
except ImportError:  # pragma: no cover - nur ohne prometheus-client
    metrics_router = None

setup_logging()
log = get_logger("start")

run_migrations()
Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    seed(db)

APP_VERSION = get_app_version()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Gunicorn startet die Worker mit --preload, also durch Abspalten (fork) vom
    # Hauptprozess. Der hat beim Einlesen des Moduls bereits eine Verbindung zur
    # SQLite-Datei geoeffnet (Migration, Grunddaten). Eine SQLite-Verbindung ueber
    # einen fork hinweg weiterzubenutzen, ist ausdruecklich nicht vorgesehen und
    # kann die Datei beschaedigen. Deshalb verwirft jeder Worker die geerbte
    # Verbindung und oeffnet beim ersten Zugriff eine eigene.
    engine.dispose()

    # Zeitgesteuerte Aufgaben und der Telegram-Poller laufen nur in genau einem
    # Worker - sonst wird bei mehreren Gunicorn-Workern mehrfach gesichert und
    # benachrichtigt (siehe app/worker_lock.py).
    from .worker_lock import acquire_background_lock
    if acquire_background_lock():
        start_scheduler()
        from .telegram import start_poller
        start_poller()
    from .routers.system.search import init_search
    init_search()
    try:
        INSTALLED_VERSION_MARKER.write_text(APP_VERSION, encoding="utf-8")
    except OSError:
        pass
    yield
    # Shutdown (if needed)
    # scheduler.shutdown()  # uncomment if you want graceful shutdown


tags_metadata = [
    {"name": "auth", "description": "Authentifizierung: Login, Registrierung, PIN/Passwort ändern, Benutzerinfo"},
    {"name": "telegram", "description": "Telegram-Bot Integration: Linking, Benachrichtigungen, Chat-Verwaltung"},
    {"name": "users", "description": "Benutzerverwaltung: CRUD, Rollen,Capabilities, Deaktivierung"},
    {"name": "persons", "description": "Personenstammdaten: Mitarbeiter, Helfer, Größen, Organisationen"},
    {"name": "groups", "description": "Funktionsgruppen: Rollenzuweisung, Mitgliederverwaltung"},
    {"name": "articles", "description": "Artikelstammdaten: CRUD, Suche, Filter, Historie, Bulk-Erfassung"},
    {"name": "lookups", "description": "Stammdaten-Lookups: Kategorien, Typen, Abteilungen, Lagerorte, Status"},
    {"name": "issues", "description": "Ausgabe/Rücknahme: Einzel & Batch, Pfand, Freitext-Empfänger"},
    {"name": "import", "description": "CSV-Import: Preview, Duplikat-Erkennung, Commit"},
    {"name": "export", "description": "CSV/PDF-Export: Gefilterte Listen, Etiketten"},
    {"name": "labels", "description": "Etikettendruck: Brother QL/PTouch, PDF, Direktdruck"},
    {"name": "statuses", "description": "Konfigurierbare Status: Keys, Labels, Issue-Policies"},
    {"name": "inventory", "description": "Inventur-Kampagnen: Planung, Durchführung, Scans, Fortschritt, Reports"},
    {"name": "storage-nodes", "description": "Hierarchische Lagerorte: Standort→Etage→Raum→Schrank→Fach"},
    {"name": "inspection", "description": "Prüfungen: Checklisten, Regeln, PSA-Prüfungen, Dokumente"},
    {"name": "maintenance", "description": "Wartung: Typen, Intervalle, Termine, Durchführung, Fälligkeitslisten"},
    {"name": "logbook", "description": "Fahrtenbuch/Logbuch: Einträge pro Artikel/Fahrzeug"},
    {"name": "reports", "description": "Berichte: Inventur-Abschluss, Schadensmeldungen, Auswertungen"},
    {"name": "keys", "description": "Schlüssel/Schließanlagen: Typen, Schlösser, Zuordnungen, Depots"},
    {"name": "printers", "description": "Drucker: CUPS/IP, Profile, Anwendungsfall-Zuordnung"},
    {"name": "doc-templates", "description": "Dokumentvorlagen: Briefkopf, Kopf-/Fußzeile, Hintergründe"},
    {"name": "settings", "description": "Systemeinstellungen: Backup, Labels, Organisation, Selbstregistrierung"},
    {"name": "backup", "description": "Backups: Manuell/Automatisch, Download, Restore, Verifikation"},
    {"name": "custom-fields", "description": "Benutzerdefinierte Felder: pro Kategorie/Typ, Typen, Validierung"},
    {"name": "update", "description": "Software-Updates: Versionen, Changelog, Git-basiert"},
    {"name": "system", "description": "Systemsteuerung: Server Power, Health, Version"},
    {"name": "stats", "description": "Statistiken: Dashboard, Mindestbestand, Ausleihen, Analysen"},
    {"name": "search", "description": "Globale Suche: Artikel, Personen, Standorte"},
    {"name": "receipts", "description": "Quittungen: Ausgabe/Rückgabe, Digital, Signaturen"},
    {"name": "requests", "description": "Materialanfragen: Erstellung, Genehmigung, Erfüllung"},
]

app = FastAPI(
    title="Inventarprogramm",
    version=APP_VERSION,
    lifespan=lifespan,
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # nur im lokalen Netz betrieben
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----- Exception Handlers -----

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": f"HTTP_{exc.status_code}"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(x) for x in err["loc"])
        errors.append(f"{loc}: {err['msg']}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Validierungsfehler", "errors": errors, "error_code": "VALIDATION_ERROR"},
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(x) for x in err["loc"])
        errors.append(f"{loc}: {err['msg']}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Validierungsfehler", "errors": errors, "error_code": "VALIDATION_ERROR"},
    )


def _log_db_error(kind: str, request: Request, exc: Exception) -> None:
    """Die eigentliche Datenbankmeldung ins Protokoll schreiben.

    Nach aussen bleibt die Antwort bewusst allgemein - Fehlermeldungen der
    Datenbank gehoeren nicht in die Oberflaeche. Ohne diesen Eintrag stand aber
    auch im Server-Protokoll nichts, sodass sich "Datenbank voruebergehend nicht
    verfuegbar" nicht mehr auf eine Ursache zurueckfuehren liess: gesperrte
    Datei, volle Platte und fehlendes Schreibrecht sehen von aussen gleich aus.
    """
    original = getattr(exc, "orig", None) or exc
    get_logger("datenbank").error(
        "%s bei %s %s -> %s: %s",
        kind, request.method, request.url.path, type(original).__name__, original,
    )


@app.exception_handler(IntegrityError)
async def integrity_exception_handler(request: Request, exc: IntegrityError):
    _log_db_error("Integritaet", request, exc)
    return JSONResponse(
        status_code=409,
        content={"detail": "Datenbank-Integritätsverletzung (z.B. doppelter Schlüssel)", "error_code": "INTEGRITY_ERROR"},
    )


@app.exception_handler(OperationalError)
async def operational_exception_handler(request: Request, exc: OperationalError):
    _log_db_error("Betrieb", request, exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Datenbank vorübergehend nicht verfügbar", "error_code": "DB_UNAVAILABLE"},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Log the exception (in production use proper logging)
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Interner Serverfehler", "error_code": "INTERNAL_ERROR"},
    )


# Auth
app.include_router(auth_router)
app.include_router(telegram_router)

# Users
app.include_router(users_router)
app.include_router(persons_router)
app.include_router(groups_router)

# Articles
app.include_router(articles_router)
app.include_router(lookups_router)
app.include_router(issues_router)
app.include_router(import_router)
app.include_router(export_router)
app.include_router(labels_router)
app.include_router(statuses_router)

# Inventory
app.include_router(inventory_router)
app.include_router(storage_nodes_router)
app.include_router(inspection_router)

# Maintenance
app.include_router(maintenance_router)
app.include_router(logbook_router)
app.include_router(tires_router)
app.include_router(reports_router)

# Keys / Printers / Docs
app.include_router(keys_router)
app.include_router(printers_router)
app.include_router(doc_templates_router)

# Settings
app.include_router(settings_router)
app.include_router(backup_router)
app.include_router(custom_fields_router)
app.include_router(update_router)
app.include_router(certificate_router)

# System
app.include_router(system_router)
app.include_router(stats_router)
app.include_router(search_router)
app.include_router(receipts_router)
app.include_router(requests_router)

# Metrics
if metrics_router is not None:
    app.include_router(metrics_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/version")
def version():
    return {"version": APP_VERSION}
