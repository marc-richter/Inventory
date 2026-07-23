---
title: "Benutzerhandbuch Inventarprogramm"
subtitle: "Inventarisierung von Kleidung und Ausrüstung"
date: "Stand: Juli 2026"
lang: de
---

# 1. Über dieses Programm

Das Inventarprogramm dient der Erfassung, Ausgabe und Rücknahme von Kleidung und
Ausrüstungsgegenständen in der Organisation. Es läuft als Webanwendung auf einem selbst
gehosteten Rechner im lokalen Netzwerk (Mac, Windows oder Linux) und ist von allen
Geräten im selben WLAN/LAN erreichbar — per Browser am Computer und als installierbare
App auf Android- und iOS-Smartphones.

Zentrale Funktionen:

- Gesamtübersicht aller Artikel mit Mehrfachfiltern und Volltextsuche
- Erstinventarisierung mit frei erweiterbaren Artikeltypen und Lagerorten
- Mengenerfassung: mehrere baugleiche Artikel auf einmal anlegen, inkl. Sammeldruck
  aller Etiketten und Listenexport der ganzen Charge
- Artikelnummern lassen sich überall per Gerätekamera scannen (QR-/Barcode)
- Ausgabe und Rücknahme von Artikeln mit dokumentierten Daten und vollständigem Verlauf
- Statuswechsel mit automatischer Abfrage notwendiger Zusatzangaben (z.B. bei Reparatur)
- Personenliste mit aktuellen und vergangenen Ausgaben je Person
- "Meine Artikel" für den schnellen persönlichen Überblick jedes Benutzers
- Fotodokumentation je Artikel
- Etikettendruck mit QR-Code für Brother-Labeldrucker, auch als Netzwerk-Direktdruck
- Export von Listen als CSV oder PDF, sowie Reimport mit Duplikat-Erkennung und
  Seite-an-Seite-Vergleich bestehender und importierter Daten
- Benutzerkonten mit einer oder mehreren Rollen gleichzeitig
- Eigenes Vereinslogo
- Manuelle und automatische Datensicherung (Backup)

Das Programm ist bewusst so aufgebaut, dass es über "Kleidung" hinaus später um
weitere Kategorien (z.B. technische Ausrüstung) erweitert werden kann, ohne dass
Vorhandenes verändert werden muss.

---

# 2. Voraussetzungen

- Ein Rechner (Mac, Windows oder Linux), der dauerhaft oder zumindest während der
  Nutzungszeiten eingeschaltet ist und im lokalen Netzwerk (WLAN/LAN) erreichbar ist
- Docker (wird bei Bedarf vom Installationsprogramm automatisch erkannt bzw. bei der
  Einrichtung geholfen)
- Alle Geräte, die das Programm nutzen sollen (weitere PCs, Smartphones), müssen sich
  im selben Netzwerk befinden

Ein Internetzugang ist für den laufenden Betrieb **nicht** erforderlich — lediglich für
die einmalige Installation (Herunterladen von Docker und den Programmbausteinen) sowie
für automatische Sicherheitsaktualisierungen des Betriebssystems.

---

# 3. Verwaltungs-App macOS

Für macOS gibt es **eine einzige Verwaltungs-App**, die Erstinstallation, Update,
Starten/Stoppen und Deinstallation in einer Oberfläche vereint.

1. Den Ordner `inventar` (z.B. aus dem freigegebenen Ordner) auf den Mac kopieren, der
   die Anwendung dauerhaft bereitstellen soll.
2. Im Unterordner `installer` die Datei **„Verwaltung-macOS.app“** per Doppelklick
   öffnen (alternativ „Verwaltung-macOS.command“).
3. Meldet macOS beim ersten Start eine Sicherheitswarnung („nicht verifizierter
   Entwickler“), im Finder mit der rechten Maustaste auf die Datei klicken, **„Öffnen“**
   wählen und die Sicherheitsabfrage bestätigen. Das ist nur beim allerersten Start nötig.
4. Es öffnet sich ein Terminal-Fenster mit einem Menü:

   ```
   1) Uebersicht anzeigen
   2) Starten
   3) Stoppen
   4) Erweitert (Erstinstallation/Update, Deinstallation)
   5) Beenden
   ```

**Uebersicht anzeigen** zeigt, ob die Anwendung installiert und/oder gestartet ist, die
installierte sowie die verfügbare Version (mit Hinweis auf ein Update), die Adressen im
lokalen Netz sowie die Speicherbelegung von Datenbank/Bildern, Backup-Ordner,
HTTPS-Zertifikaten und den gebauten Docker-Images.

**Starten/Stoppen** fahren die bereits eingerichtete Anwendung hoch bzw. herunter, ohne
neu zu bauen und ohne Daten zu verändern.

**Erweitert** ist absichtlich ein eigener Menüpunkt und fragt vor dem Öffnen extra
nach, ob dieser Bereich wirklich betreten werden soll. Darin:

