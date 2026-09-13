"""Echtzeit-Benachrichtigung an offene Browser-Fenster.

Warum das so gebaut ist
-----------------------
Die Oberflaeche hat bisher im Sekundentakt nachgefragt ("Polling"): jede offene
Uebersicht hat alle acht Sekunden die komplette Liste neu geladen. Das kostet
auf einem Raspberry Pi spuerbar Leistung und zeigt Aenderungen trotzdem erst
verzoegert an.

Der Server laeuft mit mehreren Arbeitsprozessen (gunicorn, 3 Worker). Ein
Prozess weiss nichts von den Verbindungen der anderen - eine Nachricht, die nur
im Speicher eines Prozesses verteilt wird, erreicht also nur einen Teil der
Nutzer. Deshalb laeuft der Weg ueber die Datenbank, die sich alle Prozesse
teilen:

    Aenderung  ->  Zeile in Tabelle change_events
                   jeder Arbeitsprozess liest neue Zeilen (alle 2 Sekunden)
                   und schickt sie an SEINE offenen Verbindungen

Datenschutz
-----------
Ueber die Verbindung geht bewusst nur, DASS sich in einem Bereich etwas
geaendert hat (z.B. "artikel", "ausgaben") - nie Namen, Inhalte oder wer etwas
getan hat. Die Oberflaeche laedt daraufhin ganz normal ueber die uebliche
Schnittstelle nach, und dabei greifen wie immer die Berechtigungen des
angemeldeten Benutzers. So kann ueber die Echtzeitverbindung nichts
durchsickern, was jemand nicht ohnehin sehen duerfte.

Auch die Anmeldung wurde geaendert: der Sitzungsschluessel wird nicht mehr an
die Adresse angehaengt (dort landet er in Server-Protokollen und im Verlauf),
sondern als erste Nachricht ueber die bereits aufgebaute Verbindung geschickt.
"""

import asyncio
import datetime as dt
from typing import Dict, Optional, Set

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from . import models
from .database import SessionLocal
from .logging_config import get_logger

log = get_logger("echtzeit")

# Wie oft ein Arbeitsprozess nach neuen Ereignissen sieht.
TAKT_SEKUNDEN = 2.0
# Wie lange auf die Anmeldung gewartet wird, bevor die Verbindung geschlossen wird.
ANMELDE_FRIST_SEKUNDEN = 10.0
# Aelter als das braucht niemand mehr - die Tabelle bleibt dadurch winzig.
AUFBEWAHRUNG_MINUTEN = 60

# Welcher Bereich zu welcher Art von Datensatz gehoert. Die Oberflaeche
# abonniert Bereiche, nicht einzelne Datensaetze.
BEREICHE = {
    "article": "artikel",
    "articles": "artikel",
    "category": "artikel",
    "type": "artikel",
    "storage_node": "artikel",
    "issue": "ausgaben",
    "issue_record": "ausgaben",
    "bereitstellung": "ausgaben",
    "inventory": "inventur",
    "inventory_campaign": "inventur",
    "inventory_scan": "inventur",
    "damage_report": "meldungen",
    "damage_loss_report": "meldungen",
    "request": "anfragen",
    "material_request": "anfragen",
    "maintenance": "wartung",
    "inspection": "wartung",
    "key": "schluessel",
    "key_object": "schluessel",
    "vehicle": "fahrzeuge",
    "vehicle_log": "fahrzeuge",
    "person": "personen",
    "user": "benutzer",
    "setting": "einstellungen",
    "system": "system",
}
ALLE_BEREICHE = sorted(set(BEREICHE.values()))


def bereich_fuer(entity_type: str, action: str = "") -> str:
    """Ordnet einen Datensatz-Typ einem Bereich zu. Unbekanntes -> "sonstiges"."""
    schluessel = (entity_type or "").strip().lower()
    if schluessel in BEREICHE:
        return BEREICHE[schluessel]
    # Zweiter Versuch ueber die Aktion, z.B. "article_create".
    for name, bereich in BEREICHE.items():
        if (action or "").lower().startswith(name + "_"):
            return bereich
    return "sonstiges"


