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
    # Persoenlich entzogene Rechte (unabhaengig von der Rolle) – z.B. bei Missbrauch.
    revoked_capabilities = Column(JSON, default=list)
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
    # Persoenliche Vorlaufzeit (Tage) fuer Inventur-Erinnerungen. NULL = den in der
    # jeweiligen Inventur hinterlegten Standardwert verwenden.
    reminder_days_before = Column(Integer, nullable=True)

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
    # Standard, ob Artikel dieser Klasse ausgegeben/persoenlich zugeordnet werden
    # koennen. Einzelartikel koennen das ueberschreiben (Article.issuable_override).
    issuable_default = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=now)

    types = relationship("ArticleType", back_populates="category")


class ArticleType(Base):
    """Typ innerhalb einer Kategorie, z.B. 'T-Shirt', 'Hose'. Frei erweiterbar."""
    __tablename__ = "article_types"
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    name = Column(String(64), nullable=False)
    # Mindestbestand (Anzahl verfuegbarer Stueck). 0 = aus (keine Warnung) - so ist
    # die Funktion standardmaessig deaktiviert, auch fuer Kleidung.
    min_stock = Column(Integer, default=0, nullable=False)
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


class UserGroup(Base):
    """Frei definierbare Funktionsgruppe/-rolle (z.B. 'Materialwart', 'Abteilung JRK').
    Dient der Aufgabenzuteilung und – spaeter – der gezielten Benachrichtigung.
    Unabhaengig von den Berechtigungs-Rollen (admin/verwalter/…)."""
    __tablename__ = "user_groups"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=now)


class UserGroupMember(Base):
    __tablename__ = "user_group_members"
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("user_groups.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=now)


class StorageNode(Base):
    """Fest verwalteter Lagerort-Knoten in einem Baum. level ist eine der festen
    Ebenen (standort/etage/raum/schrank/fach). Ein Standort ist ein Wurzelknoten
    (parent_id=None, level='standort'); darunter beliebig tiefe Unterknoten. Jeder
    Knoten kann Adresse/Kontakt tragen (v.a. der Standort). Artikel verweisen mit
    storage_node_id auf ihren (Blatt-)Knoten."""
    __tablename__ = "storage_nodes"
    LEVELS = ["standort", "etage", "raum", "schrank", "fach", "tasche"]
    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("storage_nodes.id"), nullable=True, index=True)
    level = Column(String(16), default="standort", nullable=False)
    name = Column(String(128), nullable=False)
    # Freitext-Beschreibung / Inhalts-Kurzuebersicht des Lagerorts (alle Ebenen).
    description = Column(Text, default="")
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
    # Standard-Vorlaufzeit (Tage) fuer die Erinnerung vor dieser Inventur.
    reminder_days_before = Column(Integer, default=3)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    created_by = relationship("User", foreign_keys=[created_by_id])
    scope_nodes = relationship("InventoryScopeNode", cascade="all, delete-orphan", backref="campaign")
    scope_categories = relationship("InventoryScopeCategory", cascade="all, delete-orphan", backref="campaign")
    participants = relationship("InventoryParticipant", cascade="all, delete-orphan", backref="campaign")
    found = relationship("InventoryFound", cascade="all, delete-orphan", backref="campaign")
    steps = relationship("InventoryStep", order_by="InventoryStep.position",
                         cascade="all, delete-orphan", backref="campaign")


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


class InventoryStep(Base):
    """Eine geordnete Station ("Rundgang-Schritt") einer geführten Inventur.
    Meist an einen Standort-Knoten gebunden (node_id); die Reihenfolge ergibt
    sich aus position. status fuehrt den Nutzer: pending -> done/skipped."""
    __tablename__ = "inventory_steps"
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("inventory_campaigns.id"), nullable=False, index=True)
    position = Column(Integer, default=0, nullable=False)
    node_id = Column(Integer, ForeignKey("storage_nodes.id"), nullable=True)
    label = Column(String(160), default="")
    status = Column(String(16), default="pending", nullable=False)  # pending/done/skipped
    note = Column(Text, default="")
    done_at = Column(DateTime, nullable=True)
    done_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    node = relationship("StorageNode", foreign_keys=[node_id])
    done_by = relationship("User", foreign_keys=[done_by_id])


