"""Wasserzeichen verwalten: Katalog, eigene Motive hochladen, Vorschau.

Die hochgeladenen Motive liegen im Branding-Ordner und sind eine gemeinsame
Sammlung: einmal hochladen, danach bei jeder Vorlage und jedem Lagerort
auswaehlbar. Eine Datei je Vorlage waere dieselbe Grafik zehnmal auf der Platte
und zehnmal zu pflegen.
"""
import io
import os
import re
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from reportlab.lib.pagesizes import A4, landscape
from sqlalchemy.orm import Session

from app import models, security, wasserzeichen
from app.audit import log_action
from app.config import BRANDING_DIR
from app.database import get_db

router = APIRouter(prefix="/api/v1/wasserzeichen", tags=["wasserzeichen"])

MAX_BYTES = 10 * 1024 * 1024


def _sicherer_name(name: str) -> str:
    stamm = os.path.splitext(os.path.basename(name or ""))[0]
    stamm = re.sub(r"[^A-Za-z0-9_-]+", "_", stamm).strip("_").lower()
    return stamm[:40] or "motiv"


@router.get("")
def katalog(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Alles, was sich auswaehlen laesst - mitgelieferte Motive und eigene Dateien."""
    return {
        "motive": wasserzeichen.MOTIVE,
        "positionen": wasserzeichen.POSITIONEN,
        "eigene": wasserzeichen.eigene_dateien(),
        "standard": wasserzeichen.STANDARD,
        "hinweis": ("Monochrom heißt: eine Farbe, frei wählbar. Ein mehrfarbiges Bild "
                    "hinter einer Tabelle macht die Zahlen unleserlich, und auf einem "
                    "Schwarzweißdrucker wird ohnehin ein grauer Fleck daraus."),
    }


@router.post("")
async def hochladen(file: UploadFile = File(...), db: Session = Depends(get_db),
                    user=Depends(security.require_roles("admin"))):
    """Eigenes Motiv hochladen. Beim Zeichnen wird es auf eine Farbe reduziert:
    dunkle Stellen werden zur Zeichnung, helle verschwinden."""
    inhalt = await file.read()
    if not inhalt:
        raise HTTPException(status_code=400, detail="Datei ist leer")
    if len(inhalt) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="Datei ist zu groß (max. 10 MB)")
    endung = os.path.splitext(file.filename or "")[1].lower()
    if endung not in wasserzeichen.ERLAUBTE_ENDUNGEN:
        erlaubt = ", ".join(sorted(wasserzeichen.ERLAUBTE_ENDUNGEN))
        raise HTTPException(status_code=400, detail=f"Nur Bilddateien erlaubt ({erlaubt})")
    try:
        from PIL import Image
        Image.open(io.BytesIO(inhalt)).verify()
    except Exception:
        raise HTTPException(status_code=400, detail="Die Datei ist kein lesbares Bild")

    name = f"{wasserzeichen.DATEI_VORSATZ}{_sicherer_name(file.filename)}_{uuid.uuid4().hex[:6]}{endung}"
    try:
        BRANDING_DIR.mkdir(parents=True, exist_ok=True)
        (BRANDING_DIR / name).write_bytes(inhalt)
    except OSError:
        raise HTTPException(status_code=500, detail="Ablage fehlgeschlagen")
    log_action(db, user, "watermark_upload", "watermark", None, {"datei": name})
    return {"datei": name, "eigene": wasserzeichen.eigene_dateien()}


@router.delete("/{datei}")
def loeschen(datei: str, db: Session = Depends(get_db),
             user=Depends(security.require_roles("admin"))):
    """Eigenes Motiv entfernen. Vorlagen und Lagerorte, die darauf zeigen,
    werden mit zurueckgesetzt - sonst bliebe ein Verweis ins Leere stehen."""
    name = os.path.basename(datei)
    if not name.startswith(wasserzeichen.DATEI_VORSATZ):
        raise HTTPException(status_code=400, detail="Kein eigenes Wasserzeichen")
    pfad = BRANDING_DIR / name
    if pfad.exists():
        try:
            pfad.unlink()
        except OSError:
            raise HTTPException(status_code=500, detail="Löschen fehlgeschlagen")
    for klasse in (models.DocTemplate, models.StorageNode):
        for zeile in db.query(klasse).all():
            marke = zeile.watermark or {}
            if isinstance(marke, dict) and marke.get("datei") == name:
                zeile.watermark = {}
    db.commit()
    log_action(db, user, "watermark_delete", "watermark", None, {"datei": name})
    return {"ok": True, "eigene": wasserzeichen.eigene_dateien()}


@router.get("/bild/{datei}")
def bild(datei: str, user=Depends(security.get_current_user)):
    name = os.path.basename(datei)
    pfad = BRANDING_DIR / name
    if not name.startswith(wasserzeichen.DATEI_VORSATZ) or not pfad.exists():
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    return FileResponse(pfad)


@router.get("/vorschau")
def vorschau(art: str = "motiv", motiv: str = "blutstropfen", datei: str = "",
             farbe: str = "#999999", deckkraft: int = 10, groesse_mm: float = 120,
             drehung: float = 0, position: str = "mitte", quer: bool = False,
             user=Depends(security.get_current_user)):
    """Eine leere Seite nur mit dem Wasserzeichen - zum Prüfen von Farbe,
    Deckkraft und Größe, bevor 30 Listen damit gedruckt werden."""
    daten = {"art": art, "motiv": motiv, "datei": datei, "farbe": farbe,
             "deckkraft": deckkraft, "groesse_mm": groesse_mm, "drehung": drehung,
             "position": position}
    seite = landscape(A4) if quer else A4
    roh = wasserzeichen.seite_pdf(daten, seite[0], seite[1])
    return Response(content=roh, media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="wasserzeichen.pdf"'})
