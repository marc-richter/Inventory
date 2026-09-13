"""Bereitstellungen: Artikel vormerken, spaeter gesammelt ausgeben.

Der Ablauf ist der eines Warenkorbs: Artikel werden einer Person zugeordnet,
das Blatt wird gedruckt und zur Ausstattung gelegt, und erst bei der Uebergabe
wird alles auf einmal ausgegeben - dann mit Unterschrift.

Warum ueberhaupt ein Zwischenschritt? Weil Zusammenstellen und Uebergeben
auseinanderfallen: die Einsatzausstattung wird abends gepackt und am naechsten
Morgen abgeholt. Ohne Vormerkung stehen die Sachen bis dahin als verfuegbar da
und werden ein zweites Mal verplant.

Vorgemerkte Artikel bekommen den Status "Vorgemerkt". Er ist ein Hinweis, kein
Verbot: wer den Artikel anderweitig ausgeben will, wird gefragt und kann
bestaetigen. Der vorherige Status wird an der Position gemerkt und
zurueckgesetzt, sobald die Vormerkung endet.

Zusaetzlich lassen sich alle Artikel eines Vorgangs gesammelt an einen anderen
Lagerort umlagern - den Bereitstellungsplatz, an dem die Ausstattung bis zur
Abholung steht. Bei groesseren Ausgaben ist das der eigentliche Gewinn: man
raeumt einmal zusammen, statt beim Uebergeben durch das ganze Lager zu laufen.
"""

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.audit import log_action
from app.database import get_db
from app.realtime import ereignis_melden

from .issues import _try_issue

router = APIRouter(prefix="/api/v1/bereitstellungen", tags=["bereitstellungen"])

# Schluessel des mitgelieferten Status (siehe systemkategorien.STATUS).
VORGEMERKT = "vorgemerkt"


def _status_setzen(db: Session, pos: models.BereitstellungPosition):
    """Artikel auf "Vorgemerkt" setzen und den bisherigen Stand festhalten."""
    a = pos.article
    if a is None or a.status == VORGEMERKT:
        return
    if not db.query(models.StatusDef).filter(models.StatusDef.key == VORGEMERKT).first():
        return      # Status (noch) nicht vorhanden - dann bleibt alles wie es war
    pos.vorheriger_status = a.status
    a.status = VORGEMERKT


def _status_zuruecksetzen(db: Session, pos: models.BereitstellungPosition,
                          lagerort_auch: bool = False):
    """Vormerkung aufheben: Status (und auf Wunsch der Lagerort) wie vorher."""
    a = pos.article
    if a is None:
        return
    if a.status == VORGEMERKT:
        a.status = pos.vorheriger_status or models.ArticleStatus.verfuegbar.value
    if lagerort_auch and pos.vorheriger_node_id:
        a.storage_node_id = pos.vorheriger_node_id
    pos.vorheriger_status = ""


def _code_erzeugen(db: Session) -> str:
    """Fortlaufender, gut scanbarer Code: BS-2026-0007."""
    jahr = dt.date.today().year
    vorsatz = f"BS-{jahr}-"
    letzte = (db.query(models.Bereitstellung)
              .filter(models.Bereitstellung.code.like(f"{vorsatz}%"))
              .order_by(models.Bereitstellung.id.desc()).first())
    nummer = 1
    if letzte:
        try:
            nummer = int(letzte.code.rsplit("-", 1)[1]) + 1
        except (ValueError, IndexError):
            nummer = letzte.id + 1
    return f"{vorsatz}{nummer:04d}"


def _holen(db: Session, bereitstellung_id: int) -> models.Bereitstellung:
    b = db.get(models.Bereitstellung, bereitstellung_id)
    if not b:
        raise HTTPException(status_code=404, detail="Bereitstellung nicht gefunden")
    return b