class InventoryTemplate(Base):
    """Wiederverwendbare Rundgang-Vorlage: geordnete Stationen + Einstellungen.
    Vorlagen lassen sich beim Anlegen einer Inventur einzeln oder kombiniert
    verwenden (Stationen werden zusammengefuehrt)."""
    __tablename__ = "inventory_templates"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    ignore_status = Column(Text, default="ausgegeben,reparatur,ausgemustert")
    notes = Column(Text, default="")
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    created_by = relationship("User", foreign_keys=[created_by_id])
    steps = relationship("InventoryTemplateStep",
                         order_by="InventoryTemplateStep.position",
                         cascade="all, delete-orphan", backref="template")


class InventoryTemplateStep(Base):
    __tablename__ = "inventory_template_steps"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("inventory_templates.id"), nullable=False, index=True)
    position = Column(Integer, default=0, nullable=False)
    node_id = Column(Integer, ForeignKey("storage_nodes.id"), nullable=True)
    label = Column(String(160), default="")

    node = relationship("StorageNode", foreign_keys=[node_id])


class InventorySchedule(Base):
    """Wiederkehrender Termin, der automatisch eine Inventur-Kampagne erzeugt.
    unit/interval bilden die Kadenz (z.B. alle 3 Monate). next_run ist der
    naechste Faelligkeitstermin; der Scheduler materialisiert faellige Plaene."""
    __tablename__ = "inventory_schedules"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    interval = Column(Integer, default=1, nullable=False)
    unit = Column(String(16), default="month", nullable=False)  # day/week/month/month_weekday
    # Nur fuer unit="month_weekday": weekday 0=Mo..6=So; week_of_month 1..4 bzw. 5=letzter.
    weekday = Column(Integer, nullable=True)
    week_of_month = Column(Integer, nullable=True)
    next_run = Column(DateTime, nullable=True)
    last_run = Column(DateTime, nullable=True)
    ignore_status = Column(Text, default="ausgegeben,reparatur,ausgemustert")
    notes = Column(Text, default="")
    # Standard-Vorlaufzeit (Tage) fuer die Erinnerung; wird auf erzeugte Kampagnen
    # uebernommen. ics_sent: ob die (einzelne) Serientermin-ICS schon verschickt wurde.
    reminder_days_before = Column(Integer, default=3)
    ics_sent = Column(Boolean, default=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now)

    created_by = relationship("User", foreign_keys=[created_by_id])
    templates = relationship("InventoryScheduleTemplate",
                             cascade="all, delete-orphan", backref="schedule")
    schedule_participants = relationship("InventoryScheduleParticipant",
                                         cascade="all, delete-orphan", backref="schedule")


class InventoryScheduleTemplate(Base):
    __tablename__ = "inventory_schedule_templates"
    id = Column(Integer, primary_key=True)
    schedule_id = Column(Integer, ForeignKey("inventory_schedules.id"), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey("inventory_templates.id"), nullable=False)
    position = Column(Integer, default=0)

    template = relationship("InventoryTemplate", foreign_keys=[template_id])


class InventoryScheduleParticipant(Base):
    __tablename__ = "inventory_schedule_participants"
    id = Column(Integer, primary_key=True)
    schedule_id = Column(Integer, ForeignKey("inventory_schedules.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(16), default="helper")

    user = relationship("User", foreign_keys=[user_id])


class InventoryReportArchive(Base):
    """Archivierter Abschlussbericht einer Inventur. Haelt einen unveraenderlichen
    Snapshot (JSON) der Kennzahlen und Listen sowie den Dateinamen der abgelegten
    PDF, damit vergangene Inventuren jederzeit online eingesehen werden koennen -
    unabhaengig davon, ob sich der Bestand spaeter aendert oder die Kampagne
    geloescht wird."""
    __tablename__ = "inventory_report_archives"
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, nullable=True, index=True)   # bewusst ohne FK/Cascade
    campaign_name = Column(String(128), default="")
    created_at = Column(DateTime, default=now)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    stats = Column(JSON, default=dict)      # erwartet/gefunden/offen/ignoriert
    data = Column(JSON, default=dict)       # {meta, found, missing, ignored}
    pdf_filename = Column(String(200), default="")

    created_by = relationship("User", foreign_keys=[created_by_id])


class InventoryReminderLog(Base):
    """Merkt, an welchen Chat fuer welche Kampagne bereits eine Vor-Erinnerung
    verschickt wurde - damit jede Person genau eine Erinnerung erhaelt."""
    __tablename__ = "inventory_reminder_log"
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("inventory_campaigns.id"), nullable=False, index=True)
    chat_id = Column(String(32), nullable=False)
    sent_at = Column(DateTime, default=now)


