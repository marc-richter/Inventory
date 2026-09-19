"""Dokumente an Artikeln: Pflege, Desinfektion, Bedienungsanleitungen.

Der Administrator legt einmal ab, was immer wieder gebraucht wird; am Artikel
wird es nur noch zugeordnet. Zugeordnet werden kann auf drei Ebenen -
Materialklasse, Artikeltyp, einzelner Artikel -, weil die Wirklichkeit drei
kennt: die Desinfektionsanleitung gilt fuer die ganze Klasse, die
Bedienungsanleitung fuer einen Geraetetyp, die Rechnung fuer genau ein Stueck.

Kommt eine neue Fassung einer Anleitung, wird nur die Datei ersetzt. Alle
Zuordnungen bleiben - das ist der Grund fuer die zentrale Ablage. Wer stattdessen
vierzig Mal dieselbe PDF anhaengt, aktualisiert sie nie wieder.

Zugelassen sind ausschliesslich PDF-Dateien, und zwar geprueft am Inhalt und
nicht an der Endung: eine Datei, die jeder Benutzer spaeter im Browser oeffnet,
darf nichts anderes sein als das, wonach sie aussieht.
"""
import datetime as dt
import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app import dokumentarten, models, schemas, security
from app.audit import log_action
from app.config import DOKUMENTE_DIR
from app.database import get_db

router = APIRouter(prefix="/api/v1/dokumente", tags=["dokumente"])

MAX_BYTES = 40 * 1024 * 1024