def _position_out(pos: models.BereitstellungPosition) -> dict:
    a = pos.article
    node = a.storage_node if a is not None else None
    return {
        "id": pos.id,
        "article_id": pos.article_id,
        "artikelnummer": a.artikelnummer if a else "",
        "lagerort": node.name if node is not None else "",
        "typ": a.type.name if (a and a.type) else "",
        "size": (a.size or "") if a else "",
        "model": (a.model or "") if a else "",
        "status": a.status if a else "",
        "issue_record_id": pos.issue_record_id,
    }


def _out(db: Session, b: models.Bereitstellung) -> dict:
    person = b.person
    return {
        "id": b.id,
        "code": b.code,
        "status": b.status,
        "person_id": b.person_id,
        "person": f"{person.first_name} {person.last_name}".strip() if person else "",
        "note": b.note or "",
        "expected_return_date": b.expected_return_date,
        "created_at": b.created_at,
        "created_by": (b.created_by.full_name or b.created_by.username) if b.created_by else "",
        "issued_at": b.issued_at,
        "issued_by": (b.issued_by.full_name or b.issued_by.username) if b.issued_by else "",
        "receipt_id": b.receipt_id,
        "positionen": [_position_out(p) for p in b.positionen],
    }


def offene_vormerkung(db: Session, article_id: int, ausser_id: int = None):
    """Die offene Bereitstellung, auf der dieser Artikel steht - oder None.

    Wird auch aus der Artikelansicht heraus verwendet: wer einen vorgemerkten
    Artikel in der Hand hat, soll sehen, fuer wen er gedacht ist.
    """
    q = (db.query(models.Bereitstellung)
         .join(models.BereitstellungPosition,
               models.BereitstellungPosition.bereitstellung_id == models.Bereitstellung.id)
         .filter(models.BereitstellungPosition.article_id == article_id,
                 models.Bereitstellung.status == models.Bereitstellung.OFFEN))
    if ausser_id:
        q = q.filter(models.Bereitstellung.id != ausser_id)
    return q.first()


@router.get("")
def liste(status: str = "offen", person_id: int = None, db: Session = Depends(get_db),
          user=Depends(security.require_capability("issues"))):
    """Bereitstellungen, standardmaessig die offenen."""
    q = db.query(models.Bereitstellung)
    if status and status != "alle":
        q = q.filter(models.Bereitstellung.status == status)
    if person_id:
        q = q.filter(models.Bereitstellung.person_id == person_id)
    rows = q.order_by(models.Bereitstellung.created_at.desc()).limit(300).all()
    return [_out(db, b) for b in rows]


@router.get("/by-code/{code}")
def nach_code(code: str, db: Session = Depends(get_db),
              user=Depends(security.require_capability("issues"))):
    """Bereitstellung ueber den Scancode des Belegs finden."""
    b = (db.query(models.Bereitstellung)
         .filter(models.Bereitstellung.code == code.strip().upper()).first())
    if not b:
        raise HTTPException(status_code=404, detail="Keine Bereitstellung mit diesem Code")
    return _out(db, b)


@router.get("/fuer-artikel/{article_id}")
def fuer_artikel(article_id: int, db: Session = Depends(get_db),
                 user=Depends(security.require_capability("issues"))):
    """Ist dieser Artikel vorgemerkt - und wenn ja, für wen?"""
    b = offene_vormerkung(db, article_id)
    if not b:
        return {"vorgemerkt": False}
    person = b.person
    return {"vorgemerkt": True, "bereitstellung_id": b.id, "code": b.code,
            "person": f"{person.first_name} {person.last_name}".strip() if person else ""}


@router.get("/{bereitstellung_id}")
def einzeln(bereitstellung_id: int, db: Session = Depends(get_db),
            user=Depends(security.require_capability("issues"))):
    return _out(db, _holen(db, bereitstellung_id))