class MaterialManager(Base):
    """Zustaendigkeit eines Nutzers als Materialverwalter. organization_id/category_id
    NULL bedeutet jeweils "alle". Steuert Zugriff auf die Auswertung und schraenkt die
    dort gezeigten Daten auf die eigene Abteilung/Materialklasse ein."""
    __tablename__ = "material_managers"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization", foreign_keys=[organization_id])
    category = relationship("Category", foreign_keys=[category_id])


class MinStockRule(Base):
    """Mindestbestand-Regel. Basis: type_id (+ optionale Groesse) ueber den gesamten
    Bestand (node_id NULL). Optional als Ueberschreibung fuer einen Lagerplatz beliebiger
    Stufe (node_id gesetzt -> gilt fuer diesen Knoten samt Unterebenen). `notified`
    verhindert wiederholte Benachrichtigungen, solange die Unterschreitung anhaelt."""
    __tablename__ = "min_stock_rules"
    id = Column(Integer, primary_key=True)
    type_id = Column(Integer, ForeignKey("article_types.id"), nullable=False, index=True)
    size = Column(String(32), default="")            # "" = alle Groessen
    node_id = Column(Integer, ForeignKey("storage_nodes.id"), nullable=True)
    min_stock = Column(Integer, default=0, nullable=False)
    notified = Column(Boolean, default=False, nullable=False)

    type = relationship("ArticleType", foreign_keys=[type_id])
    node = relationship("StorageNode", foreign_keys=[node_id])


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
    # Groessenprofil: frei verwaltbare Groessenarten (SizeField). Werte als Map
    # {size_field_id (str): Wert}. Die alten festen Spalten bleiben aus
    # Kompatibilitaetsgruenden erhalten, werden aber nicht mehr genutzt.
    size_top = Column(String(32), default="")
    size_bottom = Column(String(32), default="")
    size_shoes = Column(String(32), default="")
    size_head = Column(String(32), default="")
    size_gloves = Column(String(32), default="")
    sizes = Column(JSON, default=dict)
    created_at = Column(DateTime, default=now)

    organization = relationship("Organization")


class Receipt(Base):
    """Abgelegte Ausgabe-/Rueckgabe-Quittung. Die (unterschriebene) Datei liegt im
    RECEIPTS_DIR; ueber person_id und issued_by_user_id ist sie sowohl beim Empfaenger
    als auch bei der ausgebenden Person auffindbar."""
    __tablename__ = "receipts"
    id = Column(Integer, primary_key=True)
    kind = Column(String(16), default="issue")   # issue | return
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True, index=True)
    issued_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    filename = Column(String(200), default="")
    note = Column(Text, default="")
    signed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)

    person = relationship("Person", foreign_keys=[person_id])
    issued_by = relationship("User", foreign_keys=[issued_by_user_id])


class MaterialRequest(Base):
    """Reservierung/Anfrage eines Nutzers nach Material (Typ + Groesse + Menge, ohne
    Bestandssperre). Erscheint bei den zustaendigen Materialverwaltern als Aufgabe."""
    __tablename__ = "material_requests"
    id = Column(Integer, primary_key=True)
    requester_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type_id = Column(Integer, ForeignKey("article_types.id"), nullable=True)
    size = Column(String(32), default="")
    quantity = Column(Integer, default=1)
    desired_from = Column(DateTime, nullable=True)
    desired_until = Column(DateTime, nullable=True)
    note = Column(Text, default="")
    status = Column(String(16), default="open", nullable=False)   # open/approved/rejected/done
    handled_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    handled_at = Column(DateTime, nullable=True)
    decision_note = Column(Text, default="")
    created_at = Column(DateTime, default=now)

    requester = relationship("User", foreign_keys=[requester_user_id])
    type = relationship("ArticleType", foreign_keys=[type_id])
    handled_by = relationship("User", foreign_keys=[handled_by_user_id])


class InspectionChecklist(Base):
    """Vom Admin definierte Prüf-Checkliste (mehrere möglich)."""
    __tablename__ = "inspection_checklists"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=now)
    items = relationship("InspectionChecklistItem", order_by="InspectionChecklistItem.position",
                         cascade="all, delete-orphan", backref="checklist")


class InspectionChecklistItem(Base):
    __tablename__ = "inspection_checklist_items"
    id = Column(Integer, primary_key=True)
    checklist_id = Column(Integer, ForeignKey("inspection_checklists.id"), nullable=False, index=True)
    position = Column(Integer, default=0)
    label = Column(String(200), nullable=False)