# Zugelassene Dateiarten, erkannt an den ersten Bytes und nicht an der Endung:
# was jeder Benutzer spaeter im Browser oeffnet, darf nichts anderes sein als
# das, wonach es aussieht.
#
# Bilder sind ausdruecklich dabei: ein Pflegeetikett fotografiert man ab, man
# scannt es nicht. Wer erst ein PDF daraus bauen muesste, hinterlegt es gar nicht.
DATEIARTEN = [
    (".pdf", "application/pdf", lambda b: b.lstrip()[:5].startswith(b"%PDF-")),
    (".jpg", "image/jpeg", lambda b: b[:3] == b"\xff\xd8\xff"),
    (".png", "image/png", lambda b: b[:8] == b"\x89PNG\r\n\x1a\n"),
    (".webp", "image/webp", lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP"),
    (".heic", "image/heic", lambda b: b[4:8] == b"ftyp"
     and b[8:12] in (b"heic", b"heix", b"hevc", b"mif1", b"msf1")),
    (".gif", "image/gif", lambda b: b[:4] == b"GIF8"),
]
ERLAUBTE_ENDUNGEN = {e for e, _m, _p in DATEIARTEN}


def medientyp(dateiname: str) -> str:
    """Der Medientyp zur Endung - beim Ausliefern, nicht geraten."""
    endung = Path(dateiname or "").suffix.lower()
    for e, mime, _pruef in DATEIARTEN:
        if e == endung:
            return mime
    return "application/octet-stream"


# --------------------------- Hilfen -----------------------------------------

async def _datei_einlesen(file: UploadFile):
    """Liest die hochgeladene Datei und erkennt ihre Art am Inhalt.

    Rueckgabe: (Bytes, Endung). Passt nichts, wird abgelehnt - lieber eine klare
    Meldung als eine Datei, die spaeter niemand oeffnen kann.
    """
    inhalt = await file.read()
    if not inhalt:
        raise HTTPException(status_code=400, detail="Die Datei ist leer.")
    if len(inhalt) > MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Die Datei ist zu groß (max. {MAX_BYTES // (1024 * 1024)} MB). "
                   "Gescannte Anleitungen und Fotos lassen sich meist deutlich verkleinern.")
    for endung, _mime, passt in DATEIARTEN:
        if passt(inhalt):
            return inhalt, endung
    raise HTTPException(
        status_code=400,
        detail="Nur PDF-Dateien und Bilder (JPG, PNG, WEBP, HEIC, GIF) können "
               "hinterlegt werden.")


def _ablegen(inhalt: bytes, original: str, endung: str = ".pdf") -> str:
    stamm = Path(original or "dokument").stem[:40] or "dokument"
    sicher = "".join(c if (c.isascii() and (c.isalnum() or c in "-_")) else "_" for c in stamm)
    name = f"{sicher or 'dokument'}_{uuid.uuid4().hex[:8]}{endung}"
    (DOKUMENTE_DIR / name).write_bytes(inhalt)
    return name


def _datei_loeschen(name: str):
    try:
        (DOKUMENTE_DIR / name).unlink(missing_ok=True)
    except OSError:
        pass   # Eine liegengebliebene Datei ist kein Grund, den Vorgang scheitern zu lassen


def _tags_lesen(roh) -> list:
    """Schlagworte aus einem Formularfeld: durch Komma getrennt.

    Doppelte fliegen raus, und zwar ohne Ruecksicht auf Gross- und
    Kleinschreibung: "TÜV" und "tüv" sind dasselbe Schlagwort, sonst stehen
    beide in der Auswahlliste und die Suche findet nur die Haelfte. Geschrieben
    wird die erste Fassung - so, wie jemand es getippt hat.
    """
    if isinstance(roh, (list, tuple)):
        teile = [str(t) for t in roh]
    else:
        teile = str(roh or "").split(",")
    raus, gesehen = [], set()
    for t in teile:
        t = " ".join(t.split())[:40]
        if not t:
            continue
        if t.casefold() in gesehen:
            continue
        gesehen.add(t.casefold())
        raus.append(t)
    return raus[:20]


def _datum_lesen(roh: str):
    """Datum aus einem Formularfeld. Leer ist erlaubt - nicht jede Anleitung hat eins."""
    roh = (roh or "").strip()
    if not roh:
        return None
    for muster in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return dt.datetime.strptime(roh, muster)
        except ValueError:
            continue
    raise HTTPException(status_code=400,
                        detail=f"„{roh}“ ist kein Datum. Erwartet wird z.B. 2026-03-12.")


def _kategorie_ids(article) -> list:
    """Die Klassen, deren Dokumente fuer diesen Artikel gelten - eigene und Oberklasse.

    Eine Unterklasse erbt die Dokumente ihrer Oberklasse, genau wie sie deren
    Felder und Status erbt. Sonst muesste die Desinfektionsanleitung an
    "Funk", "Funk-Akkus" und "Funk-Zubehoer" einzeln haengen.
    """
    kat = article.category
    if kat is None:
        return []
    ids = [kat.id]
    if kat.parent_id:
        ids.append(kat.parent_id)
    return ids


def _vorgang_text(db, link) -> str:
    """Zu welchem Vorgang das Dokument gehoert - Titel und Datum des Eintrags."""
    if not link.log_entry_id:
        return ""
    eintrag = db.get(models.VehicleLogEntry, link.log_entry_id)
    if eintrag is None:
        return ""
    titel = (eintrag.title or "Eintrag").strip()
    if eintrag.entry_date:
        return f"{titel} am {eintrag.entry_date.strftime('%d.%m.%Y')}"
    return titel


def _ziel_name(db, link) -> tuple:
    if link.article_id:
        a = db.get(models.Article, link.article_id)
        return "artikel", link.article_id, (a.artikelnummer if a else "—")
    if link.type_id:
        t = db.get(models.ArticleType, link.type_id)
        return "typ", link.type_id, (t.name if t else "—")
    if link.category_id:
        k = db.get(models.Category, link.category_id)
        return "klasse", link.category_id, (k.name if k else "—")
    return "", 0, "—"


def _artikel_anzahl(db, dok) -> int:
    """Fuer wie viele Artikel gilt dieses Dokument insgesamt?

    Die Zahl beantwortet die Frage, die vor dem Loeschen zaehlt: wem fehlt
    hinterher etwas. Doppelt gezaehlt wird nicht - ein Artikel, der ueber Klasse
    UND Typ getroffen wird, ist ein Artikel.
    """
    kat_ids = [l.category_id for l in dok.links if l.category_id]
    typ_ids = [l.type_id for l in dok.links if l.type_id]
    art_ids = {l.article_id for l in dok.links if l.article_id}
    if kat_ids:
        # Unterklassen erben - also auch deren Artikel mitzaehlen.
        kinder = [c.id for c in db.query(models.Category.id)
                  .filter(models.Category.parent_id.in_(kat_ids)).all()]
        kat_ids = list(set(kat_ids) | set(kinder))
    treffer = set(art_ids)
    if kat_ids:
        treffer |= {r.id for r in db.query(models.Article.id)
                    .filter(models.Article.category_id.in_(kat_ids)).all()}
    if typ_ids:
        treffer |= {r.id for r in db.query(models.Article.id)
                    .filter(models.Article.type_id.in_(typ_ids)).all()}
    return len(treffer)


def _serialize(db, dok, mit_zuordnungen: bool = True) -> dict:
    zuordnungen = []
    if mit_zuordnungen:
        for l in dok.links:
            ebene, ziel_id, name = _ziel_name(db, l)
            if ebene:
                zuordnungen.append({"id": l.id, "ebene": ebene,
                                    "ziel_id": ziel_id, "ziel_name": name})
        zuordnungen.sort(key=lambda z: (z["ebene"], z["ziel_name"]))
    sym = next((s for k, _l, _so, s in dokumentarten.ARTEN if k == dok.art), "📄")
    return {
        "id": dok.id, "title": dok.title, "art": dok.art,
        "art_label": dokumentarten.bezeichnung(dok.art), "symbol": sym,
        "original_name": dok.original_name or "", "size_bytes": dok.size_bytes or 0,
        "stand": dok.stand or "", "note": dok.note or "",
        "zentral": bool(dok.zentral), "active": bool(dok.active),
        "doc_date": dok.doc_date, "tags": list(dok.tags or []),
        "uploaded_at": dok.uploaded_at,
        "uploaded_by_name": (dok.uploaded_by.full_name or dok.uploaded_by.username)
                            if dok.uploaded_by else "",
        "zuordnungen": zuordnungen,
        "artikel_anzahl": _artikel_anzahl(db, dok) if mit_zuordnungen else 0,
    }


def _laden(db, dokument_id):
    dok = db.query(models.Document).options(joinedload(models.Document.links)) \
        .filter(models.Document.id == dokument_id).first()
    if not dok:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    return dok


# --------------------------- Ablage -----------------------------------------

@router.get("/arten")
def list_arten(user=Depends(security.get_current_user)):
    return dokumentarten.katalog()


@router.get("/tags")
def list_tags(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Alle vergebenen Schlagworte mit Anzahl - fuer Filterleiste und Vorschlaege.

    Gezaehlt wird ohne Ruecksicht auf Gross- und Kleinschreibung; angezeigt wird
    die haeufigste Schreibweise, damit die Liste nicht "TÜV" und "tüv"
    nebeneinander zeigt.
    """
    zaehler = {}
    for (roh,) in db.query(models.Document.tags).filter(
            models.Document.active == True).all():  # noqa: E712
        for t in (roh or []):
            eintrag = zaehler.setdefault(str(t).casefold(), {"schreibweisen": {}, "anzahl": 0})
            eintrag["anzahl"] += 1
            eintrag["schreibweisen"][t] = eintrag["schreibweisen"].get(t, 0) + 1
    raus = [{"tag": max(v["schreibweisen"].items(), key=lambda x: x[1])[0], "anzahl": v["anzahl"]}
            for v in zaehler.values()]
    raus.sort(key=lambda x: (-x["anzahl"], x["tag"].casefold()))
    return raus


@router.get("", response_model=list[schemas.DokumentOut])
def list_dokumente(art: str = "", q: str = "", tag: str = "", nur_aktive: bool = True,
                   sortierung: str = "art",
                   db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Die zentrale Ablage. Dokumente, die nur zu einem Artikel gehoeren, stehen
    hier nicht - die wuerden die Ablage zumuellen.

    Gefiltert und gesucht wird in Python statt in SQL: die Schlagworte liegen als
    Liste in einem JSON-Feld, danach sucht SQLite nicht sinnvoll. Bei der
    Groessenordnung einer Vereinsablage kostet das nichts und bleibt lesbar.

    sortierung: "art" (Standard: nach Dokumentart, dann Titel) oder "datum"
    (neueste zuerst - das beantwortet "die letzten Berichte").
    """
    query = db.query(models.Document).options(joinedload(models.Document.links)) \
        .filter(models.Document.zentral == True)  # noqa: E712
    if nur_aktive:
        query = query.filter(models.Document.active == True)  # noqa: E712
    if art:
        query = query.filter(models.Document.art == dokumentarten.normalisieren(art))
    dokumente = query.all()

    if tag.strip():
        gesucht = tag.strip().casefold()
        dokumente = [d for d in dokumente
                     if any(str(t).casefold() == gesucht for t in (d.tags or []))]
    if q.strip():
        gesucht = q.strip().casefold()

        def passt(d):
            felder = [d.title or "", d.note or "", d.original_name or "", d.stand or ""]
            felder += [str(t) for t in (d.tags or [])]
            return any(gesucht in f.casefold() for f in felder)

        dokumente = [d for d in dokumente if passt(d)]

    if sortierung == "datum":
        dokumente.sort(key=lambda d: (d.doc_date or d.uploaded_at or dt.datetime.min),
                       reverse=True)
    else:
        reihe = {k: i for i, (k, _l, _s, _y) in enumerate(dokumentarten.ARTEN)}
        dokumente.sort(key=lambda d: (reihe.get(d.art, 99), (d.title or "").lower()))
    return [_serialize(db, d) for d in dokumente]


@router.post("", response_model=schemas.DokumentOut)
async def upload_dokument(file: UploadFile = File(...), title: str = Form(""),
                          art: str = Form("sonstiges"), stand: str = Form(""),
                          note: str = Form(""), doc_date: str = Form(""),
                          tags: str = Form(""), db: Session = Depends(get_db),
                          user=Depends(security.require_roles("admin", "verwalter"))):
    """Legt ein Dokument in der zentralen Ablage ab."""
    inhalt, endung = await _datei_einlesen(file)
    pruefsumme = hashlib.sha256(inhalt).hexdigest()
    doppelt = db.query(models.Document).filter(
        models.Document.sha256 == pruefsumme,
        models.Document.zentral == True).first()  # noqa: E712
    if doppelt is not None:
        raise HTTPException(
            status_code=400,
            detail=f"Dieselbe Datei liegt schon als „{doppelt.title}“ in der Ablage. "
                   "Für eine neue Fassung bitte dort „Neue Fassung“ verwenden – dann "
                   "bleiben alle Zuordnungen erhalten.")
    name = _ablegen(inhalt, file.filename or "", endung)
    dok = models.Document(
        title=(title.strip() or Path(file.filename or "Dokument").stem)[:160],
        art=dokumentarten.normalisieren(art), filename=name,
        original_name=(file.filename or "")[:256], size_bytes=len(inhalt),
        sha256=pruefsumme, stand=stand.strip()[:48], note=note.strip(),
        doc_date=_datum_lesen(doc_date), tags=_tags_lesen(tags),
        zentral=True, uploaded_by_id=user.id,
    )
    db.add(dok)
    db.commit()
    db.refresh(dok)
    log_action(db, user, "upload_dokument", "dokument", dok.id,
               {"title": dok.title, "art": dok.art})
    return _serialize(db, dok)


@router.post("/{dokument_id}/datei", response_model=schemas.DokumentOut)
async def neue_fassung(dokument_id: int, file: UploadFile = File(...),
                       stand: str = Form(""), db: Session = Depends(get_db),
                       user=Depends(security.require_roles("admin", "verwalter"))):
    """Ersetzt die Datei eines Dokuments. Alle Zuordnungen bleiben bestehen -
    genau dafuer gibt es die zentrale Ablage."""
    dok = _laden(db, dokument_id)
    inhalt, endung = await _datei_einlesen(file)
    alt = dok.filename
    dok.filename = _ablegen(inhalt, file.filename or "", endung)
    dok.original_name = (file.filename or "")[:256]
    dok.size_bytes = len(inhalt)
    dok.sha256 = hashlib.sha256(inhalt).hexdigest()
    dok.uploaded_at = dt.datetime.utcnow()
    dok.uploaded_by_id = user.id
    if stand.strip():
        dok.stand = stand.strip()[:48]
    db.commit()
    db.refresh(dok)
    if alt and alt != dok.filename:
        _datei_loeschen(alt)
    log_action(db, user, "neue_fassung_dokument", "dokument", dok.id, {"stand": dok.stand})
    return _serialize(db, dok)


@router.put("/{dokument_id}", response_model=schemas.DokumentOut)
def update_dokument(dokument_id: int, payload: schemas.DokumentUpdate,
                    db: Session = Depends(get_db),
                    user=Depends(security.require_roles("admin", "verwalter"))):
    dok = _laden(db, dokument_id)
    daten = payload.model_dump(exclude_unset=True)
    if "title" in daten:
        titel = (daten.pop("title") or "").strip()
        if not titel:
            raise HTTPException(status_code=400, detail="Titel erforderlich")
        dok.title = titel[:160]
    if "art" in daten:
        dok.art = dokumentarten.normalisieren(daten.pop("art"))
    if "stand" in daten:
        dok.stand = (daten.pop("stand") or "").strip()[:48]
    if "tags" in daten:
        dok.tags = _tags_lesen(daten.pop("tags"))
    for k, v in daten.items():
        setattr(dok, k, v)
    db.commit()
    db.refresh(dok)
    return _serialize(db, dok)


@router.delete("/{dokument_id}")
def delete_dokument(dokument_id: int, db: Session = Depends(get_db),
                    user=Depends(security.require_roles("admin", "verwalter"))):
    """Loescht ein Dokument samt Datei und allen Zuordnungen."""
    dok = _laden(db, dokument_id)
    name = dok.filename
    db.delete(dok)          # Zuordnungen haengen per cascade daran
    db.commit()
    _datei_loeschen(name)
    log_action(db, user, "delete_dokument", "dokument", dokument_id)
    return {"ok": True}


@router.get("/{dokument_id}/datei")
def dokument_datei(dokument_id: int, db: Session = Depends(get_db),
                   user=Depends(security.get_current_user)):
    """Liefert das PDF aus - zum Ansehen im Browser."""
    dok = db.get(models.Document, dokument_id)
    if not dok:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    pfad = DOKUMENTE_DIR / dok.filename
    if not pfad.exists():
        raise HTTPException(
            status_code=404,
            detail="Die Datei fehlt auf dem Server. Sie ging vermutlich bei einer "
                   "Wiederherstellung verloren – bitte neu hochladen.")
    from app import pdf_layout
    name = pdf_layout.dateiname_teil(dok.title) or "dokument"
    endung = Path(dok.filename).suffix.lower() or ".pdf"
    return FileResponse(
        pfad, media_type=medientyp(dok.filename),
        headers={"Content-Disposition": f'inline; filename="{name}{endung}"',
                 # Der Browser soll den Typ NICHT selbst raten - wir haben ihn
                 # beim Hochladen am Inhalt bestimmt.
                 "X-Content-Type-Options": "nosniff"})


# --------------------------- Zuordnungen ------------------------------------

def _zuordnung_anlegen(db, dok, category_id=None, type_id=None, article_id=None,
                       log_entry_id=None):
    """Legt eine Zuordnung an, sofern es sie nicht schon gibt."""
    vorhanden = db.query(models.DocumentLink).filter(
        models.DocumentLink.document_id == dok.id,
        models.DocumentLink.category_id.is_(category_id) if category_id is None
        else models.DocumentLink.category_id == category_id,
        models.DocumentLink.type_id.is_(type_id) if type_id is None
        else models.DocumentLink.type_id == type_id,
        models.DocumentLink.article_id.is_(article_id) if article_id is None
        else models.DocumentLink.article_id == article_id,
    ).first()
    if vorhanden is not None and log_entry_id and not vorhanden.log_entry_id:
        # Nachtraeglich einem Vorgang zugeordnet.
        vorhanden.log_entry_id = log_entry_id
    if vorhanden is None:
        link = models.DocumentLink(document_id=dok.id, category_id=category_id,
                                   type_id=type_id, article_id=article_id,
                                   log_entry_id=log_entry_id)
        db.add(link)
        db.flush()
        return link
    return vorhanden


@router.put("/{dokument_id}/zuordnungen", response_model=schemas.DokumentOut)
def set_zuordnungen(dokument_id: int, payload: schemas.DokumentZuordnungenSet,
                    db: Session = Depends(get_db),
                    user=Depends(security.require_roles("admin", "verwalter"))):
    """Setzt Klassen und Typen, an denen dieses Dokument haengt (komplette Liste).

    Artikel-Zuordnungen bleiben unberuehrt: die pflegt der Materialverwalter am
    Artikel, und sie sollen nicht verschwinden, weil der Administrator hier eine
    Klasse anhakt.
    """
    dok = _laden(db, dokument_id)
    kat_soll = set(payload.category_ids or [])
    typ_soll = set(payload.type_ids or [])
    for l in list(dok.links):
        if l.category_id and l.category_id not in kat_soll:
            db.delete(l)
        elif l.type_id and l.type_id not in typ_soll:
            db.delete(l)
    db.flush()
    for kid in kat_soll:
        if db.get(models.Category, kid):
            _zuordnung_anlegen(db, dok, category_id=kid)
    for tid in typ_soll:
        if db.get(models.ArticleType, tid):
            _zuordnung_anlegen(db, dok, type_id=tid)
    db.commit()
    db.refresh(dok)
    log_action(db, user, "set_dokument_zuordnungen", "dokument", dok.id,
               {"klassen": sorted(kat_soll), "typen": sorted(typ_soll)})
    return _serialize(db, dok)


@router.delete("/zuordnungen/{link_id}")
def delete_zuordnung(link_id: int, db: Session = Depends(get_db),
                     user=Depends(security.require_capability("articles"))):
    """Loest eine einzelne Zuordnung. Gehoert das Dokument nur diesem einen
    Artikel, verschwindet mit der letzten Zuordnung auch das Dokument - sonst
    bliebe eine Datei zurueck, die niemand mehr findet."""
    link = db.get(models.DocumentLink, link_id)
    if not link:
        return {"ok": True}
    dok = db.get(models.Document, link.document_id)
    db.delete(link)
    db.flush()
    verwaist = dok is not None and not dok.zentral and not dok.links
    name = dok.filename if verwaist else ""
    if verwaist:
        db.delete(dok)
    db.commit()
    if name:
        _datei_loeschen(name)
    return {"ok": True, "dokument_geloescht": bool(name)}


# --------------------------- Am Artikel -------------------------------------
#
# Eigener Router, weil die Adresse zum Artikel gehoert und nicht zur Ablage.

artikel_router = APIRouter(prefix="/api/v1/articles", tags=["dokumente"])


@artikel_router.get("/{article_id}/dokumente", response_model=list[schemas.ArtikelDokumentOut])
def artikel_dokumente(article_id: int, db: Session = Depends(get_db),
                      user=Depends(security.get_current_user)):
    """Alle Dokumente, die fuer diesen Artikel gelten - samt Herkunft.

    Die Herkunft steht dabei, weil sie die naechste Frage beantwortet: wer das
    Dokument loswerden will, muss wissen, ob es an diesem Stueck haengt oder an
    der ganzen Klasse. Trifft dasselbe Dokument ueber mehrere Ebenen zu, gewinnt
    die speziellste - der Artikel vor dem Typ, der Typ vor der Klasse.
    """
    a = db.get(models.Article, article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")

    kat_ids = _kategorie_ids(a)
    bedingungen = [models.DocumentLink.article_id == a.id]
    if a.type_id:
        bedingungen.append(models.DocumentLink.type_id == a.type_id)
    if kat_ids:
        bedingungen.append(models.DocumentLink.category_id.in_(kat_ids))
    from sqlalchemy import or_
    links = db.query(models.DocumentLink).filter(or_(*bedingungen)).all()

    rang = {"artikel": 0, "typ": 1, "klasse": 2}
    beste = {}
    for l in links:
        dok = db.get(models.Document, l.document_id)
        if dok is None or not dok.active:
            continue
        ebene, _ziel_id, name = _ziel_name(db, l)
        vorhanden = beste.get(dok.id)
        if vorhanden and rang[vorhanden["herkunft"]] <= rang[ebene]:
            continue
        sym = next((s for k, _lb, _so, s in dokumentarten.ARTEN if k == dok.art), "📄")
        beste[dok.id] = {
            "id": dok.id, "title": dok.title, "art": dok.art,
            "art_label": dokumentarten.bezeichnung(dok.art), "symbol": sym,
            "original_name": dok.original_name or "", "size_bytes": dok.size_bytes or 0,
            "stand": dok.stand or "", "note": dok.note or "",
            "zentral": bool(dok.zentral),
            "doc_date": dok.doc_date, "tags": list(dok.tags or []),
            "herkunft": ebene, "herkunft_name": name,
            "link_id": l.id if ebene == "artikel" else None,
            "vorgang": _vorgang_text(db, l),
            "log_entry_id": l.log_entry_id,
        }
    # Innerhalb einer Dokumentart das Neueste zuerst: bei TUEV-Berichten und
    # Werkstattrechnungen ist genau das die Frage - welcher ist der letzte.
    reihe = {k: i for i, (k, _l, _s, _y) in enumerate(dokumentarten.ARTEN)}
    return sorted(beste.values(),
                  key=lambda d: (reihe.get(d["art"], 99),
                                 -(d["doc_date"].timestamp() if d["doc_date"] else 0),
                                 d["title"].lower()))


@artikel_router.post("/{article_id}/dokumente", response_model=schemas.ArtikelDokumentOut)
async def artikel_dokument_hochladen(article_id: int, file: UploadFile = File(...),
                                     title: str = Form(""), art: str = Form("sonstiges"),
                                     stand: str = Form(""), note: str = Form(""),
                                     doc_date: str = Form(""), tags: str = Form(""),
                                     log_entry_id: str = Form(""),
                                     db: Session = Depends(get_db),
                                     user=Depends(security.require_capability("articles"))):
    """Haengt eine eigene PDF an genau diesen Artikel.

    Fuer das, was es nur einmal gibt: die Rechnung, das Pruefprotokoll des
    Herstellers, die Kopie des Fahrzeugscheins. In der zentralen Ablage taucht so
    ein Dokument nicht auf - dort gehoert nur hin, was wiederverwendet wird.
    """
    a = db.get(models.Article, article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    inhalt, endung = await _datei_einlesen(file)
    name = _ablegen(inhalt, file.filename or "", endung)
    dok = models.Document(
        title=(title.strip() or Path(file.filename or "Dokument").stem)[:160],
        art=dokumentarten.normalisieren(art), filename=name,
        original_name=(file.filename or "")[:256], size_bytes=len(inhalt),
        sha256=hashlib.sha256(inhalt).hexdigest(), stand=stand.strip()[:48],
        note=note.strip(), doc_date=_datum_lesen(doc_date), tags=_tags_lesen(tags),
        zentral=False, uploaded_by_id=user.id,
    )
    vorgang = None
    if (log_entry_id or "").strip().isdigit():
        eintrag = db.get(models.VehicleLogEntry, int(log_entry_id))
        if eintrag is None or eintrag.article_id != a.id:
            raise HTTPException(status_code=400,
                                detail="Der gewählte Vorgang gehört nicht zu diesem Artikel.")
        vorgang = eintrag.id
    db.add(dok)
    db.flush()
    link = _zuordnung_anlegen(db, dok, article_id=a.id, log_entry_id=vorgang)
    db.commit()
    db.refresh(dok)
    log_action(db, user, "upload_artikel_dokument", "article", a.id, {"title": dok.title})
    sym = next((s for k, _lb, _so, s in dokumentarten.ARTEN if k == dok.art), "📄")
    return {
        "id": dok.id, "title": dok.title, "art": dok.art,
        "art_label": dokumentarten.bezeichnung(dok.art), "symbol": sym,
        "original_name": dok.original_name or "", "size_bytes": dok.size_bytes or 0,
        "stand": dok.stand or "", "note": dok.note or "", "zentral": False,
        "doc_date": dok.doc_date, "tags": list(dok.tags or []),
        "herkunft": "artikel", "herkunft_name": a.artikelnummer, "link_id": link.id,
        "vorgang": _vorgang_text(db, link), "log_entry_id": link.log_entry_id,
    }


@artikel_router.post("/{article_id}/dokumente/{dokument_id}")
def artikel_dokument_zuordnen(article_id: int, dokument_id: int,
                              db: Session = Depends(get_db),
                              user=Depends(security.require_capability("articles"))):
    """Ordnet ein Dokument aus der Ablage genau diesem Artikel zu."""
    a = db.get(models.Article, article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    dok = db.get(models.Document, dokument_id)
    if not dok:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    if not dok.zentral:
        raise HTTPException(
            status_code=400,
            detail="Dieses Dokument gehört bereits zu genau einem Artikel und lässt "
                   "sich nicht weiterverteilen. Wiederkehrendes gehört in die Ablage "
                   "unter Einstellungen › Stammdaten.")
    _zuordnung_anlegen(db, dok, article_id=a.id)
    db.commit()
    log_action(db, user, "zuordnen_dokument", "article", a.id, {"dokument_id": dok.id})
    return {"ok": True}
