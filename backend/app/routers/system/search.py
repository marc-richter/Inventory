import json
import sys
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import or_, text, func
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from app import models, security
from app.database import get_db
from app.permissions import user_capabilities
from app.routers.articles.articles import _article_query, _is_eigen_only, _eigen_article_ids
from app.audit import log_action

router = APIRouter(prefix="/api/v1/search", tags=["search"])

LIMIT = 12


def _node_path(n):
    parts, seen = [], set()
    while n is not None and n.id not in seen:
        seen.add(n.id)
        parts.append(n.name)
        n = n.parent
    return " › ".join(reversed(parts))


# Ausdruck fuer den Lagerort-Text im Suchindex. Frueher stand hier
# new.location_path - das ist aber KEINE Spalte der Tabelle, sondern eine in
# Python berechnete Eigenschaft (die Eltern-Kette des Lagerort-Baums). SQLite
# prueft Trigger-Rumpfe erst beim Ausloesen, deshalb liess sich der Trigger
# anlegen und scheiterte danach bei JEDEM Anlegen oder Aendern eines Artikels
# mit "no such column: new.location_path" - nach aussen sichtbar als "Datenbank
# voruebergehend nicht verfuegbar". Stattdessen werden hier echte Spalten
# verwendet: der Name des Lagerort-Knotens plus die freien Ortsfelder.
_LOC_EXPR = """
    coalesce((SELECT name FROM storage_nodes WHERE id = new.storage_node_id), '') || ' ' ||
    coalesce(new.etage, '') || ' ' || coalesce(new.raum, '') || ' ' ||
    coalesce(new.schrank, '') || ' ' || coalesce(new.fach, '')
"""

_FTS_COLUMNS = ("artikelnummer, model, size, properties, remarks, "
                "type_name, category_name, location_path")


def _init_fts(db: Session):
    """Legt die Volltext-Tabelle fuer die Artikelsuche an, falls sie fehlt.

    Bewusst OHNE content='articles': die Spalten type_name, category_name und
    location_path gibt es in der Tabelle articles nicht, eine an sie gekoppelte
    Aussenspeicher-Tabelle waere also von vornherein unstimmig. Der Index haelt
    den Text deshalb selbst; das kostet wenig Platz und ist dafuer korrekt.
    """
    result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='articles_fts'"))
    if result.fetchone():
        return
    try:
        db.execute(text(f"""
            CREATE VIRTUAL TABLE articles_fts USING fts5(
                artikelnummer, model, size, properties, remarks,
                type_name, category_name, location_path
            )
        """))
        db.execute(text(f"""
            CREATE TRIGGER articles_ai AFTER INSERT ON articles BEGIN
                INSERT INTO articles_fts(rowid, {_FTS_COLUMNS})
                VALUES (new.id, new.artikelnummer, new.model, new.size, new.properties, new.remarks,
                        (SELECT name FROM article_types WHERE id = new.type_id),
                        (SELECT name FROM categories WHERE id = new.category_id),
                        {_LOC_EXPR});
            END
        """))
        db.execute(text("""
            CREATE TRIGGER articles_ad AFTER DELETE ON articles BEGIN
                DELETE FROM articles_fts WHERE rowid = old.id;
            END
        """))
        db.execute(text(f"""
            CREATE TRIGGER articles_au AFTER UPDATE ON articles BEGIN
                DELETE FROM articles_fts WHERE rowid = old.id;
                INSERT INTO articles_fts(rowid, {_FTS_COLUMNS})
                VALUES (new.id, new.artikelnummer, new.model, new.size, new.properties, new.remarks,
                        (SELECT name FROM article_types WHERE id = new.type_id),
                        (SELECT name FROM categories WHERE id = new.category_id),
                        {_LOC_EXPR});
            END
        """))
        db.execute(text(f"""
            INSERT INTO articles_fts(rowid, {_FTS_COLUMNS})
            SELECT a.id, a.artikelnummer, a.model, a.size, a.properties, a.remarks,
                   at.name, c.name,
                   coalesce(sn.name, '') || ' ' || coalesce(a.etage, '') || ' ' ||
                   coalesce(a.raum, '') || ' ' || coalesce(a.schrank, '') || ' ' ||
                   coalesce(a.fach, '')
            FROM articles a
            LEFT JOIN article_types at ON a.type_id = at.id
            LEFT JOIN categories c ON a.category_id = c.id
            LEFT JOIN storage_nodes sn ON a.storage_node_id = sn.id
        """))
        db.commit()
    except Exception as exc:
        # Nicht stillschweigend verschlucken: ohne diese Meldung blieb frueher
        # unbemerkt, dass der Suchindex gar nicht aufgebaut wurde. Nur der
        # Wettlauf mehrerer Arbeitsprozesse beim ersten Start ist harmlos - dann
        # hat ein anderer Prozess die Tabelle bereits angelegt.
        db.rollback()
        if "already exists" in str(exc):
            return
        print(f"[Suche] Volltextindex konnte nicht angelegt werden: "
              f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)


