"""Zentrale Protokollierung.

Bis hierher hatte die Anwendung gar keine: Fehler wurden an vielen Stellen
abgefangen und verworfen, sodass sich im Betrieb nicht mehr feststellen liess,
warum etwas nicht funktioniert. Ein fehlerhafter Suchindex blieb so monatelang
unbemerkt, und eine Fehlermeldung der Datenbank fuehrte zu tagelanger Sucherei.

Ausgegeben wird nach stderr - damit landet alles in `docker compose logs`. Die
Stufe laesst sich ueber die Umgebungsvariable LOG_LEVEL steuern (DEBUG, INFO,
WARNING, ERROR); Standard ist INFO.
"""

import logging
import os
import sys

_CONFIGURED = False

FORMAT = "%(asctime)s %(levelname)-8s %(name)-22s %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """Einmalig die Protokollierung einrichten. Mehrfachaufrufe sind harmlos."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    level_name = (os.environ.get("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(FORMAT, datefmt=DATEFMT))

    root = logging.getLogger()
    root.setLevel(level)
    # Vorhandene Handler ersetzen: gunicorn/uvicorn richten eigene ein, sonst
    # erscheint jede Meldung doppelt.
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)

    # Bibliotheken, die sonst jede Kleinigkeit melden, etwas leiser stellen.
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Protokollierer fuer einen Programmteil. `name` ohne Praefix, z.B. "suche"."""
    setup_logging()
    return logging.getLogger(f"inventar.{name}")
