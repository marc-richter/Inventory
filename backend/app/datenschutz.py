"""Loeschkonzept: Aufbewahrungsfristen fuer personenbezogene Daten.

Die DSGVO verlangt, personenbezogene Daten nicht laenger aufzubewahren, als es
fuer den Zweck noetig ist (Art. 5 Abs. 1 lit. e, "Speicherbegrenzung"). Bisher
gab es das nur fuer das Pruefprotokoll; Ausgabehistorie, Quittungen und
Schadensmeldungen blieben unbegrenzt liegen.

Hier stehen die Fristen an einer Stelle zusammen. Alle sind im Auslieferungs-
zustand auf 0 gesetzt - also "unbegrenzt", damit sich bei einem Update an
bestehenden Installationen nichts von selbst aendert. Der Administrator stellt
sie in den Einstellungen unter "Sicherheit" ein.

Grundsatz: es wird so wenig wie moeglich geloescht und so viel wie noetig
anonymisiert. Wer wann welches Material zurueckgegeben hat, ist fuer die
Materialverwaltung wichtig - WER es war, nach Jahren aber nicht mehr. Deshalb
wird der Personenbezug entfernt und der Vorgang selbst behalten.
"""

import datetime as dt
from typing import Dict

from sqlalchemy.orm import Session

from . import models
from .config import RECEIPTS_DIR
from .logging_config import get_logger
from .settings_helper import get_setting

log = get_logger("datenschutz")

# Einstellungsname -> Beschreibung (auch fuer die Oberflaeche verwendbar)
FRISTEN = {
    "issue_retention_days": "Ausgabehistorie: Personenbezug nach X Tagen entfernen",
    "receipt_retention_days": "Unterschriebene Quittungen nach X Tagen loeschen",
    "report_retention_days": "Abgeschlossene Schadens-/Verlustmeldungen nach X Tagen anonymisieren",
    "audit_retention_days": "Pruefprotokoll nach X Tagen loeschen",
}


def _tage(db: Session, name: str) -> int:
    try:
        return int(get_setting(db, name, "0") or "0")
    except (TypeError, ValueError):
        return 0


def _grenze(tage: int):
    return dt.datetime.utcnow() - dt.timedelta(days=tage)


def ausgabehistorie_anonymisieren(db: Session, tage: int) -> int:
    """Entfernt den Personenbezug aus laengst zurueckgegebenen Ausgaben.

    Der Vorgang selbst (welcher Artikel, wann ausgegeben, wann zurueck, Zustand)
    bleibt erhalten - nur wer ihn hatte, wird geloescht. Laufende Ausgaben
    (noch nicht zurueckgegeben) werden nie angefasst.
    """
    if tage <= 0:
        return 0
    grenze = _grenze(tage)
    treffer = (db.query(models.IssueRecord)
               .filter(models.IssueRecord.return_date.isnot(None),
                       models.IssueRecord.return_date < grenze)
               .filter((models.IssueRecord.person_id.isnot(None))
                       | (models.IssueRecord.recipient_name_freetext != ""))
               .all())
    for eintrag in treffer:
        eintrag.person_id = None
        eintrag.recipient_name_freetext = ""
        eintrag.notes = ""
        eintrag.issued_by_user_id = None
        eintrag.returned_by_user_id = None
    if treffer:
        db.commit()
    return len(treffer)


def quittungen_loeschen(db: Session, tage: int) -> int:
    """Loescht alte Quittungen samt Datei.

    Quittungen enthalten Namen und haeufig eine eingescannte Unterschrift - das
    ist der sensibelste Datenbestand des Programms und gehoert nach Ablauf der
    Frist tatsaechlich geloescht, nicht nur anonymisiert.
    """
    if tage <= 0:
        return 0
    grenze = _grenze(tage)
    treffer = (db.query(models.Receipt)
               .filter(models.Receipt.created_at < grenze).all())
    for quittung in treffer:
        if quittung.filename:
            try:
                (RECEIPTS_DIR / quittung.filename).unlink(missing_ok=True)
            except OSError as exc:
                log.warning("Quittungsdatei %s nicht loeschbar: %s", quittung.filename, exc)
        db.delete(quittung)
    if treffer:
        db.commit()
    return len(treffer)


def meldungen_anonymisieren(db: Session, tage: int) -> int:
    """Entfernt Personenangaben aus abgeschlossenen Schadens-/Verlustmeldungen.

    Hergang, Ort und Wert bleiben als Sachverhalt erhalten; Melder, Zeugen und
    Rueckfrage-Kontakt verschwinden. Offene Meldungen bleiben unberuehrt, denn
    dort werden die Angaben noch gebraucht.
    """
    if tage <= 0:
        return 0
    grenze = _grenze(tage)
    treffer = (db.query(models.DamageLossReport)
               .filter(models.DamageLossReport.status == "done",
                       models.DamageLossReport.created_at < grenze)
               .filter((models.DamageLossReport.reporter_user_id.isnot(None))
                       | (models.DamageLossReport.witnesses != "")
                       | (models.DamageLossReport.reporter_contact != ""))
               .all())
    for meldung in treffer:
        meldung.reporter_user_id = None
        meldung.handled_by_user_id = None
        meldung.witnesses = ""
        meldung.reporter_contact = ""
    if treffer:
        db.commit()
    return len(treffer)


def alles_anwenden(db: Session) -> Dict[str, int]:
    """Wendet alle eingestellten Fristen an und meldet, was passiert ist."""
    from .audit import purge_old

    ergebnis = {
        "ausgaben_anonymisiert": ausgabehistorie_anonymisieren(db, _tage(db, "issue_retention_days")),
        "quittungen_geloescht": quittungen_loeschen(db, _tage(db, "receipt_retention_days")),
        "meldungen_anonymisiert": meldungen_anonymisieren(db, _tage(db, "report_retention_days")),
        "protokoll_geloescht": purge_old(db, _tage(db, "audit_retention_days")),
    }
    if any(ergebnis.values()):
        log.info("Aufbewahrungsfristen angewendet: %s",
                 ", ".join(f"{k}={v}" for k, v in ergebnis.items() if v))
    return ergebnis


def vorschau(db: Session) -> Dict[str, object]:
    """Zeigt, was die eingestellten Fristen betreffen WUERDEN - ohne zu loeschen.

    Damit kann ein Administrator eine Frist gefahrlos ausprobieren, bevor er sie
    speichert.
    """
    heute = dt.datetime.utcnow()

    def zaehle(tage: int, abfrage):
        if tage <= 0:
            return None      # None = keine Frist gesetzt
        return abfrage(heute - dt.timedelta(days=tage))

    return {
        "ausgaben": zaehle(_tage(db, "issue_retention_days"), lambda g: (
            db.query(models.IssueRecord)
            .filter(models.IssueRecord.return_date.isnot(None),
                    models.IssueRecord.return_date < g,
                    models.IssueRecord.person_id.isnot(None)).count())),
        "quittungen": zaehle(_tage(db, "receipt_retention_days"), lambda g: (
            db.query(models.Receipt).filter(models.Receipt.created_at < g).count())),
        "meldungen": zaehle(_tage(db, "report_retention_days"), lambda g: (
            db.query(models.DamageLossReport)
            .filter(models.DamageLossReport.status == "done",
                    models.DamageLossReport.created_at < g).count())),
        "protokoll": zaehle(_tage(db, "audit_retention_days"), lambda g: (
            db.query(models.AuditLog).filter(models.AuditLog.timestamp < g).count())),
    }
