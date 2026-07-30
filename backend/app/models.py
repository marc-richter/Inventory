import enum
import datetime as dt
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.orm import relationship
from .database import Base


def now():
    return dt.datetime.utcnow()


class Role(str, enum.Enum):
    admin = "admin"          # voller Zugriff, Benutzerverwaltung, Einstellungen
    verwalter = "verwalter"  # Artikel anlegen/bearbeiten, Aus-/Rueckgabe, Auswertungen
    helfer = "helfer"        # nur Aus-/Rueckgabe, Uebersicht
    lesend = "lesend"        # nur lesender Zugriff (z.B. Vorstand)
    eigen = "eigen"          # geringste Rechte (Selbstregistrierung): nur eigene Artikel


class ArticleStatus(str, enum.Enum):
    verfuegbar = "verfuegbar"
    ausgegeben = "ausgegeben"
    reparatur = "reparatur"
    ausgemustert = "ausgemustert"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    full_name = Column(String(128), default="")
    roles = Column(JSON, default=lambda: [Role.helfer.value], nullable=False)
    password_hash = Column(String(256), nullable=True)
    pin_hash = Column(String(256), nullable=True)
    pin_length = Column(Integer, default=4, nullable=False)
    must_change_pin = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True)
    created_at = Column(DateTime, default=now)
    last_seen = Column(DateTime, nullable=True)   # fuer Online-Nutzer-Anzeige
    # Telegram-Selbstverknuepfung: verknuepfte Chat-ID und ein temporaerer Code,
    # den der Nutzer dem Bot per /link schickt.
    telegram_chat_id = Column(String(32), nullable=True)
    telegram_link_code = Column(String(16), nullable=True)

    issues = relationship("IssueRecord", back_populates="issued_by", foreign_keys="IssueRecord.issued_by_user_id")
    person = relationship("Person", foreign_keys=[person_id])

    def has_role(self, *roles) -> bool:
        mine = self.roles or []
        return any((r.value if hasattr(r, "value") else r) in mine for r in roles)


class Category(Base):
    """Oberkategorie, z.B. 'Kleidung'. Spaeter erweiterbar um weitere Kategorien."""
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, nullable=False)
    created_at = Column(DateTime, default=now)

    types = relationship("ArticleType", back_populates="category")


class ArticleType(Base):
    """Typ innerhalb einer Kategorie, z.B. 'T-Shirt', 'Hose'. Frei erweiterbar."""
    __tablename__ = "article_types"
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    name = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=now)

    category = relationship("Category", back_populates="types")


class Organization(Base):
    """Abteilung, z.B. 'Abteilung 01', 'Abteilung 02'. Frei erweiterbar."""
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, nullable=False)
    created_at = Column(DateTime, default=now)


class StorageLocation(Base):
    """Standort (oberste Ebene eines Lagerorts), z.B. 'Feuerwache Mitte'. Traegt
    optional eine Adresse und Kontaktdaten (z.B. fuer Reparaturwerkstaetten). Die
    feineren Ebenen (Etage/Raum/Schrank/Fach) stehen als Freitext am Artikel."""
    __tablename__ = "storage_locations"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True, nullable=False)
    address = Column(Text, default="")
    contact_name = Column(String(128), default="")
    contact_phone = Column(String(64), default="")
    contact_fax = Column(String(64), default="")
    contact_email = Column(String(128), default="")
    # True fuer aus einer aelteren Version uebernommene Lagerorte, die der Admin noch
    # einer Ebene zuordnen soll (Standort/Etage/Raum/Schrank/Fach).
    needs_review = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=now)


