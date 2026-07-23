import os
from pathlib import Path

# Basisverzeichnis fuer alle persistenten Daten (per Docker-Volume gemountet)
DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
IMAGES_DIR = DATA_DIR / "images"
BACKUPS_DIR_DEFAULT = DATA_DIR / "backups"
BRANDING_DIR = DATA_DIR / "branding"
DB_PATH = DATA_DIR / "inventar.db"

# Schreibgeschuetzt gemountetes Verzeichnis (docker-compose: ./config -> /app/initial)
# fuer Assets, die die Verwaltungs-App bei der Erstinstallation bereitstellt -
# insbesondere ein optional gewaehltes Logo (siehe DEFAULT_LOGO_FILE).
INITIAL_ASSETS_DIR = Path(os.environ.get("INITIAL_ASSETS_DIR", "/app/initial"))

DATA_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR_DEFAULT.mkdir(parents=True, exist_ok=True)
BRANDING_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.environ.get("SECRET_KEY", "bitte-in-.env-aendern-" + os.urandom(8).hex())
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))

DATABASE_URL = f"sqlite:///{DB_PATH}"

DEFAULT_ADMIN_USERNAME = os.environ.get("DEFAULT_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "admin1234")

# Optionale Personalisierung, die die Verwaltungs-App bei der Erstinstallation
# vorbelegen kann (leer = nicht gesetzt, wird spaeter in der App abgefragt).
# DEFAULT_LOGO_FILE ist ein Pfad INNERHALB des Containers (i.d.R. unter
# INITIAL_ASSETS_DIR), auf den beim ersten Start das Logo uebernommen wird.
DEFAULT_ORG_NAME = os.environ.get("DEFAULT_ORG_NAME", "").strip()
DEFAULT_LOGO_FILE = os.environ.get("DEFAULT_LOGO_FILE", "").strip()

# Versionsdatei aus dem Projekt-Root wird per Docker-Bind-Mount (siehe
# docker-compose.yml) schreibgeschuetzt in den Container gemountet. So laesst
# sich die Version auslesen, ohne das Image bei jeder Aenderung neu bauen zu
# muessen - und die Verwaltungs-Skripte (installer/) koennen dieselbe Datei
# direkt auf dem Host lesen.
VERSION_FILE = Path(os.environ.get("VERSION_FILE", "/app/VERSION"))
# Marker-Datei im (host-sichtbaren) Backup-Verzeichnis: haelt fest, welche
# Version zuletzt erfolgreich gestartet ist - lesbar durch die
# Verwaltungs-Skripte, auch wenn die Container gerade gestoppt sind.
INSTALLED_VERSION_MARKER = BACKUPS_DIR_DEFAULT / ".installed_version"


def get_app_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip() or "unbekannt"
    except OSError:
        return "unbekannt"