def ereignis_objekt(entity_type: str, entity_id=None, action: str = ""):
    """Baut den Vermerk, ohne ihn zu speichern.

    So kann er zusammen mit dem Protokolleintrag in EINEM Schreibvorgang
    abgelegt werden - auf einem Raspberry Pi ist jeder gesparte Schreibzugriff
    spuerbar.
    """
    return models.ChangeEvent(
        bereich=bereich_fuer(entity_type, action),
        entity_type=(entity_type or "")[:64],
        entity_id=entity_id if isinstance(entity_id, int) else None,
    )


def ereignis_melden(db, entity_type: str, entity_id=None, action: str = "") -> None:
    """Haelt eine Aenderung fest, damit offene Fenster davon erfahren.

    Darf unter keinen Umstaenden den eigentlichen Vorgang scheitern lassen -
    deshalb faengt die Funktion alles ab und schreibt hoechstens eine Zeile ins
    Protokoll.
    """
    try:
        db.add(ereignis_objekt(entity_type, entity_id, action))
        db.commit()
    except Exception:  # pragma: no cover - reine Absicherung
        try:
            db.rollback()
        except Exception:
            pass
        log.debug("Ereignis konnte nicht vermerkt werden", exc_info=True)


def alte_ereignisse_loeschen() -> int:
    """Raeumt die Ereignistabelle auf (wird vom Zeitplan aufgerufen)."""
    db = SessionLocal()
    try:
        grenze = dt.datetime.utcnow() - dt.timedelta(minutes=AUFBEWAHRUNG_MINUTEN)
        anzahl = (db.query(models.ChangeEvent)
                  .filter(models.ChangeEvent.timestamp < grenze)
                  .delete(synchronize_session=False))
        db.commit()
        return anzahl
    finally:
        db.close()


class Verteiler:
    """Haelt die offenen Verbindungen DIESES Arbeitsprozesses."""

    def __init__(self) -> None:
        self.verbindungen: Dict[WebSocket, Set[str]] = {}
        self._aufgabe: Optional[asyncio.Task] = None
        self._letzte_id: Optional[int] = None

    async def aufnehmen(self, ws: WebSocket) -> None:
        # Den Stand der Ereignisse MERKEN, bevor die Verbindung als bereit gilt.
        # Geschaehe das erst in der Schleife, koennte eine Aenderung, die genau
        # dazwischen faellt, uebersprungen werden - der Browser haette sie nie
        # erfahren.
        if self._letzte_id is None:
            schleife = asyncio.get_running_loop()
            self._letzte_id = await schleife.run_in_executor(None, self._hoechste_id)
        self.verbindungen[ws] = set(ALLE_BEREICHE)
        if self._aufgabe is None or self._aufgabe.done():
            self._aufgabe = asyncio.create_task(self._schleife())

    def entfernen(self, ws: WebSocket) -> None:
        self.verbindungen.pop(ws, None)

    def abonnieren(self, ws: WebSocket, bereiche) -> Set[str]:
        gewaehlt = {b for b in (bereiche or []) if isinstance(b, str)}
        gewaehlt = gewaehlt or set(ALLE_BEREICHE)
        self.verbindungen[ws] = gewaehlt
        return gewaehlt

    def _hoechste_id(self) -> int:
        db = SessionLocal()
        try:
            letzte = (db.query(models.ChangeEvent.id)
                      .order_by(models.ChangeEvent.id.desc()).first())
            return letzte[0] if letzte else 0
        finally:
            db.close()

    def _neue_ereignisse(self, ab_id: int):
        db = SessionLocal()
        try:
            return (db.query(models.ChangeEvent)
                    .filter(models.ChangeEvent.id > ab_id)
                    .order_by(models.ChangeEvent.id)
                    .limit(500).all())
        finally:
            db.close()

    async def _schleife(self) -> None:
        """Sieht regelmaessig nach neuen Ereignissen und verteilt sie.

        Laeuft nur, solange dieser Arbeitsprozess ueberhaupt Verbindungen hat -
        ohne offene Fenster wird die Datenbank nicht angefasst.
        """
        schleife = asyncio.get_running_loop()
        if self._letzte_id is None:  # pragma: no cover - aufnehmen() setzt das bereits
            self._letzte_id = await schleife.run_in_executor(None, self._hoechste_id)
        log.info("Echtzeit-Verteilung gestartet")
        try:
            while self.verbindungen:
                await asyncio.sleep(TAKT_SEKUNDEN)
                if not self.verbindungen:
                    break
                try:
                    ereignisse = await schleife.run_in_executor(
                        None, self._neue_ereignisse, self._letzte_id)
                except Exception:
                    log.exception("Ereignisse konnten nicht gelesen werden")
                    continue
                if not ereignisse:
                    continue
                self._letzte_id = ereignisse[-1].id
                # Mehrere Aenderungen im selben Bereich zu einer Nachricht
                # zusammenfassen - sonst laedt die Oberflaeche bei einem Import
                # hunderte Male neu.
                gebuendelt: Dict[str, dict] = {}
                for e in ereignisse:
                    eintrag = gebuendelt.setdefault(
                        e.bereich, {"typ": "aenderung", "bereich": e.bereich, "anzahl": 0, "ids": []})
                    eintrag["anzahl"] += 1
                    if e.entity_id and len(eintrag["ids"]) < 20:
                        eintrag["ids"].append(e.entity_id)
                for bereich, nachricht in gebuendelt.items():
                    await self.senden(bereich, nachricht)
        except asyncio.CancelledError:  # pragma: no cover
            raise
        except Exception:  # pragma: no cover
            log.exception("Echtzeit-Verteilung abgebrochen")
        finally:
            log.info("Echtzeit-Verteilung beendet")

    async def senden(self, bereich: str, nachricht: dict) -> None:
        for ws, abos in list(self.verbindungen.items()):
            if bereich not in abos:
                continue
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(nachricht)
                else:
                    self.entfernen(ws)
            except Exception:
                self.entfernen(ws)


