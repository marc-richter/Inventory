"""Zustaendigkeit von Materialverwalterinnen und Materialverwaltern.

Bisher hat die Zustaendigkeit (Abteilung und/oder Materialklasse) nur bestimmt,
was in der Auswertung erscheint. Der Artikelbestand selbst war fuer alle
Verwalter vollstaendig sichtbar.

Neu schraenkt eine hinterlegte Zustaendigkeit auch den ARTIKELbestand ein: wer
nur fuer eine Abteilung zustaendig ist, sieht auch nur deren Material.

Bewusst NICHT eingeschraenkt sind Personen. Material wird bei Einsaetzen
abteilungsuebergreifend ausgegeben; wer nur noch die eigenen Leute sehen wuerde,
koennte die Ausgabe nicht mehr erledigen.

Wer gar keine Zustaendigkeit hinterlegt hat, sieht wie bisher alles. Das ist
Absicht: nach einem Update sollen bestehende Verwalter nicht ploetzlich vor
einer leeren Liste stehen. Wer einschraenken will, traegt die Zustaendigkeit ein.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from . import models


def ist_admin(user) -> bool:
    return "admin" in (user.roles or [])


def ist_verwalter(user) -> bool:
    return "verwalter" in (user.roles or [])


def sichtbare_abteilungen(db: Session, user) -> Optional[List[int]]:
    """Auf welche Abteilungen ist dieser Nutzer beim Material beschraenkt?

    None bedeutet: keine Einschraenkung (Administrator, keine Zustaendigkeit
    hinterlegt, oder mindestens eine Zustaendigkeit ohne Abteilungsbindung).
    Eine Liste bedeutet: nur Artikel dieser Abteilungen.
    """
    if ist_admin(user):
        return None
    rows = (db.query(models.MaterialManager)
            .filter(models.MaterialManager.user_id == user.id).all())
    if not rows:
        return None
    if any(r.organization_id is None for r in rows):
        return None       # "alle Abteilungen" ausdruecklich zugewiesen
    return sorted({r.organization_id for r in rows})


def artikel_einschraenken(db: Session, user, query):
    """Haengt die Abteilungs-Einschraenkung an eine Artikel-Abfrage."""
    abteilungen = sichtbare_abteilungen(db, user)
    if abteilungen is None:
        return query
    # Artikel ohne Abteilung bleiben sichtbar - sonst verschwindet Material, das
    # noch niemand zugeordnet hat, klaglos aus der Uebersicht.
    return query.filter(
        (models.Article.organization_id.in_(abteilungen))
        | (models.Article.organization_id.is_(None)))


def darf_artikel_sehen(db: Session, user, artikel: models.Article) -> bool:
    abteilungen = sichtbare_abteilungen(db, user)
    if abteilungen is None:
        return True
    return artikel.organization_id is None or artikel.organization_id in abteilungen