- **Erstinstallation / Update:** Ist noch keine Installation vorhanden, fragt die App
  nach Administrator-Benutzername/-Passwort, Web- und HTTPS-Port sowie Backup-Verzeichnis
  (Enter = Standardwert), erzeugt automatisch ein selbstsigniertes HTTPS-Zertifikat
  (siehe Kapitel 6), baut und startet die Anwendung und öffnet sie im Browser. Besteht
  bereits eine Installation, erkennt die App das automatisch, zeigt installierte und
  verfügbare Version an und bietet die Wahl zwischen **Update** (Daten bleiben erhalten),
  **Neuinstallation mit Beibehaltung der Daten** oder **Neuinstallation mit vollständigem
  Löschen der Daten** (mit zusätzlicher, deutlich hervorgehobener Sicherheitsabfrage).
- **Deinstallation:** fragt ebenfalls zunächst extra nach, ob wirklich fortgefahren
  werden soll, stoppt und entfernt dann die Container und fragt anschließend **einzeln**
  nach, ob auch alle Daten (Datenbank, Bilder, Verlauf), der Backup-Ordner, die
  HTTPS-Zertifikate und die gebauten Docker-Images gelöscht werden sollen — standardmäßig
  bleibt alles erhalten. Der Projektordner selbst wird dabei nie gelöscht.

Am Ende von Start bzw. Erstinstallation zeigt das Fenster die Adresse für diesen Mac
sowie die Adressen, unter denen das Programm von Handys im selben WLAN erreichbar ist
(HTTP und HTTPS), zusammen mit den ersten Zugangsdaten. **Diese Angaben notieren!**

---

# 4. Verwaltungs-App Windows

Für Windows gibt es eine grafische Verwaltungs-App (ein echtes Fenster, keine reine
Kommandozeile), die Erstinstallation, Update, Starten/Stoppen und Deinstallation
vereint.

1. Den Ordner `inventar` auf den Windows-Rechner kopieren, der die Anwendung dauerhaft
   bereitstellen soll.
2. Im Unterordner `installer` die Datei **„Verwaltung-Windows.bat“** per Doppelklick
   ausführen.
3. Meldet Windows SmartScreen eine Warnung, auf **„Weitere Informationen“** und dann
   **„Trotzdem ausführen“** klicken (nur beim ersten Start nötig).
4. Es öffnet sich ein Fenster mit einer Übersicht (Status, installierte/verfügbare
   Version, Adressen, Speicherbelegung von Datenbank/Bildern, Backup-Ordner,
   Zertifikaten und Docker-Images) sowie den Knöpfen **„Starten“**, **„Stoppen“** und
   **„Aktualisieren“**.

Rechts oben befindet sich der zurückhaltend platzierte Knopf **„Erweitert“**, der einen
zusätzlichen Bereich einblendet:

- **„Erstinstallation / Update...“** fragt zunächst per Sicherheitsabfrage, ob dieser
  Bereich wirklich geöffnet werden soll. Ist noch keine Installation vorhanden, öffnet
  sich ein Formular für Administrator-Benutzername/-Passwort, Web- und HTTPS-Port sowie
  Backup-Verzeichnis; nach „Installieren“ baut und startet die App die Anwendung
  automatisch (inkl. selbstsigniertem HTTPS-Zertifikat, siehe Kapitel 6) und öffnet sie
  im Browser. Besteht bereits eine Installation, zeigt ein Dialog installierte und
  verfügbare Version und bietet drei Optionen: **Update** (Daten bleiben erhalten),
  **Neuinstallation — Daten behalten** oder **Neuinstallation — Daten löschen** (mit
  eigener, deutlich hervorgehobener Sicherheitsabfrage inkl. Option, auch den
  Backup-Ordner zu löschen).
- **„Deinstallation...“** fragt ebenfalls zunächst extra nach, ob der Bereich geöffnet
  werden soll, und zeigt danach ein Formular mit einzelnen Kontrollkästchen: alle Daten
  löschen (Datenbank, Bilder, Verlauf), davon abhängig zusätzlich Backup-Ordner und/oder
  HTTPS-Zertifikate löschen, sowie unabhängig davon die gebauten Docker-Images
  entfernen. Vor der eigentlichen Durchführung erscheint eine letzte Sicherheitsabfrage.

Der Fortschritt aller Aktionen (Starten, Stoppen, Installation, Update, Deinstallation)
wird live im Protokollbereich am unteren Fensterrand angezeigt; die Oberfläche bleibt
dabei durchgehend bedienbar.

---

# 5. Verwaltungs-App Linux

Für Linux gibt es ein einziges Verwaltungsskript mit Terminal-Menü, das Erstinstallation,
Update, Starten/Stoppen und Deinstallation vereint.

1. Den Ordner `inventar` auf den Linux-Rechner kopieren, der die Anwendung dauerhaft
   bereitstellen soll.
