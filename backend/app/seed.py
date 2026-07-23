from sqlalchemy.orm import Session
from . import models, security
from .config import DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD
from .settings_helper import ensure_defaults

DEFAULT_TYPES = ["Polo Shirt", "T-Shirt", "Hose", "Jacke", "Schuhe", "Handschuhe"]
DEFAULT_ORGS = ["Abteilung 01", "Abteilung 02"]


def seed(db: Session):
    ensure_defaults(db)

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