@router.post("")
def anlegen(payload: schemas.BereitstellungCreate, db: Session = Depends(get_db),
            user=Depends(security.require_capability("issues"))):
    person = db.get(models.Person, payload.person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person nicht gefunden")
    b = models.Bereitstellung(
        code=_code_erzeugen(db), person_id=person.id, status=models.Bereitstellung.OFFEN,
        note=payload.note or "", expected_return_date=payload.expected_return_date,
        created_by_user_id=user.id)
    db.add(b)
    db.flush()
    for article_id in (payload.article_ids or []):
        _position_anlegen(db, b, article_id)
    db.commit()
    db.refresh(b)
    log_action(db, user, "bereitstellung_create", "bereitstellung", b.id,
               {"person_id": person.id, "code": b.code})
    ereignis_melden(db, "bereitstellung")
    return _out(db, b)


def _position_anlegen(db: Session, b: models.Bereitstellung, article_id: int):
    a = db.get(models.Article, article_id)
    if not a:
        raise HTTPException(status_code=404, detail=f"Artikel {article_id} nicht gefunden")
    if any(p.article_id == a.id for p in b.positionen):
        return
    if not a.is_issuable:
        raise HTTPException(status_code=400,
                            detail=f"{a.artikelnummer} ist nicht für die Ausgabe vorgesehen.")
    andere = offene_vormerkung(db, a.id, ausser_id=b.id)
    if andere:
        raise HTTPException(
            status_code=400,
            detail=f"{a.artikelnummer} ist bereits für {andere.person.first_name} "
                   f"{andere.person.last_name} vorgemerkt ({andere.code}).")
    pos = models.BereitstellungPosition(bereitstellung_id=b.id, article_id=a.id,
                                        vorheriger_node_id=a.storage_node_id)
    pos.article = a
    db.add(pos)
    _status_setzen(db, pos)


@router.post("/{bereitstellung_id}/positionen")
def position_hinzufuegen(bereitstellung_id: int, payload: schemas.BereitstellungPositionen,
                         db: Session = Depends(get_db),
                         user=Depends(security.require_capability("issues"))):
    b = _holen(db, bereitstellung_id)
    if b.status != models.Bereitstellung.OFFEN:
        raise HTTPException(status_code=400, detail="Diese Bereitstellung ist abgeschlossen.")
    for article_id in (payload.article_ids or []):
        _position_anlegen(db, b, article_id)
    db.commit()
    db.refresh(b)
    ereignis_melden(db, "bereitstellung")
    return _out(db, b)


@router.delete("/{bereitstellung_id}/positionen/{position_id}")
def position_entfernen(bereitstellung_id: int, position_id: int,
                       lagerort_zuruecksetzen: bool = False, db: Session = Depends(get_db),
                       user=Depends(security.require_capability("issues"))):
    b = _holen(db, bereitstellung_id)
    if b.status != models.Bereitstellung.OFFEN:
        raise HTTPException(status_code=400, detail="Diese Bereitstellung ist abgeschlossen.")
    pos = db.get(models.BereitstellungPosition, position_id)
    if pos and pos.bereitstellung_id == b.id:
        _status_zuruecksetzen(db, pos, lagerort_auch=lagerort_zuruecksetzen)
        db.delete(pos)
        db.commit()
        db.refresh(b)
    ereignis_melden(db, "bereitstellung")
    return _out(db, b)


@router.put("/{bereitstellung_id}")
def aendern(bereitstellung_id: int, payload: schemas.BereitstellungUpdate,
            db: Session = Depends(get_db),
            user=Depends(security.require_capability("issues"))):
    b = _holen(db, bereitstellung_id)
    if b.status != models.Bereitstellung.OFFEN:
        raise HTTPException(status_code=400, detail="Diese Bereitstellung ist abgeschlossen.")
    daten = payload.model_dump(exclude_unset=True)
    for feld in ("note", "expected_return_date"):
        if feld in daten:
            setattr(b, feld, daten[feld])
    db.commit()
    db.refresh(b)
    return _out(db, b)


@router.post("/{bereitstellung_id}/abbrechen")
def abbrechen(bereitstellung_id: int, lagerort_zuruecksetzen: bool = False,
              db: Session = Depends(get_db),
              user=Depends(security.require_capability("issues"))):
    """Vormerkung aufheben - die Artikel sind wieder frei planbar.

    Ihr Status geht auf den Stand vor der Vormerkung zurueck. Der Lagerort nur
    auf Wunsch: wurde die Ausstattung koerperlich auf den Bereitstellungsplatz
    geraeumt, waere ein stilles Zurueckbuchen schlicht falsch.
    """
    b = _holen(db, bereitstellung_id)
    if b.status == models.Bereitstellung.AUSGEGEBEN:
        raise HTTPException(status_code=400,
                            detail="Bereits ausgegeben - das lässt sich nur noch zurücknehmen.")
    for pos in b.positionen:
        if pos.issue_record_id is None:
            _status_zuruecksetzen(db, pos, lagerort_auch=lagerort_zuruecksetzen)
    b.status = models.Bereitstellung.ABGEBROCHEN
    db.commit()
    db.refresh(b)
    log_action(db, user, "bereitstellung_abbrechen", "bereitstellung", b.id, {"code": b.code})
    ereignis_melden(db, "bereitstellung")
    return _out(db, b)


@router.post("/{bereitstellung_id}/ausgeben")
def ausgeben(bereitstellung_id: int, payload: schemas.BereitstellungAusgabe,
             db: Session = Depends(get_db),
             user=Depends(security.require_capability("issues"))):
    """Die Uebergabe: alle vorgemerkten Artikel auf einmal ausgeben.

    Es wird derselbe Weg genommen wie bei der Sammelausgabe - einschliesslich
    aller Pruefungen. Was nicht durchgeht (zwischenzeitlich ausgegeben, gesperrt),
    bleibt stehen und wird gemeldet; die Bereitstellung gilt erst als ausgegeben,
    wenn keine Position mehr offen ist.
    """
    b = _holen(db, bereitstellung_id)
    if b.status == models.Bereitstellung.AUSGEGEBEN:
        raise HTTPException(status_code=400, detail="Diese Bereitstellung ist bereits ausgegeben.")
    if b.status == models.Bereitstellung.ABGEBROCHEN:
        raise HTTPException(status_code=400, detail="Diese Bereitstellung wurde abgebrochen.")

    offene = [p for p in b.positionen if p.issue_record_id is None]
    nur = set(payload.position_ids or [])
    if nur:
        offene = [p for p in offene if p.id in nur]

    ergebnisse = []
    erfolgreich = []
    for pos in offene:
        a = pos.article
        if a is None:
            continue
        # Vor dem Buchen die Vormerkung aufloesen: sonst prueft _try_issue gegen
        # den Status "Vorgemerkt" und verlangt eine Bestaetigung fuer etwas, das
        # hier gerade planmaessig passiert.
        _status_zuruecksetzen(db, pos)
        res = _try_issue(db, a, b.person_id, "", None, b.note, user,
                         confirm=payload.confirm, reissue=payload.reissue,
                         expected_return_date=b.expected_return_date)
        eintrag = {"position_id": pos.id, "article_id": a.id,
                   "artikelnummer": a.artikelnummer, "ok": res["ok"],
                   "code": res.get("code"), "detail": res.get("detail")}
        if res["ok"]:
            erfolgreich.append((pos, res["record"]))
        else:
            # Klappt es nicht, bleibt die Vormerkung bestehen - der Artikel ist ja
            # weiterhin fuer diese Person gedacht.
            _status_setzen(db, pos)
        ergebnisse.append(eintrag)

    db.commit()
    ausgabe_ids = []
    for pos, datensatz in erfolgreich:
        pos.issue_record_id = datensatz.id
        ausgabe_ids.append(datensatz.id)
    if not any(p.issue_record_id is None for p in b.positionen) and b.positionen:
        b.status = models.Bereitstellung.AUSGEGEBEN
        b.issued_at = dt.datetime.utcnow()
        b.issued_by_user_id = user.id
    db.commit()
    db.refresh(b)
    log_action(db, user, "bereitstellung_ausgeben", "bereitstellung", b.id,
               {"code": b.code, "ausgegeben": len(ausgabe_ids)})
    ereignis_melden(db, "bereitstellung")
    return {"bereitstellung": _out(db, b), "results": ergebnisse, "issue_ids": ausgabe_ids}


@router.post("/{bereitstellung_id}/lagerort")
def umlagern(bereitstellung_id: int, payload: schemas.BereitstellungLagerort,
             db: Session = Depends(get_db),
             user=Depends(security.require_capability("issues"))):
    """Alle vorgemerkten Artikel gesammelt an einen Lagerort buchen.

    Der Bereitstellungsplatz, an dem die Ausstattung bis zur Abholung steht. Bei
    groesseren Ausgaben ist das der eigentliche Gewinn: einmal zusammenraeumen
    und einmal buchen, statt beim Uebergeben durch das ganze Lager zu laufen -
    und wer den Artikel sucht, findet ihn dort, wo er wirklich liegt.
    """
    b = _holen(db, bereitstellung_id)
    if b.status != models.Bereitstellung.OFFEN:
        raise HTTPException(status_code=400, detail="Diese Bereitstellung ist abgeschlossen.")
    node = db.get(models.StorageNode, payload.storage_node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Lagerort nicht gefunden")

    bewegt = 0
    for pos in b.positionen:
        if pos.issue_record_id is not None or pos.article is None:
            continue
        if pos.article.storage_node_id == node.id:
            continue
        if pos.vorheriger_node_id is None:
            pos.vorheriger_node_id = pos.article.storage_node_id
        pos.article.storage_node_id = node.id
        bewegt += 1
    db.commit()
    db.refresh(b)
    log_action(db, user, "bereitstellung_umlagern", "bereitstellung", b.id,
               {"code": b.code, "node_id": node.id, "artikel": bewegt})
    ereignis_melden(db, "bereitstellung")
    return {"bereitstellung": _out(db, b), "umgelagert": bewegt, "lagerort": node.name}


@router.put("/{bereitstellung_id}/beleg/{receipt_id}")
def beleg_verknuepfen(bereitstellung_id: int, receipt_id: int, db: Session = Depends(get_db),
                      user=Depends(security.require_capability("issues"))):
    """Den abgelegten (unterschriebenen) Beleg an der Bereitstellung vermerken."""
    b = _holen(db, bereitstellung_id)
    beleg = db.get(models.Receipt, receipt_id)
    if not beleg:
        raise HTTPException(status_code=404, detail="Beleg nicht gefunden")
    b.receipt_id = beleg.id
    db.commit()
    db.refresh(b)
    return _out(db, b)


@router.get("/{bereitstellung_id}/beleg")
def beleg(bereitstellung_id: int, db: Session = Depends(get_db),
          user=Depends(security.require_capability("issues"))):
    """Der Beleg zum Ausdrucken und Beilegen.

    Er traegt den Scancode oben rechts: wer die Ausstattung spaeter uebergibt,
    scannt das Blatt und hat die Bereitstellung vor sich, ohne in einer Liste zu
    suchen. Unterschriftsfelder sind dabei - wird auf Papier unterschrieben,
    wandert das abfotografierte Blatt spaeter als Beleg in die Akte.
    """
    import io as _io

    from fastapi.responses import StreamingResponse
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    from app import pdf_layout

    from .labels import _qr_png

    b = _holen(db, bereitstellung_id)
    person = b.person
    name = f"{person.first_name} {person.last_name}".strip() if person else "—"
    dateiname = f"bereitstellung-{b.code.lower()}.pdf"

    puffer = _io.BytesIO()
    oben, unten, eigener_kopf, canvasmaker = pdf_layout.doc_setup(
        db, "bereitstellung", "Bereitstellung", name, dateiname=dateiname,
        benutzer=getattr(user, "username", "") or "")
    doc = SimpleDocTemplate(puffer, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=oben, bottomMargin=unten, title="Bereitstellung")
    stile = getSampleStyleSheet()
    klein = ParagraphStyle("kl", parent=stile["Normal"], fontSize=8.5, leading=10)
    nutzbreite = A4[0] - 32 * mm

    qr = Image(_io.BytesIO(_qr_png(b.code)), width=26 * mm, height=26 * mm)
    kopfzeilen = [Paragraph(f"<b>{b.code}</b>", stile["Heading2"]),
                  Paragraph(f"Für: <b>{name}</b>", klein),
                  Paragraph(f"Zusammengestellt am {b.created_at.strftime('%d.%m.%Y')}"
                            + (f" von {b.created_by.full_name or b.created_by.username}"
                               if b.created_by else ""), klein)]
    if b.expected_return_date:
        kopfzeilen.append(Paragraph("Rückgabe bis "
                                    + b.expected_return_date.strftime("%d.%m.%Y"), klein))
    inhalt = []
    if eigener_kopf:
        inhalt.append(Paragraph("Bereitstellung", stile["Title"]))
    kopf = Table([[kopfzeilen, qr]], colWidths=[nutzbreite - 30 * mm, 30 * mm])
    kopf.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    inhalt.append(kopf)
    inhalt.append(Spacer(1, 8))
    if b.note:
        inhalt.append(Paragraph(b.note, klein))
        inhalt.append(Spacer(1, 6))

    kopfstil = ParagraphStyle("th", parent=stile["Normal"], fontSize=8, leading=9,
                              textColor=colors.white, fontName="Helvetica-Bold")
    spalten = [("Artikelnr.", "artikelnummer", 0.26), ("Typ", "typ", 0.38),
               ("Größe", "size", 0.14), ("Modell", "model", 0.22)]
    daten = [[Paragraph(t, kopfstil) for (t, _, _) in spalten]]
    for pos in b.positionen:
        zeile = _position_out(pos)
        daten.append([Paragraph(str(zeile.get(k) or ""), klein) for (_, k, _) in spalten])
    if len(daten) == 1:
        daten.append([Paragraph("– noch nichts vorgemerkt –", klein), "", "", ""])
    tabelle = Table(daten, colWidths=[f * nutzbreite for (_, _, f) in spalten], repeatRows=1)
    tabelle.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8B0000")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    inhalt.append(tabelle)
    inhalt.append(Spacer(1, 10))
    inhalt.append(Paragraph(
        f"Mit der Unterschrift wird der Empfang der <b>{len(b.positionen)}</b> oben "
        "aufgeführten Artikel bestätigt. Bis zur Übergabe sind sie im Programm für "
        "die genannte Person vorgemerkt und werden erst beim Ausgeben gebucht.", klein))
    inhalt.append(Spacer(1, 12))

    def unterschrift(rolle, wer):
        return [Paragraph(f"<b>{rolle}</b>: {wer or ''}", klein), Spacer(1, 16 * mm),
                Paragraph("Unterschrift / Datum", ParagraphStyle(
                    "sig", parent=klein, fontSize=7, textColor=colors.grey))]

    felder = Table([[unterschrift("Ausgebende Person", ""), unterschrift("Empfänger", name)]],
                   colWidths=[nutzbreite / 2, nutzbreite / 2])
    felder.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
    inhalt.append(felder)

    doc.build(inhalt, canvasmaker=canvasmaker)
    rohdaten = pdf_layout.finalize(db, "bereitstellung", puffer.getvalue())
    return StreamingResponse(_io.BytesIO(rohdaten), media_type="application/pdf",
                             headers={"Content-Disposition": f'inline; filename="{dateiname}"'})