2. Im Unterordner `installer` die Datei **„verwaltung-linux.sh“** ausführbar machen
   (meist schon der Fall) und per Doppelklick starten, **oder** ein Terminal in diesem
   Ordner öffnen und Folgendes eingeben:
   ```bash
   ./verwaltung-linux.sh
   ```
   Je nach Desktop-Umgebung funktioniert alternativ auch ein Doppelklick auf
   „Verwaltung-Linux.desktop“. Falls das nicht reagiert, bitte den Terminal-Weg nutzen.
3. Es erscheint ein Menü:

   ```
   1) Uebersicht anzeigen
   2) Starten
   3) Stoppen
   4) Erweitert (Erstinstallation/Update, Deinstallation)
   5) Beenden
   ```

Die Menüpunkte entsprechen genau denen der macOS-App (siehe Kapitel 3): **Uebersicht**
zeigt Status, Version und Speicherbelegung; **Starten/Stoppen** fahren die Anwendung
hoch bzw. herunter, ohne Daten zu verändern; **Erweitert** fragt vor dem Öffnen extra
nach und enthält **Erstinstallation / Update** (inkl. automatischer Erkennung einer
bestehenden Installation mit Wahl zwischen Update, Neuinstallation mit Datenerhalt oder
Neuinstallation mit vollständigem Löschen) sowie **Deinstallation** (mit einzelner
Abfrage je Datenkategorie: Datenbank/Bilder/Verlauf, Backup-Ordner, HTTPS-Zertifikate,
Docker-Images).

Ist Docker auf dem Linux-Rechner noch nicht installiert, bietet das Skript im Bereich
„Erstinstallation / Update“ an, es automatisch über das offizielle
Docker-Installationsskript einzurichten (benötigt `sudo`). Nach der Docker-Installation
muss sich der Benutzer einmal ab- und wieder anmelden, danach das Menü erneut öffnen.

Am Ende von Start bzw. Erstinstallation zeigt das Fenster die Adresse für diesen
Rechner sowie die Adressen für Handys im selben Netzwerk (HTTP und HTTPS), zusammen mit
den ersten Zugangsdaten. **Notieren!**

---

# 6. HTTPS und Kamera-Scan

Damit sich Artikelnummern per QR-/Barcode direkt mit der Handykamera scannen lassen,
verlangen Browser aus Sicherheitsgründen eine verschlüsselte Verbindung (HTTPS) oder
den Aufruf über „localhost“. Aus diesem Grund wird bei jeder Installation bzw. jedem
Start automatisch ein sogenanntes selbstsigniertes Zertifikat erzeugt, und die
Anwendung ist zusätzlich unter einer `https://`-Adresse mit eigenem Port (Standard
`8443`) erreichbar.

Da dieses Zertifikat nicht von einer offiziell anerkannten Stelle bestätigt ist, zeigt
der Browser beim allerersten Aufruf dieser Adresse auf jedem Gerät eine Warnung, z.B.
„Verbindung ist nicht privat“ oder „Ihre Verbindung ist nicht sicher“. Das ist im
eigenen, lokalen Netzwerk unbedenklich und muss lediglich einmalig pro Gerät bestätigt
werden:

1. Auf **„Erweitert“** bzw. **„Details“** tippen
2. Danach **„Trotzdem fortfahren“** bzw. „Website besuchen“ auswählen

Über die normale `http://`-Adresse (ohne „s“) funktioniert die Anwendung weiterhin ganz
regulär — nur der Kamera-Scan steht dort aus technischen Gründen des Browsers nicht zur
Verfügung. Für alle anderen Funktionen (Übersicht, Ausgabe, Export usw.) spielt es
keine Rolle, ob HTTP oder HTTPS verwendet wird.

---

# 7. Erste Anmeldung

Nach der Installation im Browser die angezeigte Adresse aufrufen. Anmeldung mit dem
Administrator-Benutzernamen und dem bei der Installation vergebenen bzw. angezeigten
Passwort.

**Wichtig:** Direkt nach dem ersten Login unter **„Mein Konto“** ein persönliches
Passwort und/oder eine PIN vergeben, falls noch nicht geschehen, und für alle weiteren
Helferinnen und Helfer eigene Benutzerkonten anlegen (siehe Kapitel 19) — die
Administrator-Zugangsdaten sollten nicht dauerhaft im Alltag verwendet werden.

Die Anmeldung ist auf zwei Arten möglich:

- **Benutzername + Passwort** — klassische Anmeldung, z.B. am PC
- **Benutzername + PIN** — auf dem Handy erscheint automatisch ein Ziffernblock;
  gedacht für schnelle Anmeldung im Alltag (z.B. bei der Ausgabe im Lager)

Welche der beiden Möglichkeiten angeboten wird, hängt davon ab, was für das jeweilige
Konto hinterlegt ist (ein Konto kann auch beides haben).

---

# 8. Rollen und Berechtigungen

| Rolle | Übersicht | Erfassen | Ausgabe | Verwaltung |
|---|---|---|---|---|
| **Administrator** | ✓ | ✓ | ✓ | ✓ |
| **Materialverwalter** | ✓ | ✓ | ✓ | – |
| **Helfer** | ✓ | – | ✓ | – |
| **Nur-Lesend** | ✓ | – | – | – |