class InspectionRule(Base):
    """Prüfregel je Artikeltyp: ein Auslöser (Rückgabe / X Ausleihen / X Wäschen /
    X Monate) mit zugeordneter Checkliste. Mehrere Regeln je Typ moeglich."""
    __tablename__ = "inspection_rules"
    id = Column(Integer, primary_key=True)
    type_id = Column(Integer, ForeignKey("article_types.id"), nullable=False, index=True)
    # Ist article_id gesetzt, gilt die Regel nur für diesen Einzelartikel (Override);
    # sonst (NULL) ist es eine Typ-Regel. type_id bleibt der Übersicht halber gefüllt.
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True, index=True)
    trigger = Column(String(16), default="return")   # return | loans | washes | months | return_once
    threshold = Column(Integer, default=1)
    checklist_id = Column(Integer, ForeignKey("inspection_checklists.id"), nullable=True)

    type = relationship("ArticleType", foreign_keys=[type_id])
    checklist = relationship("InspectionChecklist", foreign_keys=[checklist_id])


class Inspection(Base):
    """Ein Prüfvorgang zu einem Artikel: Checkliste abarbeiten, pausieren, abschließen.
    Beim Abschluss uebernimmt die Person die Verantwortung; das Ergebnis bestimmt den
    Folgestatus des Artikels."""
    __tablename__ = "inspections"
    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    checklist_id = Column(Integer, nullable=True)
    checklist_name = Column(String(128), default="")
    status = Column(String(16), default="open", nullable=False)   # open/paused/done
    result = Column(String(16), default="")                        # passed/failed
    overall_note = Column(Text, default="")
    document_filename = Column(String(200), default="")
    started_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    finished_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    started_at = Column(DateTime, default=now)
    finished_at = Column(DateTime, nullable=True)

    article = relationship("Article", foreign_keys=[article_id])
    started_by = relationship("User", foreign_keys=[started_by_id])
    finished_by = relationship("User", foreign_keys=[finished_by_id])
    results = relationship("InspectionItemResult", order_by="InspectionItemResult.position",
                           cascade="all, delete-orphan", backref="inspection")


class InspectionItemResult(Base):
    __tablename__ = "inspection_item_results"
    id = Column(Integer, primary_key=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id"), nullable=False, index=True)
    position = Column(Integer, default=0)
    label = Column(String(200), default="")     # Snapshot des Prüfpunkts
    ok = Column(Boolean, nullable=True)          # None = offen, True/False = Ergebnis
    note = Column(Text, default="")


class DamageLossReport(Base):
    """Schadens- oder Verlustmeldung zu einem Artikel. Erzeugt beim Anlegen einen
    automatischen Statuswechsel (Schaden→Reparatur, Verlust→verschollen), eine
    Aufgabe im Eingang der Materialverantwortlichen und eine PDF-Meldung; die
    Verantwortlichen werden per Telegram (inkl. PDF) benachrichtigt."""
    __tablename__ = "damage_loss_reports"
    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    kind = Column(String(8), default="damage", nullable=False)   # damage | loss
    reporter_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    description = Column(Text, default="")                        # Hergang / Umstände (Pflicht)
    photo_filename = Column(String(200), default="")
    # Versicherungs-/polizeitaugliche Angaben:
    incident_at = Column(DateTime, nullable=True)                 # Datum/Uhrzeit des Vorfalls (Pflicht)
    incident_location = Column(String(200), default="")           # Ort des Vorfalls / zuletzt gesehen (Pflicht)
    is_theft = Column(Boolean, default=False, nullable=False)     # Diebstahl (nur Verlust)
    police_reference = Column(String(200), default="")            # Polizei-Aktenzeichen/Dienststelle (nachträglich)
    estimated_value = Column(String(64), default="")              # Zeit-/Neuwert bzw. Schadenshöhe (nachträglich)
    witnesses = Column(Text, default="")                          # Zeugen (optional)
    reporter_contact = Column(String(200), default="")            # Rückfrage-Kontakt des Melders
    complete = Column(Boolean, default=False, nullable=False, index=True)  # alle Pflichtangaben vorhanden
    status = Column(String(16), default="open", nullable=False)  # open | done
    handled_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    handled_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, default="")
    created_at = Column(DateTime, default=now)

    article = relationship("Article", foreign_keys=[article_id])
    reporter = relationship("User", foreign_keys=[reporter_user_id])
    handled_by = relationship("User", foreign_keys=[handled_by_user_id])


class SizeField(Base):
    """Admin-verwaltbare Groessenart (z.B. Oberteil, Hose, Schuhe, Krawatte …).
    Reihenfolge ueber sort_order; inaktive werden ausgeblendet, aber nicht geloescht,
    damit bestehende Werte erhalten bleiben."""
    __tablename__ = "size_fields"
    id = Column(Integer, primary_key=True)
    label = Column(String(48), nullable=False)
    sort_order = Column(Integer, default=100)
    active = Column(Boolean, default=True, nullable=False)


