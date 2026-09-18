import shutil
from pathlib import Path

from sqlalchemy.orm import Session
from . import models, security
from .config import (
    DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ORG_NAME, DEFAULT_LOGO_FILE, BRANDING_DIR,
)
from .settings_helper import ensure_defaults, get_setting, set_setting

DEFAULT_TYPES = ["Polo Shirt", "T-Shirt", "Hose", "Jacke", "Schuhe", "Handschuhe"]
DEFAULT_ORGS = ["Abteilung 01", "Abteilung 02"]

# Eingebaute (is_builtin) und zusaetzliche Standard-Status. is_builtin=True koennen
# nicht geloescht werden. category_ids=[] bedeutet: gilt fuer alle Artikelklassen.
# (key, label, sort_order, is_builtin, require_note, allow_image)
# "Beschädigt" verlangt beim Setzen eine Beschreibung (Freitext) und bietet einen
# optionalen Bild-Anhang (Schadensbild) an.
# Eingebaute Status - werden bei JEDEM Start sichergestellt (sie sind fest im
# Programm verankert und nicht loeschbar).
# (key, label, sort_order, issue_policy)
BUILTIN_STATUSES = [
    ("verfuegbar", "Verfügbar", 10, "direct"),
    ("ausgegeben", "Ausgegeben", 20, "direct"),
    ("reparatur", "In Reparatur", 30, "confirm"),
    ("ausgemustert", "Ausgemustert", 40, "blocked"),
    # Nach einer Inventur nicht auffindbare Artikel. Nicht ausgebbar (blocked);
    # taucht der Artikel wieder auf, wird beim Zurücksetzen benachrichtigt.
    ("verschollen", "Verschollen", 45, "blocked"),
    # PSA-Pruefung faellig: gesperrt, bis die Pruefung bestanden ist.
    ("zu_pruefen", "Zu prüfen", 35, "blocked"),
]

# Frueher standen hier drei Beispiel-Status (Zu waschen, Beschaedigt, Infektioes)
# ohne Klassenbindung - sie tauchten damit auch bei Schluesseln und Fahrzeugen auf.
# Sie kommen jetzt aus systemkategorien.STATUS und sind der Kleidung zugeordnet.
EXAMPLE_STATUSES = []


def seed_builtin_statuses(db: Session):
    for key, label, order, policy in BUILTIN_STATUSES:
        if not db.query(models.StatusDef).filter(models.StatusDef.key == key).first():
            db.add(models.StatusDef(
                key=key, label=label, sort_order=order,
                is_builtin=True, active=True, category_ids=[], issue_policy=policy,
            ))
    db.commit()


def seed_example_statuses(db: Session):
    for key, label, order, require_note, allow_image, policy in EXAMPLE_STATUSES:
        if not db.query(models.StatusDef).filter(models.StatusDef.key == key).first():
            db.add(models.StatusDef(
                key=key, label=label, sort_order=order,
                is_builtin=False, active=True, category_ids=[],
                require_note=require_note, allow_image=allow_image, issue_policy=policy,
            ))
    db.commit()

# Welche Logo-Dateiendungen bei der Erstinstallation uebernommen werden duerfen.
_LOGO_EXTS = {".png": ".png", ".jpg": ".jpg", ".jpeg": ".jpg", ".svg": ".svg", ".webp": ".webp"}


def seed_personalization(db: Session):
    """Uebernimmt einmalig die von der Verwaltungs-App bei der Erstinstallation
    bereitgestellte Personalisierung (Organisationsname, Logo) - aber nur, solange
    der jeweilige Wert noch nicht gesetzt ist. So werden bei einem spaeteren Start
    keine vom Administrator geaenderten Werte ueberschrieben."""
    # Organisationsname
    if DEFAULT_ORG_NAME and not (get_setting(db, "org_name", "") or "").strip():
        set_setting(db, "org_name", DEFAULT_ORG_NAME)

    # Logo (optional): aus dem gemounteten Initial-Verzeichnis in den Branding-Ordner
    if DEFAULT_LOGO_FILE and not (get_setting(db, "logo_filename", "") or "").strip():
        src = Path(DEFAULT_LOGO_FILE)
        ext = _LOGO_EXTS.get(src.suffix.lower())
        if ext and src.is_file():
            dest_name = f"logo{ext}"
            try:
                BRANDING_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, BRANDING_DIR / dest_name)
                set_setting(db, "logo_filename", dest_name)
            except OSError:
                # Fehlgeschlagenes Kopieren soll den Start nicht verhindern -
                # der Administrator wird ohnehin per Popup an das Logo erinnert.
                pass


def _split_name(name: str):
    parts = (name or "").strip().split()
    if not parts:
        return ("Benutzer", "-")
    if len(parts) == 1:
        return (parts[0], "-")
    return (parts[0], " ".join(parts[1:]))