*Übersicht = Gesamtübersicht ansehen. Erfassen = Artikel und Stammdaten anlegen/bearbeiten.
Ausgabe = Ausgabe/Rücknahme durchführen. Verwaltung = Benutzerkonten und Einstellungen.*

Ein Benutzerkonto kann auch **mehrere Rollen gleichzeitig** besitzen (z.B. ein
Materialverwalter, der zusätzlich als Helfer im Lager mit anpackt). Es gilt dann jeweils
die Summe der Berechtigungen aller zugewiesenen Rollen.

Empfehlung: Für den Vorstand bzw. zur reinen Kontrolle/Auswertung eignet sich die Rolle
„Nur-Lesend“. Für Helferinnen und Helfer, die im Lager nur Kleidung ausgeben und
zurücknehmen sollen, reicht die Rolle „Helfer“ — sie können weder neue Artikeltypen noch
neue Artikel anlegen.

Ist ein Benutzerkonto zusätzlich mit einem Personendatensatz verknüpft (siehe
Kapitel 19), kann die betreffende Person unter „Meine Artikel“ jederzeit einsehen,
welche Artikel aktuell an sie persönlich ausgegeben sind (siehe Kapitel 15).

---

# 9. Gesamtübersicht und Filter

Die Startseite zeigt alle erfassten Artikel als Liste. Über das Filterfeld oberhalb der
Liste lässt sich einschränken nach:

- Freitextsuche (Artikelnummer, Bemerkungen, Beschädigungen)
- Kategorie, Typ, Abteilung, Lagerort — bei jedem dieser Filter können **mehrere Werte
  gleichzeitig** ausgewählt werden (z.B. „Abteilung 01“ und „Abteilung 02“ zusammen)
- Status (verfügbar, ausgegeben, in Reparatur, ausgemustert) — ebenfalls mehrfach
  auswählbar

Sobald mindestens ein Filter aktiv ist, erscheint der Knopf **„Alle Filter
zurücksetzen“**, mit dem sich die komplette Übersicht wieder mit einem Klick anzeigen
lässt.

Über das Kamera-Symbol neben dem Suchfeld lässt sich eine Artikelnummer direkt per
QR-/Barcode scannen — die passende Artikeldetailseite öffnet sich danach automatisch
(setzt HTTPS voraus, siehe Kapitel 6).

Ein Klick auf eine Artikelnummer in der Liste öffnet ebenfalls die Detailansicht des
Artikels.

---

# 10. Neuen Artikel erfassen (Erstinventarisierung)

Über „Neu erfassen“ (nur Administrator/Materialverwalter) wird ein neuer Artikel
angelegt:

1. **Kategorie** auswählen (Standard: „Kleidung“). Wird ein noch nicht vorhandener
   Name eingetippt, fragt das Programm nach, ob dieser neu angelegt werden soll.
2. **Typ** auswählen oder eintippen (z.B. Polo Shirt, T-Shirt, Hose, Jacke, Schuhe,
   Handschuhe). Auch hier erscheint bei einem neuen Typ automatisch die Rückfrage zur
   Neuanlage — so wächst die Typenliste mit dem tatsächlichen Bestand mit, ohne dass
   jemand vorher eine feste Liste pflegen muss.
3. **Artikelnummer** kann frei vergeben, per Kamera-Symbol eingescannt oder leer
   gelassen werden — dann wird automatisch eine fortlaufende Nummer erzeugt (Format
   `JAHR-00001`).
4. **Größe**, **Datum des Ersteintrags**, **Abteilung** (z.B. Abteilung 01 oder Abteilung 02) und
   **Lagerort** (z.B. „Lager A, Schrank 3“) ausfüllen — beides ist frei
   erweiterbar; bei einem neuen, noch nicht vorhandenen Namen fragt das Programm auch
   hier nach, ob dieser in die Stammdaten übernommen werden soll.
5. **Beschädigungen** und **Bemerkungen** ausfüllen.
6. Optional ein **Foto** direkt mit der Handykamera aufnehmen oder ein vorhandenes Bild
   auswählen.
7. Mit „Artikel anlegen“ speichern. In der Historie des Artikels ist danach jederzeit
   ersichtlich, wer ihn angelegt hat.

---

# 11. Mengenerfassung (mehrere Artikel auf einmal anlegen)

Müssen mehrere baugleiche Artikel erfasst werden (z.B. eine neue Lieferung von 30
identischen T-Shirts derselben Größe), muss nicht jeder Artikel einzeln über „Neu
erfassen“ angelegt werden. Über **„Mengenerfassung“** (nur Administrator/Materialverwalter)
lässt sich das in einem Arbeitsschritt erledigen:

1. Die gemeinsamen Angaben einmal ausfüllen: **Kategorie**, **Typ**, **Größe**,
   **Abteilung**, **Lagerort**, **Beschädigungen**, **Bemerkungen** und **Datum des
   Ersteintrags** — diese gelten für alle auf einmal angelegten Artikel gleichermaßen.