class StorageNode(Base):
    """Fest verwalteter Lagerort-Knoten in einem Baum. level ist eine der festen
    Ebenen (standort/etage/raum/schrank/fach). Ein Standort ist ein Wurzelknoten
    (parent_id=None, level='standort'); darunter beliebig tiefe Unterknoten. Jeder
    Knoten kann Adresse/Kontakt tragen (v.a. der Standort). Artikel verweisen mit
    storage_node_id auf ihren (Blatt-)Knoten."""
    __tablename__ = "storage_nodes"
    LEVELS = ["standort", "etage", "raum", "schrank", "fach"]
    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("storage_nodes.id"), nullable=True, index=True)
    level = Column(String(16), default="standort", nullable=False)
    name = Column(String(128), nullable=False)
    address = Column(Text, default="")
    contact_name = Column(String(128), default="")
    contact_phone = Column(String(64), default="")
    contact_fax = Column(String(64), default="")
    contact_email = Column(String(128), default="")
    sort_order = Column(Integer, default=100)
    created_at = Column(DateTime, default=now)

    parent = relationship("StorageNode", remote_side=[id], backref="children")


class InventoryCampaign(Base):
    """Eine Inventur als eigenstaendiges Objekt. Muss keinen Startzeitpunkt haben.
    scope_type: 'full' (alles), 'nodes' (nur bestimmte Standort-Teilbaeume),
    'categories' (nur bestimmte Klassen, z.B. Kleidung). status steuert den
    Lebenszyklus: geplant -> laufend <-> pausiert -> abgeschlossen/abgesagt."""
    __tablename__ = "inventory_campaigns"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    scope_type = Column(String(16), default="full", nullable=False)
    status = Column(String(16), default="planned", nullable=False)  # planned/running/paused/done/cancelled
    ignore_status = Column(Text, default="ausgegeben,reparatur,ausgemustert")
    planned_start = Column(DateTime, nullable=True)
    planned_end = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    notes = Column(Text, default="")
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    created_by = relationship("User", foreign_keys=[created_by_id])
    scope_nodes = relationship("InventoryScopeNode", cascade="all, delete-orphan", backref="campaign")
    scope_categories = relationship("InventoryScopeCategory", cascade="all, delete-orphan", backref="campaign")
    participants = relationship("InventoryParticipant", cascade="all, delete-orphan", backref="campaign")
    found = relationship("InventoryFound", cascade="all, delete-orphan", backref="campaign")


class InventoryScopeNode(Base):
    __tablename__ = "inventory_scope_nodes"
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("inventory_campaigns.id"), nullable=False, index=True)
    node_id = Column(Integer, ForeignKey("storage_nodes.id"), nullable=False)


