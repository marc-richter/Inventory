# Inventarprogramm

Web-basiertes Inventarisierungsprogramm fuer Kleidung (und spaeter weitere Kategorien),
lauffaehig im lokalen Netz auf einem selbst gehosteten Rechner (Windows/Linux/Mac via Docker).
Nutzbar per Browser auf Mac/Windows und als installierbare PWA ("App") auf Android/iOS-Handys.

## Funktionen

- Gesamtübersicht mit Mehrfachfiltern (mehrere Kategorien/Typen/Abteilungen/Lagerorte/Status
  gleichzeitig auswählbar, Volltextsuche, Größe) inkl. "Alle Filter zurücksetzen"
- Erstinventarisierung mit frei erweiterbaren Typen (z.B. Polo Shirt, T-Shirt, Hose, Jacke,
  Schuhe, Handschuhe) und Lagerorten - bei neuem Eintrag erscheint eine Rückfrage, ob dieser
  in die Stammdaten übernommen werden soll
- Mengenerfassung: mehrere baugleiche Artikel (gleicher Typ/Größe/Abteilung/Lagerort) auf
  einmal anlegen - mit automatisch fortlaufend vergebenen, manuell eingegebenen oder
  eingescannten Artikelnummern; die erzeugte Charge lässt sich anschließend en bloc als
  eine Sammel-PDF mit allen Etiketten ausdrucken oder als Liste (CSV/PDF) exportieren
- Artikelnummer überall per Gerätekamera scanbar (QR-/Barcode), inkl. Schnellzugriff über die
  Suche in der Übersicht
- Ausgabe / Rücknahme von Artikeln mit dokumentiertem Ausgabe-/Rückgabedatum und
  vollständigem Verlauf pro Artikel; neue, noch nicht hinterlegte Empfänger können direkt
  bei der Ausgabe in die Personen-Stammdaten übernommen werden
- Statuswechsel (Verfügbar/Ausgegeben/In Reparatur/Ausgemustert) über einen Dialog, der je
  nach neuem Status automatisch die nötigen Zusatzangaben abfragt (z.B. bei "In Reparatur"
  Grund und voraussichtliches Rückgabedatum)
- Personenliste: zeigt je Person die aktuell ausgegebenen Artikel sowie eine ausklappbare
  Historie vergangener Ausgaben; Personen sind anlegbar, bearbeitbar und entfernbar
- "Meine Artikel": jeder Benutzer (insbesondere Helfer) sieht dort nur die Artikel, die
  aktuell an ihn persönlich ausgegeben sind
- Sichtbar, wer einen Artikel ursprünglich angelegt hat
- Alle Stammdaten (Kategorien, Typen, Abteilungen, Lagerorte, Personen) sind über die
  Einstellungen bzw. die Personenseite umbenennbar und löschbar
- Bilder pro Artikel (Aufnahme direkt per Handykamera möglich)
- Artikelnummer inkl. QR-Etikett zum Ausdrucken auf einem Brother-Labeldrucker
  (zum Aufbügeln/Aufkleben); optionaler Direktdruck über das Netzwerk bei
  WLAN/LAN-fähigen Brother-Druckern
- CSV- und PDF-Export gefilterter Listen
- CSV-Import (Reimport zuvor exportierter Daten): erkennt Duplikate anhand der
  Artikelnummer und stellt bestehende und importierte Werte Feld für Feld
  gegenüber - die Auswahl, welcher Datensatz übernommen wird, lässt sich pro
  Duplikat einzeln oder für alle Duplikate auf einmal treffen
- Eigenes Organisationslogo hochladbar (erscheint im Anmeldebildschirm und in der
  Kopfzeile)
- Benutzerkonten mit einer oder mehreren Rollen gleichzeitig (Administrator, Materialverwalter,
  Helfer, Nur-Lesend), optional mit einem Personendatensatz verknüpft; Benutzer sind über die
  Einstellungen vollständig bearbeitbar
- Anmeldung per Benutzername+Passwort ODER Benutzername+PIN (auf dem Handy erscheint
  automatisch ein Ziffernblock); PIN-Länge ist einstellbar, Nutzer können ihre PIN selbst ändern
- HTTPS mit automatisch erzeugtem, selbstsigniertem Zertifikat - Voraussetzung dafür, dass
  Browser den Kamerazugriff zum Scannen auf dem Handy überhaupt erlauben
- Backups: manuell per Knopfdruck oder automatisch (täglich, konfigurierbare Uhrzeit),
  Zielverzeichnis frei wählbar