2. Bei den **Artikelnummern** zwischen zwei Modi wählen:
   - **Automatisch vergeben**: einfach die gewünschte **Anzahl** eingeben (z.B. 30) —
     das Programm erzeugt automatisch ebenso viele fortlaufende Artikelnummern
     (Format `JAHR-00001`, `JAHR-00002`, ...).
   - **Manuell / Scannen**: die Artikelnummern werden von Hand eingetippt (eine Nummer
     je Zeile) oder nacheinander über das Kamera-Symbol eingescannt — praktisch, wenn
     die Artikel bereits vom Hersteller oder Lieferanten mit eigenen Nummern oder
     Barcodes versehen sind. Jede eingescannte Nummer wird automatisch als neue Zeile
     ergänzt.
3. Mit „Artikel anlegen“ werden alle Artikel auf einmal gespeichert.

Nach dem Speichern erscheint eine Ergebnisliste mit allen neu angelegten
Artikelnummern dieser Charge sowie direkten Aktionen dafür:

- **„Alle Etiketten drucken (PDF)“** erzeugt eine einzige Sammel-PDF mit einer Seite je
  Etikett (QR-Code + Artikelnummer), zum En-bloc-Ausdrucken auf dem Etikettendrucker,
  statt jedes Etikett einzeln öffnen zu müssen
- **„Direktdruck (Netzwerk)“** sendet dieselbe Sammel-PDF direkt an einen im WLAN/LAN
  eingebundenen Brother-Drucker (siehe Kapitel 18 zu den Einschränkungen bei
  USB/Bluetooth-Druckern)
- **„Liste als CSV“** bzw. **„Liste als PDF“** exportiert genau die Artikel dieser
  Charge als Tabelle, z.B. zur Weitergabe an die Kassenprüfung oder als Lieferschein-Beleg

Jeder einzelne Artikel aus der Charge lässt sich anschließend ganz normal über die
Gesamtübersicht oder per Klick in der Ergebnisliste öffnen und wie gewohnt bearbeiten,
ausgeben oder zurücknehmen.

---

# 12. Artikeldetails, Bilder und Status

Auf der Detailseite eines Artikels stehen zur Verfügung:

- Alle Bilder des Artikels sowie die Möglichkeit, weitere Fotos hinzuzufügen
- Alle Stammdaten (Typ, Größe, Abteilung, Lagerort, Beschädigungen, Bemerkungen) — der
  Lagerort lässt sich direkt hier ändern, inklusive Neuanlage-Rückfrage bei neuen Orten
- Wer den Artikel ursprünglich angelegt hat
- Der aktuelle **Status**: verfügbar, ausgegeben, in Reparatur, ausgemustert

Über **„Status ändern“** (Administrator/Materialverwalter) öffnet sich ein Dialog, der
automatisch die passenden Zusatzangaben abfragt: Wird z.B. der Status **„In
Reparatur“** gewählt, fragt das Programm zusätzlich nach dem **Grund der Reparatur**
(Pflichtfeld) und dem **voraussichtlichen Rückgabedatum**. Diese Angaben werden auf der
Detailseite angezeigt, solange sich der Artikel in Reparatur befindet.

Zum Etikettendruck stehen zwei Knöpfe zur Verfügung, siehe Kapitel 18.

---

# 13. Ausgabe und Rücknahme

Ist ein Artikel verfügbar, kann er über den Knopf **„Artikel ausgeben“** an eine Person
ausgegeben werden. Der Empfänger wird entweder aus den vorhandenen Personen-Stammdaten
ausgewählt oder — falls die Person dort noch nicht existiert — direkt im
Ausgabe-Dialog neu angelegt (mit Rückfrage, ob der neue Name in die Stammdaten
übernommen werden soll) oder alternativ als reiner Freitext eingetragen, ohne einen
Stammdatensatz anzulegen. Zusätzlich lässt sich das **Ausgabedatum** eintragen bzw.
anpassen (Standard: heute). Der Artikel wechselt daraufhin automatisch in den Status
„ausgegeben“.

Wird derselbe Artikel später zurückgegeben, öffnet sich auf der Detailseite die
Rücknahme-Funktion: Das **Rückgabedatum** lässt sich ebenfalls dokumentieren bzw.
anpassen, optional lässt sich der Zustand bei Rückgabe vermerken (z.B. bei
Beschädigungen), danach wechselt der Artikel automatisch zurück auf „verfügbar“.

Unter **„Offene Ausgaben“** in der Navigation lassen sich alle aktuell ausgegebenen
Artikel auf einen Blick einsehen — mit denselben Informationen wie in der
Gesamtübersicht (Typ, Größe, Abteilung, Lagerort) sowie zusätzlich Empfänger und
Ausgabedatum, und ebenfalls mit Mehrfachfiltern und Reset-Knopf.

---

# 14. Verlauf eines Artikels

Jede Detailseite zeigt eine vollständige Tabelle aller bisherigen Ausgabe- und
Rücknahmevorgänge dieses Artikels: Datum der Ausgabe, Datum der Rücknahme, Empfänger
sowie Bemerkungen. So lässt sich für jeden Artikel jederzeit nachvollziehen, wer ihn
wann hatte.

