# Projekt-Durchsicht: Laufzeit-, UX- und Verbesserungsanalyse

Stand: v1.35.0 · Betrieb auf einem Raspberry Pi (SQLite, FastAPI-Backend, React/Vite-Frontend hinter nginx).

Dieses Dokument fasst zusammen, was in dieser Durchsicht bereits umgesetzt wurde, und
listet danach – nach Wirkung und Aufwand geordnet – Vorschläge für weitere
Verbesserungen. Der Fokus liegt auf spürbar besserer Bedienung („UX") bei gleichzeitig
geringer Last für den kleinen Server.

## Teil 1 – In dieser Durchsicht umgesetzt

**Datenbank-Indizes für die häufigsten Filter und Verknüpfungen.** Die Tabelle
`articles` wird ständig nach Kategorie, Typ, Status, Standort-Knoten und „vorläufig"
gefiltert, `issue_records` nach Artikel und Person. Auf diese Spalten wurden Indizes
gelegt (für neue Installationen im Modell, für bestehende Datenbanken idempotent per
`CREATE INDEX IF NOT EXISTS` in der Start-Migration). SQLite muss dadurch bei jeder
Übersicht, Auswertung und Ausgabe nicht mehr die gesamte Tabelle durchsuchen – der
Effekt wächst mit dem Bestand.

**Beseitigung von N+1-Datenbankabfragen bei der Artikel-Auslieferung.** Die
Artikel-Übersicht ist der am häufigsten aufgerufene Endpunkt (sie aktualisiert sich
automatisch). Pro Artikel wurden bisher zusätzliche Abfragen ausgelöst – für den
Lagerort-Pfad (die gesamte Eltern-Kette des Standort-Baums), für „vorläufig von" und für
„zur Prüfung zugewiesen". Jetzt werden diese Beziehungen gebündelt geladen und der
(kleine) Standort-Baum einmal pro Anfrage vorgeladen; die Pfad-Berechnung liest die
Eltern danach ohne weitere Abfragen. Aus vielen hundert kleinen Abfragen pro Seitenaufruf
werden eine Handvoll. Dieselbe Optimierung greift jetzt auch beim CSV-/PDF-Export und in
der Typ-Übersicht „nach Standort".

**Schrittfortschritt der geführten Inventur effizienter berechnet.** Die Kennzahlen je
Station bauen den Standort-Baum jetzt nur noch einmal auf statt einmal pro Station.

**Weniger unnötige Netzlast durch sichtbarkeitsgesteuertes Aktualisieren.** Alle
Live-Aktualisierungen (Übersicht alle 8 s, Inventur und Artikeldetail alle 8–10 s) pausieren
jetzt, sobald der Tab im Hintergrund liegt, und holen beim Zurückkehren sofort einmal den
aktuellen Stand. Das entlastet den Pi genau dann, wenn niemand hinschaut – ein offenes,
aber ungenutztes Tablet erzeugt keine Dauerlast mehr.

**Kompression und Dauer-Caching im Webserver.** nginx komprimiert jetzt HTML, JavaScript,
CSS und JSON (gzip) und liefert die gehashten Build-Dateien mit langem Cache aus. Der erste
Seitenaufruf überträgt deutlich weniger Daten, Folgeaufrufe laden das Programm gar nicht
mehr neu herunter. Das ist besonders über WLAN/Mobilfunk und auf dem Pi spürbar.

## Teil 2 – Weitere Vorschläge, nach Wirkung geordnet

### Hohe Wirkung, geringer Aufwand

**Fortschritt in der Inventur-Liste bündeln.** Die Kampagnen-Liste berechnet den
Fortschritt aktuell je Kampagne mit einer eigenen Abfrage. Solange es wenige Kampagnen
gibt, ist das unkritisch; bei vielen abgeschlossenen Inventuren summiert es sich. Ein
gemeinsamer Zähl-Query über alle aktiven Kampagnen (oder das Ausblenden abgeschlossener
Inventuren aus der Standardliste, mit „ältere anzeigen") wäre eine einfache Entlastung.

**Code-Aufteilung des Frontends (Lazy Loading).** Derzeit wird die gesamte Oberfläche als
ein Bündel geladen. Große, selten genutzte Seiten (Einstellungen, Auswertungen, Inventur)
ließen sich per `React.lazy` erst bei Bedarf nachladen. Das verkürzt den ersten Start
merklich, gerade auf älteren Tablets.

**„WAL"-Modus für SQLite.** Mit `PRAGMA journal_mode=WAL` können mehrere Nutzer
gleichzeitig lesen, während einer schreibt – das reduziert kurze Hänger bei paralleler
Nutzung (mehrere Helfer während der Inventur). Einmalig beim Start zu setzen, sehr geringes
Risiko.

**Serverseitige Paginierung / „mehr laden" bei sehr großem Bestand.** Die Übersicht lädt
alle Artikel auf einmal. Bis einige Tausend Artikel ist das vertretbar; darüber hinaus
lohnt sich Nachladen in Blöcken (oder eine reine Zähl-/Suchansicht), damit die Seite auch
bei großem Bestand sofort reagiert.

### Hohe Wirkung, mittlerer Aufwand

**Automatische Tests für die Kernabläufe.** Ausgabe/Rücknahme, Rechteprüfung, Inventur-
Fortschritt und die DSGVO-Funktionen (Auskunft/Anonymisierung) sind die kritischen Pfade.
Einige wenige automatisierte Tests (pytest) würden Regressionen früh abfangen – gerade weil
das Programm laufend erweitert wird. Ergänzend im Frontend ein Smoke-Test des Seitenaufbaus.

**Offline-Fähigkeit der Inventur.** Im Keller oder in der Fahrzeughalle ist das WLAN oft
schwach. Wenn die Scans lokal zwischengespeichert und beim Wiederverbinden gesammelt
gesendet würden (die PWA-Grundlage ist vorhanden), bräche die Inventur bei Funklöchern
nicht ab.

**Konsolidierte Benachrichtigungs-Zustellung.** Telegram-Nachrichten werden aktuell direkt
im Anfrage-Ablauf versendet. Eine kleine Warteschlange (Hintergrund-Versand mit
Wiederholung) macht Aktionen für den Nutzer schneller und robust gegen kurzzeitige
Telegram-Störungen.

### Mittlere Wirkung

**Bilder in mehreren Größen vorhalten.** Thumbnails werden bereits zwischengespeichert;
zusätzlich könnten Uploads einmalig in eine begrenzte Maximalgröße gerechnet werden, um
Speicher auf dem Pi zu sparen und die Detailansicht zu beschleunigen.

**Einheitliche Fehler- und Ladezustände im Frontend.** Ein gemeinsames Muster für „lädt",
„Fehler", „leer" (statt vereinzelter Meldungen) macht die Bedienung ruhiger und
vorhersehbarer.

**Tastatur- und Barrierearmut.** Durchgängige Fokus-Reihenfolge, Beschriftungen für
Screenreader und sichtbare Fokus-Ringe erhöhen die Zugänglichkeit – wichtig, wenn das
Programm im Verein von vielen unterschiedlichen Personen bedient wird.

### Betrieb und Sicherheit (begleitend)

**Backups regelmäßig prüfen.** Die automatische Sicherung existiert; ein gelegentlicher
Test-Rückspielvorgang stellt sicher, dass sie im Ernstfall auch trägt.

**Ressourcen-Beobachtung auf dem Pi.** Ein einfacher Blick auf CPU-/Speicherlast (bzw. ein
kleiner Health-Endpunkt mit Kennzahlen) hilft, Engpässe früh zu erkennen, bevor Nutzer sie
als „langsam" bemerken.

**Rate-Limit auch für weitere schreibende Endpunkte.** Der Login ist bereits gegen
Brute-Force geschützt; ein moderates Limit auf andere schreibende Aktionen wäre eine
sinnvolle Ergänzung.

## Priorisierte Kurzliste (Empfehlung)

Als nächste Schritte mit dem besten Verhältnis aus Nutzen und Aufwand: WAL-Modus für
SQLite aktivieren, das Frontend per Lazy Loading aufteilen und die Inventur-Liste beim
Fortschritt entlasten. Danach lohnen sich automatische Tests für die Kernabläufe und die
Offline-Fähigkeit der Inventur.
