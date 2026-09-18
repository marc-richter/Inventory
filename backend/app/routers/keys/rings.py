"""Schlüsselbünde.

Ein Bund ist die Zusammenfassung mehrerer Schlüssel, die physisch an einem Ring
hängen - "Gerätehaus komplett", "MTW Fahrer". Ausgegeben wird er als Ganzes, und
genau darum geht es: niemand übergibt sieben Schlüssel einzeln.

Warum jeder Schlüssel trotzdem seinen eigenen Ausgabe-Eintrag bekommt: geht einer
verloren, muss im Schließplan genau dieser eine stehen - mit allem, was er
öffnet. Ein Bund als einzelner Datensatz könnte das nicht beantworten.

Ein Schlüssel hängt an höchstens einem Bund. Hängt er schon an einem, wird er
beim Anhängen an einen anderen dort automatisch abgenommen - so wie in
Wirklichkeit.
"""
import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas, security
from app.database import get_db
from app.audit import log_action

router = APIRouter(prefix="/api/v1/keys/rings", tags=["keys"])

CODE_VORSATZ = "SB"


def _naechster_code(db) -> str:
    """Fortlaufender Code für den Anhänger: SB-0001, SB-0002, …"""
    hoechste = 0
    for (code,) in db.query(models.KeyRing.code).all():
        if not code or not code.upper().startswith(CODE_VORSATZ + "-"):
            continue
        teil = code.split("-", 1)[1]
        if teil.isdigit():
            hoechste = max(hoechste, int(teil))
    return f"{CODE_VORSATZ}-{hoechste + 1:04d}"


def _halter(article) -> Optional[str]:
    for iss in article.issues:
        if not iss.return_date:
            return (iss.person and f"{iss.person.first_name} {iss.person.last_name}".strip()) \
                or iss.recipient_name_freetext or None
    return None


def _ist_schluessel(article) -> bool:
    kat = article.category if article is not None else None
    return bool(kat is not None and kat.effective_key_system)


def _anhaengen(db, ring, article_ids):
    """Hängt die genannten Schlüssel an den Bund. Gibt zurück, was übersprungen wurde."""
    uebersprungen = []
    for aid in article_ids:
        a = db.get(models.Article, aid)
        if a is None:
            continue
        if not _ist_schluessel(a):
            uebersprungen.append(f"{a.artikelnummer} (kein Schlüssel)")
            continue
        a.key_ring_id = ring.id
    return uebersprungen


def _serialize(db, ring) -> dict:
    mitglieder, oeffnet, halter, ausgegeben = [], {}, set(), 0
    for a in sorted(ring.keys, key=lambda x: x.artikelnummer or ""):
        wer = _halter(a)
        if a.status == models.ArticleStatus.ausgegeben.value:
            ausgegeben += 1
        halter.add(wer)
        for eintrag in a.locks:
            oeffnet[eintrag["lock_id"]] = eintrag
        mitglieder.append({
            "article_id": a.id, "artikelnummer": a.artikelnummer,
            "key_alias": a.key_alias or "", "key_serial": a.key_serial or "",
            "key_type_name": a.key_type_name, "key_group": a.key_group or "",
            "status": a.status, "holder": wer, "locks": a.locks,
        })
    # Nur wenn ALLE Schlüssel bei derselben Person sind, ist der Bund dort. Steckt
    # einer noch im Schrank, stimmt die Aussage "Bund bei Müller" nicht mehr - und
    # das soll auffallen statt unterzugehen.
    einheitlich = len(halter) == 1
    gemeinsam = next(iter(halter)) if einheitlich else None
    return {
        "id": ring.id, "name": ring.name, "code": ring.code,
        "note": ring.note or "", "active": bool(ring.active),
        "keys": mitglieder, "schluessel_anzahl": len(mitglieder),
        "oeffnet": sorted(oeffnet.values(), key=lambda x: (x["object_name"], x["name"])),
        "holder": gemeinsam,
        "vollstaendig_da": ausgegeben == 0 or ausgegeben == len(mitglieder),
    }


def _laden(db, ring_id):
    ring = db.query(models.KeyRing).options(joinedload(models.KeyRing.keys)) \
        .filter(models.KeyRing.id == ring_id).first()
    if not ring:
        raise HTTPException(status_code=404, detail="Schlüsselbund nicht gefunden")
    return ring


# --------------------------- Bünde ------------------------------------------

@router.get("", response_model=list[schemas.KeyRingOut])
def list_rings(nur_aktive: bool = True, db: Session = Depends(get_db),
               user=Depends(security.get_current_user)):
    q = db.query(models.KeyRing).options(joinedload(models.KeyRing.keys))
    if nur_aktive:
        q = q.filter(models.KeyRing.active == True)  # noqa: E712
    return [_serialize(db, r) for r in q.order_by(models.KeyRing.name).all()]