---

# 15. Personen und "Meine Artikel"

Unter **„Personen“** in der Navigation (Administrator/Materialverwalter) steht eine
Liste aller erfassten Personen (z.B. Mitglieder, denen Kleidung ausgegeben wird) zur
Verfügung:

- Neue Personen lassen sich direkt anlegen (Vorname, Nachname, optional Abteilung)
- Bestehende Personen lassen sich umbenennen bzw. der Abteilung neu zuordnen
  ("Bearbeiten") oder entfernen — hat eine Person bereits eine Ausgabe-Historie oder ist
  mit einem Benutzerkonto verknüpft, wird sie aus Nachvollziehbarkeitsgründen nur
  deaktiviert statt endgültig gelöscht
- Über **„Details anzeigen“** wird je Person angezeigt, welche Artikel sie **aktuell**
  ausgegeben hat; eine ausklappbare Historie („Vergangene Ausgaben anzeigen“) zeigt
  darunter alle früheren, bereits zurückgegebenen Ausgaben dieser Person

Jedes Benutzerkonto kann optional mit einem solchen Personendatensatz verknüpft werden
(siehe Kapitel 19). Ist das der Fall, sieht die betreffende Person unter **„Meine
Artikel“** in der Navigation ausschließlich die Artikel, die aktuell an sie persönlich
ausgegeben sind — das ist besonders für Helferinnen und Helfer gedacht, die auf diesem
Weg jederzeit selbst nachsehen können, was sie gerade in ihrer Obhut haben, ohne
Einblick in die Daten anderer Personen zu erhalten.

---

# 16. Export als CSV und PDF

In der Gesamtübersicht stehen oben rechts zwei Export-Knöpfe zur Verfügung:

- **CSV Export** — für die Weiterverarbeitung in Excel/Calc (z.B. für Inventurlisten
  oder Kassenprüfungen)
- **PDF Export** — eine formatierte, druckfertige Liste

Beide Exporte berücksichtigen die aktuell gesetzten Filter — es kann also z.B. gezielt
nur die Liste aller Jacken einer Abteilung oder nur die Liste aller ausgegebenen Artikel
exportiert werden.

---

# 17. CSV-Import (Reimport exportierter Daten)

Über **„Import“** in der Navigation (Administrator/Materialverwalter) lässt sich eine
zuvor über „CSV Export“ (siehe Kapitel 16) erzeugte Datei wieder in das Programm
einlesen — z.B. nach einer externen Bearbeitung in Excel, oder um eine größere Liste
von Artikeln auf einmal zu übernehmen.

1. Datei auswählen und auf **„Datei analysieren“** klicken. Dabei wird noch **nichts**
   in der Datenbank verändert — es handelt sich zunächst nur um eine Vorschau.
2. Das Programm zeigt eine Übersicht: wie viele Zeilen als **neue Artikel** angelegt
   würden, wie viele Artikelnummern **bereits existieren** (Duplikate) und wie viele
   Zeilen **fehlerhaft** sind (z.B. weil Kategorie oder Typ fehlen).
3. Für jedes gefundene Duplikat werden der **bestehende** und der **importierte**
   Datensatz Feld für Feld nebeneinander dargestellt (über „Vergleich anzeigen“) —
   abweichende Werte werden hervorgehoben, damit auf einen Blick erkennbar ist, was
   sich unterscheidet. Pro Duplikat lässt sich auswählen:
   - **„Bestehend behalten“** — der Datensatz in der Datenbank bleibt unverändert
   - **„Importiert übernehmen“** — die Werte aus der Datei überschreiben den
     bestehenden Datensatz
4. Diese Entscheidung lässt sich entweder **für jedes Duplikat einzeln** treffen, oder
   über die Schaltflächen **„Bestehende Daten behalten (alle)“** bzw. **„Importierte
   Daten übernehmen (alle)“** mit einem Klick auf alle gefundenen Duplikate gleichzeitig
   anwenden — einzelne Duplikate lassen sich danach bei Bedarf weiterhin abweichend
   einstellen.
5. Mit **„Import durchführen“** werden neue Artikel angelegt und Duplikate
   entsprechend der getroffenen Auswahl übernommen oder unverändert gelassen.
   Fehlerhafte Zeilen werden dabei automatisch übersprungen.

Kategorien, Typen, Abteilungen oder Lagerorte, die in der Datei stehen, in den
Stammdaten aber noch nicht vorhanden sind, werden beim Import automatisch neu angelegt
— ähnlich wie bei der Neuanlage-Rückfrage in der normalen Erfassung, nur ohne
Einzelabfrage je Zeile, da ein Import in der Regel viele Zeilen auf einmal umfasst.

---

# 18. Etiketten drucken (Brother-Labeldrucker)

Auf der Artikel-Detailseite stehen zwei Möglichkeiten zur Verfügung:

