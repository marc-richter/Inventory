from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine, SessionLocal
from .migrate import run_migrations
from .seed import seed
from .scheduler import start_scheduler
from .config import get_app_version, INSTALLED_VERSION_MARKER
from .routers import (
    auth, users, lookups, articles, issues, export, labels, backup_router,
    settings_router, persons, import_router, statuses, stats_router, system_router,
    update_router, storage_nodes, inventory, telegram_router, groups, search,
    receipts, requests as requests_router, inspection_router, reports, maintenance, custom_fields, logbook,
)

run_migrations()
Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    seed(db)

APP_VERSION = get_app_version()

app = FastAPI(title="Inventarprogramm", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # nur im lokalen Netz betrieben
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(lookups.router)
app.include_router(articles.router)
app.include_router(issues.router)
app.include_router(export.router)
app.include_router(labels.router)
app.include_router(backup_router.router)
app.include_router(settings_router.router)
app.include_router(persons.router)
app.include_router(import_router.router)
app.include_router(statuses.router)
app.include_router(stats_router.router)
app.include_router(system_router.router)
app.include_router(update_router.router)
app.include_router(storage_nodes.router)
app.include_router(inventory.router)
app.include_router(telegram_router.router)
app.include_router(groups.router)
app.include_router(search.router)
app.include_router(receipts.router)
app.include_router(requests_router.router)
app.include_router(inspection_router.router)
app.include_router(reports.router)
app.include_router(maintenance.router)
app.include_router(custom_fields.router)
app.include_router(logbook.router)


@app.on_event("startup")
def on_startup():
    start_scheduler()
    from .telegram import start_poller
    start_poller()
    try:
        INSTALLED_VERSION_MARKER.write_text(APP_VERSION, encoding="utf-8")
    except OSError:
        pass


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/version")
def version():
    return {"version": APP_VERSION}