class InventoryScopeCategory(Base):
    __tablename__ = "inventory_scope_categories"
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("inventory_campaigns.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)


class InventoryParticipant(Base):
    """Teilnehmer einer Inventur. role='lead' darf verwalten und weitere Personen
    freischalten; role='helper' darf nur scannen/zuordnen. Die Teilnahme gewaehrt
    die Inventur-Rechte fuer GENAU diese Kampagne, auch ohne globales Recht."""
    __tablename__ = "inventory_participants"
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("inventory_campaigns.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(16), default="helper", nullable=False)
    created_at = Column(DateTime, default=now)

    user = relationship("User", foreign_keys=[user_id])


class InventoryFound(Base):
    """Ein bei einer Kampagne erfasster ("gefundener") Artikel."""
    __tablename__ = "inventory_found"
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("inventory_campaigns.id"), nullable=False, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    node_id = Column(Integer, ForeignKey("storage_nodes.id"), nullable=True)
    found_at = Column(DateTime, default=now)
    found_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)


class StatusDef(Base):
    """Konfigurierbarer Artikel-Status. Eingebaute Status (verfuegbar, ausgegeben,
    reparatur, ausgemustert) sind is_builtin=True und nicht loeschbar. Weitere
    Status (z.B. 'zu waschen', 'beschaedigt', 'infektioes') lassen sich im
    Stammdaten-Menue anlegen, aendern und entfernen. Ueber category_ids laesst
    sich festlegen, fuer welche Artikelklassen (Kategorien) ein Status gilt -
    eine leere Liste bedeutet: fuer alle Klassen."""
    __tablename__ = "status_defs"
    id = Column(Integer, primary_key=True)
    key = Column(String(48), unique=True, nullable=False)   # Slug, z.B. "zu_waschen"
    label = Column(String(64), nullable=False)              # Anzeigename
    sort_order = Column(Integer, default=100)
    is_builtin = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    category_ids = Column(JSON, default=list)               # leer = alle Klassen
    # Beim Setzen dieses Status ist eine Beschreibung (Freitext) Pflicht - z.B.
    # bei "Beschädigt" die Art der Beschaedigung. allow_image bietet beim
    # Statuswechsel zusaetzlich einen optionalen Bild-Anhang an (z.B. Schadensbild).
    require_note = Column(Boolean, default=False)
    allow_image = Column(Boolean, default=False)
    # Ausgabe-Regel fuer Artikel, die AKTUELL in diesem Status sind:
    #   "direct"  = direkt ausgebbar (z.B. Verfügbar)
    #   "confirm" = nur nach Rueckfrage/Bestaetigung ausgebbar (z.B. Reparatur)
    #   "blocked" = gesperrt; erst Status zuruecknehmen (z.B. Ausgemustert)
    issue_policy = Column(String(16), default="confirm", nullable=False)
    created_at = Column(DateTime, default=now)


class Person(Base):
    """Empfaenger / Mitglied, an den Artikel ausgegeben werden."""
    __tablename__ = "persons"
    id = Column(Integer, primary_key=True)
    first_name = Column(String(64), nullable=False)
    last_name = Column(String(64), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    notes = Column(Text, default="")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now)

    organization = relationship("Organization")


class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True)
    artikelnummer = Column(String(64), unique=True, nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    type_id = Column(Integer, ForeignKey("article_types.id"), nullable=False)
    size = Column(String(32), default="")
    model = Column(String(64), default="")       # Modell (weitere Untergliederung des Typs)
    properties = Column(Text, default="")        # weitere Eigenschaften (Freitext)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    storage_location_id = Column(Integer, ForeignKey("storage_locations.id"), nullable=True)
    # Fest verwalteter Lagerort-Knoten (Baum). Loest schrittweise die Freitext-
    # Ebenen unten ab; ist er gesetzt, hat er Vorrang bei der Pfad-Anzeige.
    storage_node_id = Column(Integer, ForeignKey("storage_nodes.id"), nullable=True)
    # Feinere Lagerort-Ebenen (Freitext, jede optional). "Etage" kann auch eine
    # Garage sein, "Raum" ein Auto usw.
    etage = Column(String(64), default="")
    raum = Column(String(64), default="")
    schrank = Column(String(64), default="")
    fach = Column(String(64), default="")
    # Aktueller Standort: bei Ausgabe automatisch der Name der Empfaenger-Person.
    # Der stammdaten-Lagerort (storage_location_id) bleibt als Rueckgabeort erhalten.
    current_location = Column(String(128), default="")
    status = Column(String(32), default=ArticleStatus.verfuegbar.value, nullable=False)
    condition_notes = Column(Text, default="")   # Beschaedigungen
    remarks = Column(Text, default="")           # Bemerkungen
    repair_expected_return = Column(DateTime, nullable=True)  # voraussichtl. Rueckdatum bei Reparatur
    repair_reason = Column(Text, default="")                  # Grund der Reparatur
    retire_reason = Column(Text, default="")                  # Grund beim Aussondern (ausgemustert)
    # Vorlaeufige Inventarisierung (z.B. schnell bei der Ausgabe angelegt, noch nicht
    # von einem Berechtigten geprueft). provisional=True bis zur Genehmigung.
    provisional = Column(Boolean, default=False, nullable=False)
    provisional_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Zeitpunkt der letzten Inventur-Erfassung (Scan/Zuordnung). Waehrend einer
    # laufenden Inventur gilt ein Artikel als "gefunden", wenn dieser Wert nach dem
    # Kampagnen-Start liegt; alles andere landet auf der offenen/fehlenden Liste.
    last_inventoried_at = Column(DateTime, nullable=True)
    first_entry_date = Column(DateTime, default=now)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    category = relationship("Category")
    type = relationship("ArticleType")
    organization = relationship("Organization")
    storage_location = relationship("StorageLocation")
    storage_node = relationship("StorageNode", foreign_keys=[storage_node_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    provisional_by = relationship("User", foreign_keys=[provisional_by_id])
    review_assignee = relationship("User", foreign_keys=[review_assignee_id])
    images = relationship("ArticleImage", back_populates="article", cascade="all, delete-orphan")
    issues = relationship("IssueRecord", back_populates="article", cascade="all, delete-orphan", order_by="desc(IssueRecord.issue_date)")

    @property
    def created_by_name(self):
        if self.created_by:
            return self.created_by.full_name or self.created_by.username
        return None

    @property
    def provisional_by_name(self):
        if self.provisional_by:
            return self.provisional_by.full_name or self.provisional_by.username
        return None

    @property
    def review_assignee_name(self):
        if self.review_assignee:
            return self.review_assignee.full_name or self.review_assignee.username
        return None

    @property
    def location_path(self):
        """Lesbarer Lagerort-Pfad. Bevorzugt den verwalteten Knoten-Baum; faellt
        sonst auf Standort + Freitext-Ebenen zurueck."""
        node = self.storage_node
        if node is not None:
            parts, seen = [], set()
            while node is not None and node.id not in seen:
                seen.add(node.id)
                parts.append(node.name)
                node = node.parent
            return " › ".join(reversed(parts))
        base = self.storage_location.name if self.storage_location else ""
        subs = [s for s in (self.etage, self.raum, self.schrank, self.fach) if s]
        return " › ".join([p for p in ([base] + subs) if p])


class ArticleImage(Base):
    __tablename__ = "article_images"
    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    filepath = Column(String(256), nullable=False)
    # "normal" = frei loeschbar/ersetzbar; "damage" = Dokumentationsbild (z.B.
    # Beschaedigung/Verschmutzung), das aus Nachweisgruenden NICHT loeschbar ist.
    kind = Column(String(16), default="normal", nullable=False)
    uploaded_at = Column(DateTime, default=now)

    article = relationship("Article", back_populates="images")


class IssueRecord(Base):
    """Ein Ausgabe-/Ruecknahme-Vorgang. Bildet den Verlauf eines Artikels ab."""
    __tablename__ = "issue_records"
    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True)
    recipient_name_freetext = Column(String(128), default="")
    issue_date = Column(DateTime, default=now)
    return_date = Column(DateTime, nullable=True)
    condition_at_return = Column(Text, default="")
    notes = Column(Text, default="")
    issued_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    returned_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    article = relationship("Article", back_populates="issues")
    person = relationship("Person")
    issued_by = relationship("User", foreign_keys=[issued_by_user_id], back_populates="issues")
    returned_by = relationship("User", foreign_keys=[returned_by_user_id])


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(64), default="")
    action = Column(String(64), nullable=False)
    entity_type = Column(String(64), default="")
    entity_id = Column(Integer, nullable=True)
    details = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=now)


class Setting(Base):
    """Generischer Key-Value Speicher fuer Einstellungen."""
    __tablename__ = "settings"
    key = Column(String(64), primary_key=True)
    value = Column(Text, default="")


class BackupRecord(Base):
    __tablename__ = "backup_records"
    id = Column(Integer, primary_key=True)
    filename = Column(String(256), nullable=False)
    kind = Column(String(16), default="manual")  # manual / auto
    size_bytes = Column(Integer, default=0)
    created_at = Column(DateTime, default=now)