- **„Etikett drucken (PDF)“** erzeugt ein PDF mit QR-Code (der die Artikelnummer
  enthält) sowie Typ und Größe im Klartext. Dieses PDF öffnet sich in einem neuen
  Fenster und kann über den normalen Systemdruckdialog auf einem Brother-Labeldrucker
  ausgedruckt werden — zum anschließenden Aufbügeln oder Aufkleben auf dem
  Kleidungsstück. Dieser Weg funktioniert unabhängig davon, ob der Drucker per USB,
  Bluetooth oder Netzwerk am jeweiligen Gerät angeschlossen ist.
- **„Direktdruck (Netzwerk)“** sendet das Etikett ohne Umweg über den Druckdialog
  direkt an einen im WLAN/LAN eingebundenen Brother-Drucker (siehe Kapitel 21 zur
  Einrichtung der Drucker-IP-Adresse). Das funktioniert nur bei netzwerkfähigen
  Druckern und ist modellabhängig — schlägt es fehl, bitte auf den PDF-Weg
  ausweichen. Bei rein per USB oder Bluetooth angeschlossenen Druckern ist der
  PDF-Weg ohnehin der einzig mögliche, da ein im Container laufender Server solche
  direkt an einem PC/Handy angeschlossenen Geräte technisch nicht ansprechen kann.

Das Etikettenformat (Breite/Höhe in Millimetern) lässt sich unter
**Einstellungen → Etiketten & Drucker** an das tatsächlich verwendete
Brother-Etikettenband anpassen; gängige Brother-DK-Formate stehen als Vorlage zur
Auswahl.

---

# 19. Benutzerkonten verwalten (Administrator)

Unter **Einstellungen → Benutzer** kann ein Administrator:

- neue Benutzerkonten anlegen (Benutzername, Name, eine oder mehrere Rollen, optional
  Verknüpfung mit einer Person für „Meine Artikel“, optional Passwort und/oder PIN)
- die Standard-PIN-Länge für neue Konten festlegen (4 bis 8 Ziffern)
- bestehende Konten vollständig **bearbeiten**: Name, Rollen (mehrere gleichzeitig
  möglich), verknüpfte Person, PIN-Länge sowie bei Bedarf ein neues Passwort/eine
  neue PIN vergeben
- bestehende Konten deaktivieren/wieder aktivieren oder löschen (eigenes Konto kann
  nicht gelöscht werden)

Jedes Konto kann sowohl ein Passwort als auch eine PIN besitzen — praktisch z.B. wenn
dieselbe Person sowohl am PC (Passwort) als auch auf dem Handy (PIN) arbeitet.

---

# 20. Eigenes Passwort/PIN ändern

Jeder angemeldete Benutzer kann unter **„Mein Konto“**:

- die eigene PIN ändern (Eingabe der alten PIN, danach zweimal die neue PIN — die
  Länge ist durch den Administrator vorgegeben)
- das eigene Passwort ändern

---

# 21. Stammdaten verwalten (Kategorien, Typen, Abteilung, Lagerorte, Logo, Drucker)

Unter **Einstellungen → Stammdaten** (nur Administrator) lassen sich unabhängig von der
laufenden Erfassung Kategorien, Typen, Abteilungen und Lagerorte anlegen,
**umbenennen** und **löschen** — Löschen ist jeweils nur möglich, solange kein Artikel
(bzw. bei Kategorien: kein Typ) den betreffenden Eintrag mehr verwendet. Das ist
derselbe Mechanismus, der beim Erfassen eines Artikels über die Neuanlage-Rückfrage
automatisch greift — hier lässt er sich zusätzlich zentral pflegen.

Personen werden über die eigene Seite **„Personen“** verwaltet (siehe Kapitel 15),
da dort zusätzlich die Ausgabe-Historie je Person sichtbar ist.

Unter **Einstellungen → Etiketten & Drucker** lässt sich außerdem:

- ein **eigenes Organisationslogo** hochladen (PNG, JPEG, WEBP oder SVG) — es
  erscheint danach im Anmeldebildschirm und in der Kopfzeile der Anwendung
- die **Drucker-Verbindung** für den Etiketten-Direktdruck einrichten: Verbindungsart
  (kein Direktdruck / Netzwerk / USB-Bluetooth), bei Netzwerkdruckern zusätzlich die
  IP-Adresse des Brother-Druckers (siehe Kapitel 18)

---

# 22. Backup und Wiederherstellung

Unter **Einstellungen → Backup**:

- **Manuell sichern:** Knopf „Jetzt manuell sichern“ erstellt sofort eine Sicherung
  (Datenbank und alle Bilder) als ZIP-Datei
- **Automatisch sichern:** Aktivieren und eine tägliche Uhrzeit festlegen — die
  Sicherung läuft dann selbstständig im Hintergrund
- **Zielverzeichnis:** Standardmäßig der Ordner `backups` neben der Anwendung; über
  die Datei `.env` (`BACKUP_HOST_PATH`) lässt sich dieser auf einen beliebigen Pfad
  legen, z.B. eine externe Festplatte oder ein NAS