def _fts_search(db: Session, query: str, limit: int = 20) -> List[int]:
    """FTS5 Suche - gibt Article IDs zurück sortiert nach Relevanz (bm25)."""
    try:
        result = db.execute(text("""
            SELECT rowid FROM articles_fts
            WHERE articles_fts MATCH :query
            ORDER BY bm25(articles_fts)
            LIMIT :limit
        """), {"query": query, "limit": limit})
        return [row[0] for row in result.fetchall()]
    except Exception:
        return []


def init_search():
    """Initialize FTS5 search index - call from main lifespan."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        _init_fts(db)
    finally:
        db.close()


@router.get("")
def global_search(
    q: str = "",
    type: Optional[str] = Query(None, description="Filter: articles, persons, nodes, organizations, users, groups"),
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    location_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort: str = Query("relevance", pattern="^(relevance|date|name|number)$"),
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user=Depends(security.get_current_user),
):
    """Erweiterte Suche mit Filtern, Facetten, Paginierung und FTS5 Full-Text."""
    q = (q or "").strip()
    out = {
        "query": q,
        "filters": {"type": type, "category_id": category_id, "status": status, "location_id": location_id},
        "page": page,
        "page_size": page_size,
        "total": 0,
        "facets": {},
        "results": {"articles": [], "persons": [], "nodes": [], "organizations": [], "users": [], "groups": []}
    }
    
    if len(q) < 2 and not any([type, category_id, status, location_id, date_from, date_to]):
        return out

    caps = user_capabilities(db, user)
    roles = user.roles or []
    is_admin = "admin" in roles

    # Base filters
    article_filters = []
    if category_id:
        article_filters.append(models.Article.category_id == category_id)
    if status:
        article_filters.append(models.Article.status == status)
    if location_id:
        article_filters.append(models.Article.storage_location_id == location_id)

    # FTS5 Suche für Artikel wenn Query vorhanden
    article_ids = []
    if q:
        article_ids = _fts_search(db, q, limit=page_size * 5)

    # Artikel
    if type is None or type == "articles":
        aq = _article_query(db)
        if article_ids:
            aq = aq.filter(models.Article.id.in_(article_ids))
        elif q:
            like = f"%{q}%"
            aq = aq.filter(or_(
                models.Article.artikelnummer.ilike(like),
                models.Article.model.ilike(like),
                models.Article.size.ilike(like),
                models.Article.properties.ilike(like),
                models.Article.remarks.ilike(like),
                models.Article.type.has(models.ArticleType.name.ilike(like)),
            ))
        if article_filters:
            aq = aq.filter(*article_filters)
        if _is_eigen_only(user):
            ids = _eigen_article_ids(db, user)
            aq = aq.filter(models.Article.id.in_(ids if ids else [-1]))
        
        total = aq.count()
        out["total"] = total
        
        # Facetten für Artikel
        out["facets"]["status"] = dict(db.query(models.Article.status, func.count(models.Article.id))
                                       .filter(*article_filters if not q else True)
                                       .group_by(models.Article.status).all())
        out["facets"]["categories"] = dict(db.query(models.Category.name, func.count(models.Article.id))
                                           .join(models.Article)
                                           .filter(*article_filters if not q else True)
                                           .group_by(models.Category.id).all())
        
        offset = (page - 1) * page_size
        articles = aq.order_by(models.Article.artikelnummer.desc()).offset(offset).limit(page_size).all()
        out["results"]["articles"] = [
            {"id": a.id, "artikelnummer": a.artikelnummer, "type": a.type.name if a.type else "",
             "size": a.size, "status": a.status, "location": a.location_path}
            for a in articles
        ]

    # Personen (nur mit Personen-/Ausgabe-Recht bzw. Admin)
    if type is None or type == "persons":
        if is_admin or ({"persons", "issues"} & caps):
            pq = db.query(models.Person).filter(
                models.Person.active == True,  # noqa: E712
                models.Person.hidden == False  # noqa: E712
            )
            if q:
                like = f"%{q}%"
                pq = pq.filter(or_(models.Person.first_name.ilike(like), models.Person.last_name.ilike(like)))
            persons = pq.order_by(models.Person.last_name).limit(LIMIT).all()
            out["results"]["persons"] = [{"id": p.id, "name": f"{p.first_name} {p.last_name}".strip()} for p in persons]

    # Lagerorte / Standort-Knoten
    if type is None or type == "nodes":
        nq = db.query(models.StorageNode)
        if q:
            nq = nq.filter(models.StorageNode.name.ilike(f"%{q}%"))
        if location_id:
            nq = nq.filter(models.StorageNode.id == location_id)
        nodes = nq.order_by(models.StorageNode.name).limit(LIMIT).all()
        out["results"]["nodes"] = [{"id": n.id, "label": _node_path(n)} for n in nodes]

    # Abteilungen
    if type is None or type == "organizations":
        oq = db.query(models.Organization)
        if q:
            oq = oq.filter(models.Organization.name.ilike(f"%{q}%"))
        orgs = oq.order_by(models.Organization.name).limit(LIMIT).all()
        out["results"]["organizations"] = [{"id": o.id, "name": o.name} for o in orgs]

    # Benutzer & Gruppen (nur Admin)
    if is_admin:
        if type is None or type == "users":
            uq = db.query(models.User)
            if q:
                like = f"%{q}%"
                uq = uq.filter(or_(models.User.username.ilike(like), models.User.full_name.ilike(like)))
            users = uq.order_by(models.User.username).limit(LIMIT).all()
            out["results"]["users"] = [{"id": u.id, "name": u.full_name or u.username, "username": u.username} for u in users]
        if type is None or type == "groups":
            gq = db.query(models.UserGroup)
            if q:
                gq = gq.filter(models.UserGroup.name.ilike(f"%{q}%"))
            groups = gq.order_by(models.UserGroup.name).limit(LIMIT).all()
            out["results"]["groups"] = [{"id": g.id, "name": g.name} for g in groups]

    return out


# ----- Search Suggestions / Autocomplete -----

@router.get("/suggest")
def search_suggest(q: str = "", limit: int = 10, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Autocomplete-Vorschläge basierend auf FTS5 Prefix-Suche."""
    q = (q or "").strip()
    if len(q) < 2:
        return {"suggestions": []}
    # Prefix-Suche in FTS
    try:
        result = db.execute(text("""
            SELECT DISTINCT artikelnummer FROM articles_fts
            WHERE articles_fts MATCH :prefix
            ORDER BY bm25(articles_fts)
            LIMIT :limit
        """), {"prefix": f"{q}*", "limit": limit})
        return {"suggestions": [row[0] for row in result.fetchall()]}
    except Exception:
        return {"suggestions": []}


