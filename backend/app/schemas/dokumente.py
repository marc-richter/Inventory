import datetime as dt
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class DokumentUpdate(BaseModel):
    title: Optional[str] = None
    art: Optional[str] = None
    stand: Optional[str] = None
    note: Optional[str] = None
    active: Optional[bool] = None


class DokumentZuordnung(BaseModel):
    """Wo ein Dokument gilt. Genau eines der drei Felder wird gesetzt."""
    category_id: Optional[int] = None
    type_id: Optional[int] = None
    article_id: Optional[int] = None


class DokumentZuordnungenSet(BaseModel):
    """Die vollstaendige Liste der Klassen und Typen, an denen ein Dokument haengt.
    Artikel-Zuordnungen bleiben davon unberuehrt - die werden am Artikel gepflegt."""
    category_ids: List[int] = []
    type_ids: List[int] = []


class ZuordnungOut(BaseModel):
    id: int
    ebene: str            # "klasse" | "typ" | "artikel"
    ziel_id: int
    ziel_name: str


class DokumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    art: str
    art_label: str = ""
    symbol: str = ""
    original_name: str = ""
    size_bytes: int = 0
    stand: str = ""
    note: str = ""
    zentral: bool = True
    active: bool = True
    uploaded_at: Optional[dt.datetime] = None
    uploaded_by_name: str = ""
    zuordnungen: List[ZuordnungOut] = []
    # Zahl der Artikel, fuer die dieses Dokument (ueber alle Ebenen) gilt.
    artikel_anzahl: int = 0


class ArtikelDokumentOut(BaseModel):
    """Ein am Artikel geltendes Dokument - mit der Angabe, woher es kommt."""
    id: int
    title: str
    art: str
    art_label: str = ""
    symbol: str = ""
    original_name: str = ""
    size_bytes: int = 0
    stand: str = ""
    note: str = ""
    zentral: bool = True
    # "klasse" | "typ" | "artikel"
    herkunft: str
    herkunft_name: str = ""
    # Nur bei herkunft="artikel" gesetzt: die Zuordnung laesst sich hier loesen.
    link_id: Optional[int] = None
