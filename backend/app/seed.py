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
# (key, label, sort_order, is_builtin, require_note, allow_image)
# "Beschädigt" verlangt beim Setzen eine Beschreibung (Freitext) und bietet einen
# optionalen Bild-Anhang (Schadensbild) an.
# Eingebaute Status - werden bei JEDEM Start sichergestellt (sie sind fest im
# Programm verankert und nicht loeschbar).
# (key, label, sort_order, issue_policy)
BUILTIN_STATUSES = [
    ("verfuegbar", "Verfügbar", 10, "direct"),
    ("ausgegeben", "Ausgegeben", 20, "direct"),
    ("reparatur", "In Reparatur", 30, "confirm"),
    ("ausgemustert", "Ausgemustert", 40, "blocked"),
]

# Beispiel-Status - werden NUR bei der Erstinstallation (leere Datenbank) angelegt.
# Loescht der Administrator sie spaeter, kommen sie nicht wieder.
# (key, label, sort_order, require_note, allow_image, issue_policy)
EXAMPLE_STATUSES = [
    ("zu_waschen", "Zu waschen", 50, False, False, "confirm"),
    ("beschaedigt", "Beschädigt", 60, True, True, "confirm"),
    ("infektioes", "Infektiös", 70, False, False, "confirm"),
]


def seed_builtin_statuses(db: Session):
    for key, label, order, policy in BUILTIN_STATUSES:
        if not db.query(models.StatusDef).filter(models.StatusDef.key == key).first():
            db.add(models.StatusDef(
                key=key, label=label, sort_order=order,
                is_builtin=True, active=True, category_ids=[], issue_policy=policy,
            ))
    db.commit()


def seed_example_statuses(db: Session):
    for key, label, order, require_note, allow_image, policy in EXAMPLE_STATUSES:
        if not db.query(models.StatusDef).filter(models.StatusDef.key == key).first():
            db.add(models.StatusDef(
                key=key, label=label, sort_order=order,
                is_builtin=False, active=True, category_ids=[],
                require_note=require_note, allow_image=allow_image, issue_policy=policy,
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


def _split_name(name: str):
    parts = (name or "").strip().split()
    if not parts:
        return ("Benutzer", "-")
    if len(parts) == 1:
        return (parts[0], "-")
    return (parts[0], " ".join(parts[1:]))


def backfill_person_user_links(db: Session):
    """Gleicht bestehende Daten an das Prinzip "Person = Benutzer" an - idempotent,
    laeuft bei jedem Start, macht aber nur einmalig Arbeit:
      1) Benutzer ohne verknuepfte Person -> Person aus dem Namen anlegen & verknuepfen.
      2) Aktive Person ohne Benutzerkonto -> passwortloses Konto (Standardrolle) anlegen.
    """
    from .usernames import ensure_user_for_person

    # 1) Benutzer ohne Person ergaenzen
    for u in db.query(models.User).filter(models.User.person_id.is_(None)).all():
        first, last = _split_name(u.full_name or u.username)
        p = models.Person(first_name=first, last_name=last, active=bool(u.active))
        db.add(p)
        db.commit()
        db.refresh(p)
        u.person_id = p.id
        db.commit()

    # 2) Personen ohne Benutzer ergaenzen (nur aktive, um deaktivierte nicht
    #    "wiederzubeleben").
    linked = {pid for (pid,) in db.query(models.User.person_id)
              .filter(models.User.person_id.isnot(None)).all()}
    for p in db.query(models.Person).filter(models.Person.active == True).all():  # noqa: E712
        if p.id not in linked:
            ensure_user_for_person(db, p)


def backfill_storage_nodes(db: Session):
    """Legt fuer jeden bestehenden Standort (StorageLocation) einen Wurzelknoten im
    verwalteten Standort-Baum an, falls noch keiner gleichen Namens existiert. So
    starten Bestandsinstallationen mit ihren Standorten; Unterebenen werden dann
    frisch im Baum angelegt (Entscheidung "neu aufbauen"). Idempotent."""
    existing = {n.name for n in db.query(models.StorageNode)
                .filter(models.StorageNode.parent_id.is_(None)).all()}
    created = False
    for loc in db.query(models.StorageLocation).all():
        if loc.name in existing:
            continue
        db.add(models.StorageNode(
            parent_id=None, level="standort", name=loc.name,
            address=loc.address or "", contact_name=loc.contact_name or "",
            contact_phone=loc.contact_phone or "", contact_fax=loc.contact_fax or "",
            contact_email=loc.contact_email or "",
        ))
        existing.add(loc.name)
        created = True
    if created:
        db.commit()


def seed(db: Session):
    ensure_defaults(db)
    seed_personalization(db)
    # Eingebaute Status immer sicherstellen (fest im Programm verankert).
    seed_builtin_statuses(db)

    # "Frische" Installation = noch kein Benutzer vorhanden. Nur dann werden die
    # Beispiel-Stammdaten (Kategorie, Typen, Abteilungen) und Beispiel-Status
    # angelegt. Loescht der Administrator sie spaeter, kommen sie NICHT zurueck.
    fresh_install = db.query(models.User).first() is None
    if fresh_install:
        seed_example_statuses(db)

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

    # Bestehende Daten an "Person = Benutzer" angleichen (idempotent).
    backfill_person_user_links(db)
    # Standort-Baum aus bestehenden Standorten vorbelegen (idempotent).
    backfill_storage_nodes(db)