- Änderungsprotokoll (Audit-Log)

## Voraussetzungen

- Docker auf dem Hosting-Rechner (Windows, Linux oder Mac) - die Installationsprogramme
  unten helfen bei Bedarf beim Einrichten
- Alle Geräte im selben lokalen Netzwerk (WLAN/LAN)

## Ausführliches Benutzerhandbuch

Eine vollständige Anleitung (Erstinstallation, Bedienung für alle Rollen, Backup,
Etikettendruck, Fehlerbehebung) befindet sich als PDF unter `docs/Benutzerhandbuch.pdf`
(Markdown-Quelle: `docs/Benutzerhandbuch.md`).

## Verwaltungs-App (empfohlen)

Im Ordner `installer/` liegt für jedes Betriebssystem **eine einzige Verwaltungs-App**,
die die frühere Sammlung einzelner Start-/Stop-/Installations-/Deinstallationsskripte
ersetzt. Sie zeigt eine Übersicht der Anwendung (Status, Version, Adressen,
Speicherbelegung) und bietet Knöpfe für Starten/Stoppen sowie einen absichtlich etwas
versteckten Bereich "Erweitert" für Erstinstallation/Update und Deinstallation:

| Betriebssystem | Datei | Start |
|---|---|---|
| macOS | `installer/Verwaltung-macOS.app` (oder `.command`) | Doppelklick |
| Windows | `installer/Verwaltung-Windows.bat` | Doppelklick (öffnet ein grafisches Fenster) |
| Linux | `installer/verwaltung-linux.sh` (oder `.desktop`) | Doppelklick bzw. `./verwaltung-linux.sh` im Terminal |

Details, Screenshots und Hinweise zu Sicherheitsabfragen des Betriebssystems
(z.B. macOS Gatekeeper, Windows SmartScreen) stehen im PDF-Benutzerhandbuch.

**Übersicht:** zeigt an, ob die Anwendung installiert/gestartet ist, die installierte
sowie die im Programmordner verfügbare Version (inkl. Hinweis, falls ein Update
vorliegt), die Adressen im lokalen Netz sowie die Speicherbelegung von Datenbank/Bildern,
Backup-Ordner, HTTPS-Zertifikaten und den gebauten Docker-Images.

**Starten/Stoppen:** startet bzw. hält die bereits eingerichtete Anwendung an, ohne
neu zu bauen - Daten bleiben dabei immer erhalten.

**Erweitert → Erstinstallation / Update:** fragt zunächst extra nach, ob dieser Bereich
wirklich geöffnet werden soll. Ist noch keine Installation vorhanden, führt die App
wie gewohnt durch die Ersteinrichtung (Administrator-Benutzername/-Passwort, Web-Port,
Backup-Verzeichnis - einfach die vorgeschlagenen Standardwerte übernehmen). Besteht
bereits eine Installation, erkennt die App das automatisch und bietet die Wahl zwischen:

1. **Update durchführen** - alle Daten bleiben vollständig erhalten, nur die Anwendung
   selbst wird auf die im Programmordner enthaltene neue Version aktualisiert.
2. **Neuinstallation, Daten behalten** - Container und Images werden komplett neu gebaut,
   Datenbank/Bilder/Backups/Konfiguration bleiben aber erhalten.
3. **Neuinstallation, Daten löschen** - entfernt zusätzlich unwiderruflich Datenbank,
   Bilder und Artikel-Verlauf (mit eigener, deutlich hervorgehobener Sicherheitsabfrage)
   und führt danach automatisch die Ersteinrichtung erneut durch.

**Erweitert → Deinstallation:** fragt ebenfalls zunächst extra nach, ob dieser Bereich
geöffnet werden soll, stoppt und entfernt dann die Container und fragt weiterhin
einzeln nach, ob Datenbank/Bilder/Verlauf, der Backup-Ordner, die HTTPS-Zertifikate
und die gebauten Docker-Images ebenfalls gelöscht werden sollen - standardmäßig bleibt
alles erhalten.

## Erststart manuell (alternativ)

```bash
cd inventar
cp .env.example .env
# .env öffnen und mindestens SECRET_KEY und DEFAULT_ADMIN_PASSWORD anpassen
docker compose up -d --build
```

Danach ist die Anwendung erreichbar unter:

```
http://<IP-des-Hosting-Rechners>:8080
https://<IP-des-Hosting-Rechners>:8443   (für Kamera-/Barcode-Scan auf dem Handy nötig)
```