class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True)
    artikelnummer = Column(String(64), unique=True, nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False, index=True)
    type_id = Column(Integer, ForeignKey("article_types.id"), nullable=False, index=True)
    size = Column(String(32), default="")
    model = Column(String(64), default="")       # Modell (weitere Untergliederung des Typs)
    properties = Column(Text, default="")        # weitere Eigenschaften (Freitext)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    storage_location_id = Column(Integer, ForeignKey("storage_locations.id"), nullable=True)
    # Fest verwalteter Lagerort-Knoten (Baum). Loest schrittweise die Freitext-
    # Ebenen unten ab; ist er gesetzt, hat er Vorrang bei der Pfad-Anzeige.
    storage_node_id = Column(Integer, ForeignKey("storage_nodes.id"), nullable=True, index=True)
    # Feinere Lagerort-Ebenen (Freitext, jede optional). "Etage" kann auch eine
    # Garage sein, "Raum" ein Auto usw.
    etage = Column(String(64), default="")
    raum = Column(String(64), default="")
    schrank = Column(String(64), default="")
    fach = Column(String(64), default="")
    # Aktueller Standort: bei Ausgabe automatisch der Name der Empfaenger-Person.
    # Der stammdaten-Lagerort (storage_location_id) bleibt als Rueckgabeort erhalten.
    current_location = Column(String(128), default="")
    status = Column(String(32), default=ArticleStatus.verfuegbar.value, nullable=False, index=True)
    condition_notes = Column(Text, default="")   # Beschaedigungen
    remarks = Column(Text, default="")           # Bemerkungen
    repair_expected_return = Column(DateTime, nullable=True)  # voraussichtl. Rueckdatum bei Reparatur
    repair_reason = Column(Text, default="")                  # Grund der Reparatur
    retire_reason = Column(Text, default="")                  # Grund beim Aussondern (ausgemustert)
    # Vorlaeufige Inventarisierung (z.B. schnell bei der Ausgabe angelegt, noch nicht
    # von einem Berechtigten geprueft). provisional=True bis zur Genehmigung.
    provisional = Column(Boolean, default=False, nullable=False, index=True)
    provisional_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Zeitpunkt der letzten Inventur-Erfassung (Scan/Zuordnung). Waehrend einer
    # laufenden Inventur gilt ein Artikel als "gefunden", wenn dieser Wert nach dem
    # Kampagnen-Start liegt; alles andere landet auf der offenen/fehlenden Liste.
    last_inventoried_at = Column(DateTime, nullable=True)
    # Ausgebbar/persoenlich zuordenbar: NULL = Standard der Klasse verwenden,
    # sonst True/False als Ueberschreibung fuer genau diesen Artikel.
    issuable_override = Column(Boolean, nullable=True)
    # Pruefwesen (PSA): Kennzeichen + Nutzungszaehler + Merker der faelligen Pruefung.
    is_psa = Column(Boolean, default=False, nullable=False)
    loan_count = Column(Integer, default=0, nullable=False)
    wash_count = Column(Integer, default=0, nullable=False)
    last_inspection_at = Column(DateTime, nullable=True)
    pending_checklist_id = Column(Integer, nullable=True)   # bewusst ohne FK/Cascade
    # Prüfung fällig – unabhängig vom Status, damit auch AUSGEGEBENE PSA geprüft
    # werden können. Bei verfügbaren Artikeln wird zusätzlich der Status „zu prüfen"
    # gesetzt (Ausgabesperre); ausgegebene behalten „ausgegeben".
    needs_inspection = Column(Boolean, default=False, nullable=False, index=True)
    # Einzelartikel-Override: eigene Prüfregeln statt der Typ-Regeln verwenden.
    inspection_override = Column(Boolean, default=False, nullable=False)
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
    def is_issuable(self) -> bool:
        """Ob der Artikel ausgegeben/persoenlich zugeordnet werden kann. Einzelartikel-
        Ueberschreibung hat Vorrang, sonst der Standard der Materialklasse."""
        if self.issuable_override is not None:
            return bool(self.issuable_override)
        return bool(self.category.issuable_default) if self.category else True

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
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True, index=True)
    recipient_name_freetext = Column(String(128), default="")
    issue_date = Column(DateTime, default=now)
    # Vereinbartes/voraussichtliches Rueckgabedatum (optional, bei der Ausgabe setzbar).
    expected_return_date = Column(DateTime, nullable=True)
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