@router.get("/by-code/{code}", response_model=schemas.KeyRingOut)
def ring_by_code(code: str, db: Session = Depends(get_db),
                 user=Depends(security.get_current_user)):
    """Bund über den Code des Anhängers finden - für den Scanner."""
    ring = db.query(models.KeyRing).options(joinedload(models.KeyRing.keys)) \
        .filter(models.KeyRing.code.ilike(code.strip())).first()
    if not ring:
        raise HTTPException(status_code=404, detail="Schlüsselbund nicht gefunden")
    return _serialize(db, ring)


@router.get("/auswahl")
def ring_auswahl(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Alle Schlüssel mit ihrer Bund-Zugehörigkeit - für die Auswahlliste.

    Absichtlich alle und nicht nur die freien: wer einen Schlüssel an einen
    anderen Bund hängen will, muss ihn finden können, und woher er kommt steht
    dabei. Der Wechsel nimmt ihn am alten Bund automatisch ab.
    """
    kat_ids = [c.id for c in db.query(models.Category).all() if c.effective_key_system]
    if not kat_ids:
        return []
    arts = db.query(models.Article).filter(models.Article.category_id.in_(kat_ids)) \
        .order_by(models.Article.artikelnummer).all()
    return [{
        "id": a.id, "artikelnummer": a.artikelnummer,
        "key_alias": a.key_alias or "", "key_serial": a.key_serial or "",
        "key_group": a.key_group or "", "status": a.status,
        "key_ring_id": a.key_ring_id,
        "key_ring_name": a.key_ring.name if a.key_ring else "",
    } for a in arts]


@router.get("/{ring_id}", response_model=schemas.KeyRingOut)
def get_ring(ring_id: int, db: Session = Depends(get_db),
             user=Depends(security.get_current_user)):
    return _serialize(db, _laden(db, ring_id))


@router.post("", response_model=schemas.KeyRingOut)
def create_ring(payload: schemas.KeyRingCreate, db: Session = Depends(get_db),
                user=Depends(security.require_capability("articles"))):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name erforderlich")
    code = (payload.code or "").strip() or _naechster_code(db)
    if db.query(models.KeyRing).filter(models.KeyRing.code.ilike(code)).first():
        raise HTTPException(status_code=400, detail=f"Der Code „{code}“ ist schon vergeben.")
    ring = models.KeyRing(name=name, code=code, note=payload.note or "")
    db.add(ring)
    db.flush()
    _anhaengen(db, ring, payload.article_ids or [])
    db.commit()
    db.refresh(ring)
    log_action(db, user, "create_key_ring", "key_ring", ring.id, {"name": name, "code": code})
    return _serialize(db, ring)


@router.put("/{ring_id}", response_model=schemas.KeyRingOut)
def update_ring(ring_id: int, payload: schemas.KeyRingUpdate, db: Session = Depends(get_db),
                user=Depends(security.require_capability("articles"))):
    ring = _laden(db, ring_id)
    daten = payload.model_dump(exclude_unset=True)
    if "code" in daten:
        code = (daten.pop("code") or "").strip()
        if code and code.lower() != (ring.code or "").lower():
            if db.query(models.KeyRing).filter(models.KeyRing.code.ilike(code)).first():
                raise HTTPException(status_code=400, detail=f"Der Code „{code}“ ist schon vergeben.")
            ring.code = code
    if "name" in daten:
        name = (daten.pop("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name erforderlich")
        ring.name = name
    for k, v in daten.items():
        setattr(ring, k, v)
    db.commit()
    db.refresh(ring)
    return _serialize(db, ring)


@router.delete("/{ring_id}")
def delete_ring(ring_id: int, db: Session = Depends(get_db),
                user=Depends(security.require_capability("articles"))):
    """Löst den Bund auf. Die Schlüssel selbst bleiben unberührt - sie hängen
    danach an keinem Bund mehr."""
    ring = _laden(db, ring_id)
    for a in list(ring.keys):
        a.key_ring_id = None
    db.delete(ring)
    db.commit()
    log_action(db, user, "delete_key_ring", "key_ring", ring_id)
    return {"ok": True}


# --------------------------- Schlüssel am Bund ------------------------------

@router.put("/{ring_id}/keys", response_model=schemas.KeyRingOut)
def set_ring_keys(ring_id: int, payload: schemas.KeyRingMembersSet, db: Session = Depends(get_db),
                  user=Depends(security.require_capability("articles"))):
    """Setzt die Schlüssel am Bund (komplette Liste)."""
    ring = _laden(db, ring_id)
    gewuenscht = set(payload.article_ids or [])
    for a in list(ring.keys):
        if a.id not in gewuenscht:
            a.key_ring_id = None
    _anhaengen(db, ring, gewuenscht)
    db.commit()
    db.refresh(ring)
    log_action(db, user, "set_key_ring_keys", "key_ring", ring.id,
               {"article_ids": sorted(gewuenscht)})
    return _serialize(db, ring)


@router.post("/{ring_id}/keys/{article_id}", response_model=schemas.KeyRingOut)
def add_ring_key(ring_id: int, article_id: int, db: Session = Depends(get_db),
                 user=Depends(security.require_capability("articles"))):
    ring = _laden(db, ring_id)
    a = db.get(models.Article, article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    if not _ist_schluessel(a):
        raise HTTPException(status_code=400,
                            detail="Nur Schlüssel können an einen Bund gehängt werden.")
    a.key_ring_id = ring.id     # an einem anderen Bund haengt er damit nicht mehr
    db.commit()
    db.refresh(ring)
    return _serialize(db, ring)


@router.delete("/{ring_id}/keys/{article_id}", response_model=schemas.KeyRingOut)
def remove_ring_key(ring_id: int, article_id: int, db: Session = Depends(get_db),
                    user=Depends(security.require_capability("articles"))):
    ring = _laden(db, ring_id)
    a = db.get(models.Article, article_id)
    if a is not None and a.key_ring_id == ring.id:
        a.key_ring_id = None
        db.commit()
        db.refresh(ring)
    return _serialize(db, ring)


# --------------------------- Ausgabe / Rücknahme ----------------------------

@router.post("/{ring_id}/ausgeben")
def issue_ring(ring_id: int, payload: schemas.KeyRingIssue, db: Session = Depends(get_db),
               user=Depends(security.require_capability("issues"))):
    """Gibt den ganzen Bund an eine Person aus.

    Jeder Schlüssel bekommt seinen eigenen Ausgabe-Eintrag - zurück kommen deren
    Nummern, damit sich direkt im Anschluss ein Ausgabeblatt über genau diese
    Übergabe drucken lässt. Klemmt ein einzelner Schlüssel (gesperrter Status,
    schon woanders), wird er gemeldet und die übrigen gehen trotzdem hinaus.
    """
    from app.routers.articles.issues import _try_issue

    ring = _laden(db, ring_id)
    if not payload.person_id and not payload.recipient_name_freetext.strip():
        raise HTTPException(status_code=400, detail="Empfänger fehlt")
    if not ring.keys:
        raise HTTPException(status_code=400, detail="An diesem Bund hängt kein Schlüssel.")

    hinweis = f"Mit Schlüsselbund {ring.code or ring.name} ausgegeben"
    notizen = (payload.notes.strip() + "\n" + hinweis).strip() if payload.notes.strip() else hinweis
    jetzt = dt.datetime.utcnow()

    ausgegeben, probleme, issue_ids = [], [], []
    for a in sorted(ring.keys, key=lambda x: x.artikelnummer or ""):
        res = _try_issue(db, a, payload.person_id, payload.recipient_name_freetext,
                         jetzt, notizen, user, confirm=payload.confirm,
                         expected_return_date=payload.expected_return_date,
                         deposit_amount=payload.deposit_amount)
        if res["ok"]:
            db.flush()
            ausgegeben.append(a.artikelnummer)
            issue_ids.append(res["record"].id)
        else:
            probleme.append({"artikelnummer": a.artikelnummer,
                             "code": res["code"], "detail": res["detail"]})
    db.commit()
    log_action(db, user, "issue_key_ring", "key_ring", ring.id,
               {"ausgegeben": len(ausgegeben), "probleme": len(probleme)})
    return {
        "ring": _serialize(db, ring),
        "ausgegeben": ausgegeben,
        "probleme": probleme,
        "issue_ids": issue_ids,
        "vollstaendig": not probleme,
    }


@router.post("/{ring_id}/zuruecknehmen")
def return_ring(ring_id: int, db: Session = Depends(get_db),
                user=Depends(security.require_capability("issues"))):
    """Nimmt alle offenen Ausgaben der Schlüssel dieses Bunds zurück."""
    from app import inspection

    ring = _laden(db, ring_id)
    jetzt = dt.datetime.utcnow()
    zurueck = []
    for a in ring.keys:
        rec = db.query(models.IssueRecord).filter(
            models.IssueRecord.article_id == a.id,
            models.IssueRecord.return_date.is_(None),
        ).order_by(models.IssueRecord.issue_date.desc()).first()
        if rec is None:
            continue
        rec.return_date = jetzt
        rec.returned_by_user_id = user.id
        if rec.deposit_amount:
            rec.deposit_returned = True
        a.status = models.ArticleStatus.verfuegbar.value
        a.current_location = ""
        inspection.flag_if_due(db, a, just_returned=True)
        zurueck.append(a.artikelnummer)
    db.commit()
    db.refresh(ring)
    log_action(db, user, "return_key_ring", "key_ring", ring.id, {"zurueck": len(zurueck)})
    return {"ring": _serialize(db, ring), "zurueck": zurueck}