Die Ports lassen sich über `WEB_PORT`/`WEB_TLS_PORT` in der `.env` ändern. Beim ersten
Start wird automatisch ein selbstsigniertes HTTPS-Zertifikat unter `./certs` erzeugt -
siehe Abschnitt "HTTPS und Kamera-Scan" weiter unten.

Erster Login: Benutzername `admin`, Passwort wie in `.env` unter `DEFAULT_ADMIN_PASSWORD`
hinterlegt (danach im Bereich "Mein Konto" bzw. "Einstellungen" ändern/PIN vergeben).

Läuft der Hosting-Rechner ohnehin durchgehend, ist "Starten"/"Stoppen" in der Regel gar
nicht nötig - die Container starten dank `restart: unless-stopped` nach einem
Rechner-Neustart von selbst wieder, sobald Docker läuft. Die Knöpfe sind vor allem für
gezieltes Pausieren (z.B. Wartung) oder Wiederstarten nach einer längeren Pause gedacht.

## Versionsnummer und Updates

Die Datei `VERSION` im Programmordner enthält die Version des jeweils vorliegenden
Programmstands; jede inhaltliche Änderung erhöht diese Nummer (siehe `CHANGELOG.md`).
Die Verwaltungs-Apps vergleichen diese Nummer beim Öffnen von "Erweitert" automatisch
mit der zuletzt tatsächlich installierten Version und zeigen an, ob ein Update
verfügbar ist.

## Nutzung auf dem Handy als App

Im mobilen Browser (Safari/Chrome) die obige Adresse öffnen, dann
"Zum Home-Bildschirm hinzufügen" wählen. Die Anwendung startet danach wie eine
eigenständige App inkl. Icon, ohne Browser-Leiste.

## Backups

- Manuell: Einstellungen → Backup → "Jetzt manuell sichern"
- Automatisch: Einstellungen → Backup → Automatik aktivieren + Uhrzeit festlegen
- Zielverzeichnis: Standardmäßig `./backups` auf dem Hosting-Rechner (per `BACKUP_HOST_PATH`
  in der `.env` änderbar, z.B. auf eine externe Platte oder ein NAS-Verzeichnis)
- Alte Backups werden automatisch nach der eingestellten Anzahl (Standard 30) gelöscht
- Wiederherstellung: aktuell per Datei-Upload über die Backup-API (`/api/backup/restore`)
  durch einen Administrator; anschließend Container neu starten (`docker compose restart backend`)

## HTTPS und Kamera-Scan

Browser erlauben den Kamerazugriff per JavaScript (zum Scannen von QR-/Barcodes) nur in
einem sogenannten "secure context" - also über HTTPS oder auf `localhost`. Deshalb wird
bei jeder Installation bzw. jedem Start automatisch ein selbstsigniertes Zertifikat unter
`./certs` erzeugt, und die Anwendung ist zusätzlich über `https://<IP>:8443` erreichbar.

Da es sich um ein selbstsigniertes (nicht von einer offiziellen Stelle bestätigtes)
Zertifikat handelt, zeigt der Browser beim allerersten Aufruf dieser Adresse auf jedem
Gerät eine Warnung ("Verbindung ist nicht privat" o.ä.). Das ist normal und unbedenklich
im eigenen lokalen Netz - einfach auf "Erweitert" bzw. "Details" und dann "Trotzdem
fortfahren" tippen. Diese Bestätigung ist pro Gerät nur einmalig nötig.

Über `http://` (ohne "s") funktioniert die Anwendung weiterhin ganz normal - nur der
Kamera-Scan steht dort aus technischen Gründen nicht zur Verfügung.

## CSV-Import (Reimport exportierter Daten)

Über die Seite "Import" (Administrator/Materialverwalter) lässt sich eine zuvor über
"CSV Export" erzeugte Datei wieder einlesen - z.B. nach externer Bearbeitung in Excel,
oder um Daten aus einer anderen Organisation/System zu übernehmen. Ablauf:

1. Datei auswählen und "Datei analysieren" klicken - es passiert dabei noch **keine**
   Änderung an der Datenbank.
2. Das Programm zeigt eine Übersicht: wie viele Zeilen neu angelegt würden, wie viele
   Artikelnummern bereits existieren (Duplikate) und welche Zeilen fehlerhaft sind
   (z.B. fehlende Pflichtfelder).
