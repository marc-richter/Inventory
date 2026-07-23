import shutil
from pathlib import Path

from sqlalchemy.orm import Session
from . import models, security
from .config import (
    DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ORG_NAME, DEFAULT_LOGO_FILE, BRANDING_DIR,
)
from .settings_helper import ensure_defaults, get_setting, set_setting

DEFAULT_TYPES = ["Polo Shirt", "T-Shirt", "Hose", "Jacke", "Schuhe", "Handschuhe"]
DEFAULT_ORGS = ["Abteilung 01", "Abteilung 02"]

# Eingebaute (is_builtin) und zusaetzliche Standard-Status. is_builtin=True koennen
# nicht geloescht werden. category_ids=[] bedeutet: gilt fuer alle Artikelklassen.
DEFAULT_STATUSES = [
    ("verfuegbar", "Verfügbar", 10, True),
    ("ausgegeben", "Ausgegeben", 20, True),
    ("reparatur", "In Reparatur", 30, True),
    ("ausgemustert", "Ausgemustert", 40, True),
    ("zu_waschen", "Zu waschen", 50, False),
    ("beschaedigt", "Beschädigt", 60, False),
    ("infektioes", "Infektiös", 70, False),
]


def seed_statuses(db: Session):
    for key, label, order, builtin in DEFAULT_STATUSES:
        if not db.query(models.StatusDef).filter(models.StatusDef.key == key).first():
            db.add(models.StatusDef(
                key=key, label=label, sort_order=order,
                is_builtin=builtin, active=True, category_ids=[],
            ))
    db.commit()

# Welche Logo-Dateiendungen bei der Erstinstallation uebernommen werden duerfen.
_LOGO_EXTS = {".png": ".png", ".jpg": ".jpg", ".jpeg": ".jpg", ".svg": ".svg", ".webp": ".webp"}


def seed_personalization(db: Session):
    """Uebernimmt einmalig die von der Verwaltungs-App bei der Erstinstallation
    bereitgestellte Personalisierung (Organisationsname, Logo) - aber nur, solange
    der jeweilige Wert noch nicht gesetzt ist. So werden bei einem spaeteren Start
    keine vom Administrator geaenderten Werte ueberschrieben."""
    # Organisationsname
    if DEFAULT_ORG_NAME and not (get_setting(db, "org_name", "") or "").strip():
        set_setting(db, "org_name", DEFAULT_ORG_NAME)

    # Logo (optional): aus dem gemounteten Initial-Verzeichnis in den Branding-Ordner
    if DEFAULT_LOGO_FILE and not (get_setting(db, "logo_filename", "") or "").strip():
        src = Path(DEFAULT_LOGO_FILE)
        ext = _LOGO_EXTS.get(src.suffix.lower())
        if ext and src.is_file():
            dest_name = f"logo{ext}"
            try:
                BRANDING_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, BRANDING_DIR / dest_name)
                set_setting(db, "logo_filename", dest_name)
            except OSError:
                # Fehlgeschlagenes Kopieren soll den Start nicht verhindern -
                # der Administrator wird ohnehin per Popup an das Logo erinnert.
                pass


def seed(db: Session):
    ensure_defaults(db)
    seed_personalization(db)
    seed_statuses(db)

    if not db.query(models.User).first():
        admin = models.User(
            username=DEFAULT_ADMIN_USERNAME,
            full_name="Administrator",
            roles=[models.Role.admin.value],
            pin_length=4,
        )
        admin.password_hash = security.hash_secret(DEFAULT_ADMIN_PASSWORD)
        db.add(admin)
        db.commit()

    kleidung = db.query(models.Category).filter(models.Category.name == "Kleidung").first()
    if not kleidung:
        kleidung = models.Category(name="Kleidung")
        db.add(kleidung)
        db.commit()
        db.refresh(kleidung)

    for name in DEFAULT_TYPES:
        exists = db.query(models.ArticleType).filter(
            models.ArticleType.category_id == kleidung.id,
            models.ArticleType.name == name
        ).first()
        if not exists:
            db.add(models.ArticleType(name=name, category_id=kleidung.id))
    db.commit()

    for name in DEFAULT_ORGS:
        if not db.query(models.Organization).filter(models.Organization.name == name).first():
            db.add(models.Organization(name=name))
    db.commit()