def backfill_person_user_links(db: Session):
    """Gleicht bestehende Daten an das Prinzip "Person = Benutzer" an - idempotent,
    laeuft bei jedem Start, macht aber nur einmalig Arbeit:
      1) Benutzer ohne verknuepfte Person -> Person aus dem Namen anlegen & verknuepfen.
      2) Aktive Person ohne Benutzerkonto -> passwortloses Konto (Standardrolle) anlegen.
    """
    from .usernames import ensure_user_for_person

    # 1) Benutzer ohne Person ergaenzen
    for u in db.query(models.User).filter(models.User.person_id.is_(None)).all():
        first, last = _split_name(u.full_name or u.username)
        p = models.Person(first_name=first, last_name=last, active=bool(u.active))
        db.add(p)
        db.commit()
        db.refresh(p)
        u.person_id = p.id
        db.commit()

    # 2) Personen ohne Benutzer ergaenzen (nur aktive, um deaktivierte nicht
    #    "wiederzubeleben").
    linked = {pid for (pid,) in db.query(models.User.person_id)
              .filter(models.User.person_id.isnot(None)).all()}
    for p in db.query(models.Person).filter(models.Person.active == True).all():  # noqa: E712
        if p.id not in linked:
            ensure_user_for_person(db, p)


def backfill_storage_nodes(db: Session):
    """Legt fuer jeden bestehenden Standort (StorageLocation) einen Wurzelknoten im
    verwalteten Standort-Baum an, falls noch keiner gleichen Namens existiert. So
    starten Bestandsinstallationen mit ihren Standorten; Unterebenen werden dann
    frisch im Baum angelegt (Entscheidung "neu aufbauen"). Idempotent."""
    existing = {n.name for n in db.query(models.StorageNode)
                .filter(models.StorageNode.parent_id.is_(None)).all()}
    created = False
    for loc in db.query(models.StorageLocation).all():
        if loc.name in existing:
            continue
        db.add(models.StorageNode(
            parent_id=None, level="standort", name=loc.name,
            address=loc.address or "", contact_name=loc.contact_name or "",
            contact_phone=loc.contact_phone or "", contact_fax=loc.contact_fax or "",
            contact_email=loc.contact_email or "",
        ))
        existing.add(loc.name)
        created = True
    if created:
        db.commit()


def backfill_min_stock_rules(db: Session):
    """Uebernimmt vorhandene Mindestbestaende vom Typ (ArticleType.min_stock) einmalig
    als Basis-Regel (ganzer Bestand, alle Groessen) in die neue Regel-Tabelle."""
    for t in db.query(models.ArticleType).filter(models.ArticleType.min_stock > 0).all():
        exists = db.query(models.MinStockRule).filter(
            models.MinStockRule.type_id == t.id,
            models.MinStockRule.size == "",
            models.MinStockRule.node_id.is_(None),
        ).first()
        if not exists:
            db.add(models.MinStockRule(type_id=t.id, size="", node_id=None, min_stock=t.min_stock))
    db.commit()


DEFAULT_SIZE_FIELDS = [("Oberteil", 10), ("Hose", 20), ("Schuhe", 30), ("Kopf", 40), ("Handschuhe", 50)]


def seed_size_fields(db: Session):
    """Legt die Standard-Groessenarten an, falls noch keine existieren, und uebernimmt
    einmalig Werte aus den alten festen Spalten in die neue Groessen-Map."""
    if db.query(models.SizeField).first() is None:
        for label, order in DEFAULT_SIZE_FIELDS:
            db.add(models.SizeField(label=label, sort_order=order, active=True))
        db.commit()
    # Backfill: alte feste Spalten -> sizes-Map (nur wenn Map noch leer ist)
    by_label = {f.label: f for f in db.query(models.SizeField).all()}
    mapping = [("size_top", "Oberteil"), ("size_bottom", "Hose"), ("size_shoes", "Schuhe"),
               ("size_head", "Kopf"), ("size_gloves", "Handschuhe")]
    changed = False
    for p in db.query(models.Person).all():
        if p.sizes:
            continue
        m = {}
        for col, label in mapping:
            val = (getattr(p, col, "") or "").strip()
            f = by_label.get(label)
            if val and f:
                m[str(f.id)] = val
        if m:
            p.sizes = m
            changed = True
    if changed:
        db.commit()


# ---------------------------------------------------------------------------
# Systemkategorien: Klassen, Standardfelder, Status und Pruefarten, die das
# Programm mitbringt. Wird bei JEDEM Start abgeglichen - fehlendes wird ergaenzt,
# vorhandenes nie ueberschrieben. Was der Administrator umbenannt oder
# ausgeblendet hat, bleibt also so.
# ---------------------------------------------------------------------------