3. Für jedes gefundene Duplikat werden die bestehenden und die importierten Werte
   Feld für Feld gegenübergestellt (abweichende Werte werden hervorgehoben). Pro
   Duplikat lässt sich auswählen, ob der bestehende oder der importierte Datensatz
   übernommen werden soll - alternativ lässt sich diese Auswahl mit einem Klick auf
   alle Duplikate gleichzeitig anwenden und bei Bedarf einzeln überschreiben.
4. Mit "Import durchführen" werden neue Artikel angelegt und Duplikate entsprechend der
   getroffenen Auswahl übernommen oder unverändert gelassen; fehlende Kategorien, Typen,
   Abteilungen oder Lagerorte aus der Datei werden dabei automatisch als neue Stammdaten
   angelegt.

## Etikettendruck (Brother)

Unter Einstellungen → Etiketten & Drucker lässt sich das Etikettenformat (Breite/Höhe in mm,
inkl. gängiger Brother-DK-Label-Vorlagen) hinterlegen. Auf der Artikel-Detailseite
erzeugt "Etikett drucken (PDF)" ein PDF mit QR-Code und Artikelnummer, das über den normalen
Systemdruckdialog auf dem an den PC angeschlossenen Brother-Labeldrucker gedruckt wird -
das funktioniert unabhängig davon, ob der Drucker per USB, Bluetooth oder Netzwerk
angeschlossen ist.

Zusätzlich gibt es "Direktdruck (Netzwerk)": Ist der Brother-Drucker per WLAN/LAN im
selben Netzwerk eingebunden (IP-Adresse unter Einstellungen → Etiketten & Drucker
hinterlegt), versucht der Server, das Etikett direkt über Port 9100 an den Drucker zu
senden. Das funktioniert nur bei netzwerkfähigen Druckern und ist modellabhängig - bei
USB- oder Bluetooth-Druckern bitte immer den PDF-Weg nutzen, da ein im Docker-Container
laufender Server solche direkt am PC/Handy angeschlossenen Geräte grundsätzlich nicht
ansprechen kann.

Nach einer Mengenerfassung (siehe oben) lassen sich alle Etiketten der gerade angelegten
Charge ebenso mit einem Klick als eine einzige Sammel-PDF (eine Seite je Etikett) drucken
oder direkt an den Netzwerkdrucker senden, statt jeden Artikel einzeln öffnen zu müssen.

## Erweiterbarkeit

Kleidung ist als erste "Kategorie" angelegt. Über Einstellungen → Stammdaten lassen
sich weitere Kategorien, Typen und Abteilungen anlegen, ohne den Code zu ändern.
Das Datenmodell ist bewusst so aufgebaut, dass spätere Artikel-Kategorien
(z.B. Ausrüstung, Technik) denselben Ausgabe-/Rücknahme- und Verlaufs-Mechanismus
mitnutzen können.

## Technischer Aufbau

- Backend: Python (FastAPI), SQLite-Datenbank, JWT-Authentifizierung
- Frontend: React (Vite), als Progressive Web App (PWA) installierbar, Tailwind CSS
- Beide Teile laufen als Docker-Container, orchestriert über `docker-compose.yml`
- Datenpersistenz über Docker-Volumes (`inventar_data` für DB/Bilder, Bind-Mount für Backups)

## Projektstruktur

```
inventar/
├── backend/           FastAPI-Anwendung
├── frontend/          React-PWA
├── installer/         Verwaltungs-Apps (macOS/Windows/Linux)
├── docs/              Benutzerhandbuch (Markdown-Quelle + PDF)
├── backups/           Standard-Ablageort für Backups (enthält auch .installed_version)
├── certs/             Automatisch erzeugtes HTTPS-Zertifikat (für Kamera-Scan)
├── docker-compose.yml
├── VERSION            Aktuelle Versionsnummer des Programmstands
├── CHANGELOG.md        Änderungsprotokoll je Version
├── .env.example       Vorlage für die Konfigurationsdatei
└── README.md
```

## Entwicklung ohne Docker (optional)

Backend:
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
DATA_DIR=./data uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Lizenz

Dieses Projekt steht unter der **GNU Affero General Public License v3.0 or later
(AGPL-3.0-or-later)** – siehe die Datei [`LICENSE`](LICENSE).

Wichtiger Hinweis zur AGPL: Wird eine (ggf. veränderte) Version über ein Netzwerk
betrieben, muss den Nutzern der zugehörige Quellcode zugänglich gemacht werden
(§ 13). Eine Übersicht der verwendeten Open-Source-Komponenten und ihrer
Lizenzen steht in [`THIRD-PARTY-LICENSES.md`](THIRD-PARTY-LICENSES.md).