verteiler = Verteiler()


async def _anmelden(ws: WebSocket):
    """Wartet auf die erste Nachricht mit dem Sitzungsschluessel."""
    from . import security

    try:
        erste = await asyncio.wait_for(ws.receive_json(), timeout=ANMELDE_FRIST_SEKUNDEN)
    except Exception:
        # Zeitueberschreitung oder ungueltige Nachricht: keine Anmeldung.
        return None
    if not isinstance(erste, dict) or erste.get("typ") != "anmeldung":
        return None
    token = erste.get("token")
    if not isinstance(token, str) or not token:
        return None
    daten = security.decode_token(token)
    if not daten:
        return None
    db = SessionLocal()
    try:
        benutzer = (db.query(models.User)
                    .filter(models.User.username == daten.get("sub")).first())
        if not benutzer or not benutzer.active:
            return None
        return benutzer.id
    finally:
        db.close()


async def websocket_endpoint(ws: WebSocket) -> None:
    """Nimmt eine Verbindung an, meldet sie an und haelt sie offen."""
    await ws.accept()
    benutzer_id = await _anmelden(ws)
    if benutzer_id is None:
        try:
            await ws.close(code=1008)
        except Exception:
            pass
        return

    await verteiler.aufnehmen(ws)
    try:
        await ws.send_json({"typ": "bereit", "bereiche": ALLE_BEREICHE, "takt": TAKT_SEKUNDEN})
        while True:
            nachricht = await ws.receive_json()
            if not isinstance(nachricht, dict):
                continue
            typ = nachricht.get("typ")
            if typ == "abo":
                gewaehlt = verteiler.abonnieren(ws, nachricht.get("bereiche"))
                await ws.send_json({"typ": "abo", "bereiche": sorted(gewaehlt)})
            elif typ == "ping":
                await ws.send_json({"typ": "pong"})
    except Exception:
        # Verbindungsabbrueche sind der Normalfall und kein Fehler.
        pass
    finally:
        verteiler.entfernen(ws)
