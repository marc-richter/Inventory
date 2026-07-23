# Änderungsprotokoll (Changelog)

Ab Version 1.0.0 wird für jede inhaltliche Änderung am Programm eine neue
Versionsnummer vergeben (Format: MAJOR.MINOR.PATCH). Die aktuelle Version steht
in der Datei `VERSION` im Projektordner. Die Verwaltungs-Apps (siehe
`installer/`) vergleichen diese Versionsnummer beim Erstinstallation/Update-Dialog
mit der Version, die zuletzt tatsächlich installiert/gestartet wurde, und zeigen
an, ob ein Update verfügbar ist.

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