- **Aufbewahrung:** Es lässt sich festlegen, wie viele Backups aufbewahrt werden
  (Standard: 30); ältere werden automatisch gelöscht
- Fertige Backups können über die Liste heruntergeladen werden

**Wiederherstellung** eines Backups erfolgt derzeit durch einen Administrator über die
technische Schnittstelle (`/api/backup/restore`) mit anschließendem Neustart der
Anwendung. Bei Bedarf hierzu bitte Rücksprache mit der technisch verantwortlichen
Person halten.

---

# 23. Nutzung auf dem Handy als App

1. Auf dem Smartphone (Android oder iOS) im Browser (Chrome bzw. Safari) die Adresse
   des Inventarprogramms aufrufen (siehe Installationsprotokoll bzw. bei der
   zuständigen Person erfragen). Für den Kamera-Scan von Barcodes bitte die
   `https://`-Adresse verwenden (siehe Kapitel 6).
2. Im Browsermenü **„Zum Home-Bildschirm hinzufügen“** (iOS) bzw. **„App installieren“**
   (Android) auswählen
3. Die Anwendung erscheint danach als eigenes Icon auf dem Home-Bildschirm und startet
   wie eine normale App, ohne Adressleiste

Das Handy muss sich dafür im selben WLAN wie der Hosting-Rechner befinden.

---

# 24. Fehlerbehebung und häufige Fragen

**Die Seite ist auf dem Handy nicht erreichbar.**
Prüfen, ob sich das Handy im selben WLAN wie der Hosting-Rechner befindet und ob die
im Installationsprotokoll angezeigte Adresse (z.B. `http://192.168.1.20:8080`)
korrekt eingegeben wurde.

**Der Browser warnt beim Aufruf der HTTPS-Adresse vor einem unsicheren Zertifikat.**
Das ist normal, siehe Kapitel 6: einfach „Erweitert“ → „Trotzdem fortfahren“ wählen.
Das ist nur einmalig pro Gerät nötig.

**Der Kamera-Scan funktioniert nicht.**
Kamera-Scan benötigt eine `https://`-Verbindung (siehe Kapitel 6) sowie eine im
Browser erteilte Kamera-Berechtigung. Bitte prüfen, ob die Adresse mit `https://`
begonnen wurde und ob die Website-Berechtigungen des Browsers den Kamerazugriff
erlauben.

**Nach einem Neustart des Rechners ist die Anwendung nicht mehr erreichbar.**
Docker Desktop muss laufen bzw. auf Linux-Servern der Docker-Dienst gestartet sein.
Docker startet die Container in der Regel automatisch neu, sobald der Dienst läuft
(„restart: unless-stopped“) — es kann nach einem Neustart kurz dauern, bis alles
wieder hochgefahren ist.

**Ich habe mein Passwort/meine PIN vergessen.**
Ein Administrator kann unter Einstellungen → Benutzer ein neues Passwort bzw. eine
neue PIN für das betroffene Konto vergeben.

**Ein Typ, eine Abteilung oder ein Lagerort wurde versehentlich falsch angelegt.**
Unter Einstellungen → Stammdaten lässt sich der jeweilige Eintrag umbenennen oder
entfernen, solange ihn kein Artikel mehr verwendet.

**Der Netzwerk-Direktdruck des Etiketts funktioniert nicht.**
Das ist modellabhängig und nur bei netzwerkfähigen Brother-Druckern möglich. Bitte
prüfen, ob die hinterlegte IP-Adresse stimmt und der Drucker im selben Netzwerk
erreichbar ist. Als zuverlässige Alternative steht immer der PDF-Weg über den
normalen Systemdruckdialog zur Verfügung.

**Was passiert, wenn der Hosting-Rechner ausfällt?**
Ohne aktuelles Backup gehen die seit der letzten Sicherung erfassten Änderungen
verloren. Es wird dringend empfohlen, die automatische Sicherung zu aktivieren und
das Backup-Verzeichnis regelmäßig auf ein separates Speichermedium zu übertragen.

---

# 25. Datenschutzhinweise

Das Programm erfasst unter anderem, welche Person welchen Kleidungsartikel erhalten
hat. Da unter den erfassten Personen auch Minderjährige sein können, gilt:

- Zugriff auf die Anwendung sollte nur den tatsächlich benötigten Personen mit
  eigenem Konto und angemessener Rolle gewährt werden
- Die Anwendung läuft ausschließlich im lokalen Netzwerk und ist nicht über das
  Internet erreichbar, solange sie nicht bewusst dafür freigegeben wird
- Regelmäßige Backups sollten sicher (z.B. verschlüsselt) aufbewahrt werden
- Nicht mehr benötigte Personendaten (z.B. ausgeschiedene Mitglieder) sollten
  regelmäßig bereinigt werden

Dieses Handbuch stellt keine Rechtsberatung dar. Bei Fragen zur
datenschutzkonformen Nutzung empfiehlt sich Rücksprache mit einer bzw. einem
Datenschutzbeauftragten.
