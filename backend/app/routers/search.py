from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, security
from ..database import get_db
from ..permissions import user_capabilities
from .articles import _article_query, _is_eigen_only, _eigen_article_ids

router = APIRouter(prefix="/api/search", tags=["search"])

LIMIT = 12


def _node_path(n):
    parts, seen = [], set()
    while n is not None and n.id not in seen:
        seen.add(n.id)
        parts.append(n.name)
        n = n.parent
    return " › ".join(reversed(parts))


@router.get("")
def global_search(q: str = "", db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Zentrale Suche ueber alle Bereiche, auf die der angemeldete Nutzer Zugriff hat.
    Ergebnisse sind nach Typ gruppiert; die Berechtigungen werden serverseitig
    beruecksichtigt (z.B. sehen 'eigen'-Nutzer nur ihre eigenen Artikel; Benutzer/
    Gruppen nur Administratoren)."""
    q = (q or "").strip()
    out = {"articles": [], "persons": [], "nodes": [], "users": [], "groups": []}
    if len(q) < 2:
        return out
    like = f"%{q}%"
    caps = user_capabilities(db, user)
    roles = user.roles or []
    is_admin = "admin" in roles

    # Artikel (Berechtigung 'eigen' beruecksichtigen)
    aq = _article_query(db).filter(or_(
        models.Article.artikelnummer.ilike(like),
        models.Article.model.ilike(like),
        models.Article.size.ilike(like),
        models.Article.properties.ilike(like),
        models.Article.remarks.ilike(like),
        models.Article.type.has(models.ArticleType.name.ilike(like)),
    ))
    if _is_eigen_only(user):
        ids = _eigen_article_ids(db, user)
        aq = aq.filter(models.Article.id.in_(ids if ids else [-1]))
    for a in aq.order_by(models.Article.artikelnummer).limit(LIMIT).all():
        label = f"{a.artikelnummer} · {a.type.name if a.type else ''} {a.size or ''}".strip()
        out["articles"].append({"id": a.id, "label": label})

    # Personen (nur mit Personen-/Ausgabe-Recht bzw. Admin)
    if is_admin or ({"persons", "issues"} & caps):
        for p in db.query(models.Person).filter(
                models.Person.active == True,  # noqa: E712
                or_(models.Person.first_name.ilike(like), models.Person.last_name.ilike(like))
        ).order_by(models.Person.last_name).limit(LIMIT).all():
            out["persons"].append({"id": p.id, "name": f"{p.first_name} {p.last_name}".strip()})

    # Lagerorte / Standort-Knoten (fuer alle Angemeldeten sichtbar)
    for n in db.query(models.StorageNode).filter(models.StorageNode.name.ilike(like)) \
            .order_by(models.StorageNode.name).limit(LIMIT).all():
        out["nodes"].append({"id": n.id, "label": _node_path(n)})

    # Benutzer & Gruppen (nur Administratoren)
    if is_admin:
        for u in db.query(models.User).filter(
                or_(models.User.username.ilike(like), models.User.full_name.ilike(like))
        ).order_by(models.User.username).limit(LIMIT).all():
            out["users"].append({"id": u.id, "name": u.full_name or u.username, "username": u.username})
        for g in db.query(models.UserGroup).filter(models.UserGroup.name.ilike(like)) \
                .order_by(models.UserGroup.name).limit(LIMIT).all():
            out["groups"].append({"id": g.id, "name": g.name})

    return out
