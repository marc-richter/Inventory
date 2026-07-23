# Änderungsprotokoll (Changelog)

Ab Version 1.0.0 wird für jede inhaltliche Änderung am Programm eine neue
Versionsnummer vergeben (Format: MAJOR.MINOR.PATCH). Die aktuelle Version steht
in der Datei `VERSION` im Projektordner. Die Verwaltungs-Apps (siehe
`installer/`) vergleichen diese Versionsnummer beim Erstinstallation/Update-Dialog
mit der Version, die zuletzt tatsächlich installiert/gestartet wurde, und zeigen
an, ob ein Update verfügbar ist.

## 1.1.0

- **Gefuehrte Personalisierung bei der Erstinstallation.** Die Verwaltungs-Apps
  (macOS, Windows, Linux) fragen jetzt optional den Organisationsnamen und ein
  Logo ab, sodass direkt nach der Installation ein fertig personalisiertes
  Produkt bereitsteht. Bei den Terminal-Apps (macOS/Linux) gilt pro Abfrage ein
  Zeitlimit von 60 Sekunden: Erfolgt keine Eingabe, wird von einer
  unbeaufsichtigten (Remote-)Installation ausgegangen und ohne diese Werte
  fortgefahren. Unter Windows sind die Felder im Installationsformular optional.
- **Erinnerung an fehlende Personalisierung.** Solange erforderliche bzw.
  empfohlene Personalisierungs-Einstellungen (Organisationsname, Logo) noch nicht
  hinterlegt sind, wird der Administrator nach dem Login per Popup daran erinnert,
  bis alle Werte gesetzt sind. Kommen bei einem Update neue solche Einstellungen
  hinzu, sind sie auf bestehenden Installationen automatisch "ausstehend" und
  werden dadurch ebenfalls abgefragt.
- Organisationsname und Logo erscheinen im Anmeldebildschirm und in der Kopfzeile.
- Neue Konfigurationswerte `DEFAULT_ORG_NAME`, `DEFAULT_LOGO_FILE` und
  `INITIAL_ASSETS_HOST_PATH` (Standard-Mount `./config` -> `/app/initial`).

## 1.0.0

- Erste Version mit gepflegter Versionsnummer.
- Vereinheitlichte Verwaltungs-Apps je Betriebssystem (macOS, Windows, Linux):
  eine App/ein Skript pro System mit Statusübersicht (läuft/gestoppt, Version,
  Speicherbelegung, Adressen), Start-/Stopp-Knöpfen sowie einem versteckten
  "Erweitert"-Bereich für Erstinstallation/Update und Deinstallation - jeweils
  mit zusätzlicher Sicherheitsabfrage und (beim Löschen) individueller Abfrage
  je Datenkategorie. Ersetzt die bisherigen separaten Start-/Stop-/
  Installations-/Deinstallationsskripte.
- Erstinstallation/Update erkennt automatisch, ob bereits eine Installation
  vorhanden ist, und bietet dann die Wahl zwischen: Update (Daten bleiben
  erhalten), Neuinstallation mit Beibehaltung der Daten, oder Neuinstallation
  mit vollständigem Löschen der Daten.