def backfill_person_organizations(db: Session):
    """Uebernimmt die bisherige einzelne Abteilung in die Mehrfach-Zuordnung.

    Bis 1.101.0 hatte eine Person genau eine Abteilung (persons.organization_id).
    Seit 1.102.0 kann sie mehreren angehoeren; die Haupt-Abteilung bleibt an der
    Person, alle Zugehoerigkeiten stehen zusaetzlich in person_organizations.
    Ohne diese Uebernahme waere die Liste nach dem Update leer - Auswertungen und
    Zustaendigkeiten zeigten dann etwas anderes als vorher.

    Laeuft nur EINMAL: sobald es irgendeine Zuordnung gibt, wird nichts mehr
    angefasst. Sonst kaeme eine vom Administrator entfernte Zuordnung bei jedem
    Start zurueck.
    """
    if db.query(models.PersonOrganization).first() is not None:
        return 0
    personen = db.query(models.Person).filter(models.Person.organization_id.isnot(None)).all()
    for p in personen:
        db.add(models.PersonOrganization(person_id=p.id, organization_id=p.organization_id))
    if personen:
        db.commit()
    return len(personen)


def seed_system_categories(db: Session):
    from .systemkategorien import KATEGORIEN, FELDER, STATUS, CHECKLISTEN, PRUEFARTEN

    nach_key = {}

    # --- Kategorien -------------------------------------------------------
    for skey, name, eltern_key, key_system, sort_order, schloesser in KATEGORIEN:
        kat = db.query(models.Category).filter(models.Category.system_key == skey).first()
        if not kat:
            # Bestehende Installationen haben "Kleidung"/"Schluessel" schon unter
            # diesem Namen - die werden uebernommen statt doppelt angelegt.
            kat = db.query(models.Category).filter(
                models.Category.name == name, models.Category.system_key.is_(None)).first()
            if kat:
                kat.system_key = skey
            else:
                kat = models.Category(name=name, system_key=skey, key_system=key_system,
                                      has_locks=schloesser)
                db.add(kat)
            db.flush()
        if key_system and not kat.key_system:
            kat.key_system = True
        # Das Schloesser-Kennzeichen wird hier bewusst NICHT nachgezogen: bestehende
        # Installationen bekommen es einmalig von der Migration, danach gehoert die
        # Entscheidung dem Administrator. Sonst waere ein abgeschaltetes Kennzeichen
        # nach dem naechsten Neustart wieder da.
        nach_key[skey] = kat
    db.commit()

    # Eltern-Zuordnung erst danach, wenn alle Kategorien existieren.
    for skey, _name, eltern_key, _ks, _so, _sl in KATEGORIEN:
        if eltern_key and nach_key.get(skey) is not None and nach_key.get(eltern_key) is not None:
            kat = nach_key[skey]
            if kat.parent_id is None:
                kat.parent_id = nach_key[eltern_key].id
    db.commit()

    # --- Standardfelder ---------------------------------------------------
    for skey, felder in FELDER.items():
        kat = nach_key.get(skey)
        if kat is None:
            continue
        for feld_key, label, typ, optionen, pflicht, sort_order in felder:
            voll = f"{skey}.{feld_key}"
            if db.query(models.CustomFieldDef).filter(
                    models.CustomFieldDef.system_key == voll).first():
                continue
            db.add(models.CustomFieldDef(
                label=label, field_type=typ, options=list(optionen),
                category_id=kat.id, system_key=voll, required=pflicht,
                sort_order=sort_order, active=True,
            ))
    db.commit()

    # --- Status -----------------------------------------------------------
    for key, label, sort_order, kat_keys, notiz, bild, policy in STATUS:
        vorhanden = db.query(models.StatusDef).filter(models.StatusDef.key == key).first()
        ids = [] if kat_keys is None else [nach_key[k].id for k in kat_keys if k in nach_key]
        if vorhanden:
            # Kleidungsstatus galten frueher fuer ALLE Klassen - "Zu waschen" tauchte
            # damit auch bei Schluesseln auf. Hat der Administrator keine eigene
            # Einschraenkung gesetzt, wird sie hier einmalig nachgezogen.
            if ids and not (vorhanden.category_ids or []):
                vorhanden.category_ids = ids
            continue
        db.add(models.StatusDef(
            key=key, label=label, sort_order=sort_order, is_builtin=False, active=True,
            category_ids=ids, require_note=notiz, allow_image=bild, issue_policy=policy,
        ))
    db.commit()

    # --- Prueflisten ------------------------------------------------------
    listen = {}
    for name, punkte in CHECKLISTEN.items():
        liste = db.query(models.InspectionChecklist).filter(
            models.InspectionChecklist.name == name).first()
        if not liste:
            liste = models.InspectionChecklist(name=name)
            db.add(liste)
            db.flush()
            for i, punkt in enumerate(punkte):
                db.add(models.InspectionChecklistItem(checklist_id=liste.id, position=i, label=punkt))
        listen[name] = liste
    db.commit()

    # --- Pruef- und Terminarten ------------------------------------------
    for (name, beschreibung, kat_keys, monate, km, km_basiert, listen_name, pruefart,
         erfassungsfelder) in PRUEFARTEN:
        art = db.query(models.MaintenanceType).filter(models.MaintenanceType.name == name).first()
        if not art:
            art = models.MaintenanceType(
                name=name, description=beschreibung,
                interval_months=monate, interval_km=km, km_based=km_basiert,
                kind=pruefart,
                checklist_id=listen[listen_name].id if listen_name in listen else None,
            )
            db.add(art)
            db.flush()
        elif not (art.kind or "").strip():
            # Bestandsinstallation: die Art war bisher nicht unterschieden.
            art.kind = pruefart
        # Erfassungsfelder (Messwerte) nur ergaenzen, was fehlt - was der
        # Administrator umbenannt oder geloescht hat, bleibt so.
        for pos, label in enumerate(erfassungsfelder, start=1):
            schon = db.query(models.MaintenanceField).filter(
                models.MaintenanceField.type_id == art.id,
                models.MaintenanceField.label == label).first()
            if not schon:
                db.add(models.MaintenanceField(type_id=art.id, label=label, position=pos * 10))
        for k in kat_keys:
            kat = nach_key.get(k)
            if kat is None:
                continue
            schon = db.query(models.MaintenanceAssignment).filter(
                models.MaintenanceAssignment.mtype_id == art.id,
                models.MaintenanceAssignment.category_id == kat.id).first()
            if not schon:
                db.add(models.MaintenanceAssignment(mtype_id=art.id, category_id=kat.id,
                                                    mode="include"))
    db.commit()