# ----- Saved Search Views -----

class SearchViewCreate(BaseModel):
    name: str
    query: str
    filters: dict = {}
    is_default: bool = False


class SearchViewOut(BaseModel):
    id: int
    name: str
    query: str
    filters: dict
    is_default: bool
    created_at: str
    updated_at: str
    model_config = ConfigDict(from_attributes=True)


@router.post("/views", response_model=SearchViewOut)
def create_search_view(payload: SearchViewCreate, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    view = models.SearchView(
        user_id=user.id,
        name=payload.name,
        query=payload.query,
        filters=json.dumps(payload.filters),
        is_default=payload.is_default
    )
    db.add(view)
    db.commit()
    db.refresh(view)
    log_action(db, user, "create_search_view", "search_view", view.id)
    return view


@router.get("/views", response_model=List[SearchViewOut])
def list_search_views(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    views = db.query(models.SearchView).filter(models.SearchView.user_id == user.id).order_by(models.SearchView.name).all()
    return [{"id": v.id, "name": v.name, "query": v.query, "filters": json.loads(v.filters or "{}"),
             "is_default": v.is_default, "created_at": v.created_at.isoformat(), "updated_at": v.updated_at.isoformat()} for v in views]


@router.put("/views/{view_id}", response_model=SearchViewOut)
def update_search_view(view_id: int, payload: SearchViewCreate, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    view = db.query(models.SearchView).filter(models.SearchView.id == view_id, models.SearchView.user_id == user.id).first()
    if not view:
        raise HTTPException(status_code=404, detail="View nicht gefunden")
    view.name = payload.name
    view.query = payload.query
    view.filters = json.dumps(payload.filters)
    view.is_default = payload.is_default
    db.commit()
    db.refresh(view)
    log_action(db, user, "update_search_view", "search_view", view.id)
    return view


@router.delete("/views/{view_id}")
def delete_search_view(view_id: int, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    view = db.query(models.SearchView).filter(models.SearchView.id == view_id, models.SearchView.user_id == user.id).first()
    if not view:
        raise HTTPException(status_code=404, detail="View nicht gefunden")
    db.delete(view)
    db.commit()
    log_action(db, user, "delete_search_view", "search_view", view_id)
    return {"ok": True}


# FTS rebuild endpoint (Admin)
@router.post("/fts/rebuild")
def rebuild_fts(db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    """FTS5 Index neu aufbauen (z.B. nach Schema-Änderungen)."""
    try:
        # Die Trigger muessen mit weg - sonst scheitert das Neuanlegen daran,
        # dass es sie schon gibt, und die alten (womoeglich fehlerhaften)
        # bleiben in Kraft.
        for trg in ("articles_ai", "articles_au", "articles_ad"):
            db.execute(text(f"DROP TRIGGER IF EXISTS {trg}"))
        db.execute(text("DROP TABLE IF EXISTS articles_fts"))
        db.commit()
        _init_fts(db)
        return {"ok": True, "message": "FTS Index neu aufgebaut"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