def seed(db: Session):
    ensure_defaults(db)
    seed_personalization(db)
    # Eingebaute Status immer sicherstellen (fest im Programm verankert).
    seed_builtin_statuses(db)

    # "Frische" Installation = noch kein Benutzer vorhanden. Nur dann werden die
    # Beispiel-Stammdaten (Kategorie, Typen, Abteilungen) und Beispiel-Status
    # angelegt. Loescht der Administrator sie spaeter, kommen sie NICHT zurueck.
    fresh_install = db.query(models.User).first() is None
    if fresh_install:
        seed_example_statuses(db)

        admin = models.User(
            username=DEFAULT_ADMIN_USERNAME,
            full_name="Administrator",
            roles=[models.Role.admin.value],
            pin_length=4,
        )
        admin.password_hash = security.hash_secret(DEFAULT_ADMIN_PASSWORD)
        db.add(admin)
        db.commit()

        kleidung = db.query(models.Category).filter(models.Category.name == "Kleidung").first()
        if not kleidung:
            kleidung = models.Category(name="Kleidung")
            db.add(kleidung)
            db.commit()
            db.refresh(kleidung)

        for name in DEFAULT_TYPES:
            exists = db.query(models.ArticleType).filter(
                models.ArticleType.category_id == kleidung.id,
                models.ArticleType.name == name
            ).first()
            if not exists:
                db.add(models.ArticleType(name=name, category_id=kleidung.id))
        db.commit()

        # Schlüssel-Kategorie standardmäßig anlegen (wie Kleidung), mit aktiviertem
        # Schließanlagen-Kennzeichen, damit die Schlüssel-Funktionen sofort bereitstehen.
        schluessel = db.query(models.Category).filter(models.Category.name == "Schlüssel").first()
        if not schluessel:
            db.add(models.Category(name="Schlüssel", key_system=True))
            db.commit()

        for name in DEFAULT_ORGS:
            if not db.query(models.Organization).filter(models.Organization.name == name).first():
                db.add(models.Organization(name=name))
        db.commit()

    # Bestehende Daten an "Person = Benutzer" angleichen (idempotent).
    backfill_person_user_links(db)
    # Standort-Baum aus bestehenden Standorten vorbelegen (idempotent).
    backfill_storage_nodes(db)
    # Vorhandene Typ-Mindestbestaende in Regeln uebernehmen (idempotent).
    backfill_min_stock_rules(db)
    # Groessenarten sicherstellen + alte feste Groessenspalten uebernehmen.
    seed_size_fields(db)
    # Bisherige Abteilungs-Zuordnung in die Mehrfach-Zuordnung uebernehmen.
    backfill_person_organizations(db)
    # Mitgelieferte Materialklassen samt Feldern, Status und Pruefarten abgleichen.
    seed_system_categories(db)
