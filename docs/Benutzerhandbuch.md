---
title: "Benutzerhandbuch Inventarprogramm"
subtitle: "Inventarisierung von Kleidung und Ausrüstung"
date: "Stand: September 2026"
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
   4) Selbsttest (prueft, ob alles laeuft)
   5) Protokoll ansehen (bei Problemen)
   6) Erweitert (Erstinstallation/Update, Deinstallation)
   7) Autostart ein-/ausschalten
   8) Beenden
   ```

**Uebersicht anzeigen** zeigt, ob die Anwendung installiert und/oder gestartet ist, die
installierte, die verfügbare und die **laufende** Version (die der Server selbst meldet),
einen Hinweis auf verfügbare Updates, die Adressen im lokalen Netz sowie die
Speicherbelegung von Datenbank/Bildern, Backup-Ordner, HTTPS-Zertifikaten und den
gebauten Docker-Images.

Die laufende Version ist wichtig: nur sie sagt, was der Server *tatsächlich* ausführt.
Weicht sie von der verfügbaren Version ab, wurden neue Programmdateien zwar kopiert,
aber noch nicht übernommen — dann fehlt ein „Erstinstallation / Update".

**Starten/Stoppen** fahren die bereits eingerichtete Anwendung hoch bzw. herunter, ohne
neu zu bauen und ohne Daten zu verändern.

**Selbsttest** prüft der Reihe nach alles, was erfahrungsgemäß schiefgeht: läuft Docker,
gibt es eine Installation, laufen die Container, antwortet der Server, passt die laufende
Version zu den Programmdateien, ist genug Platz frei, gibt es aktuelle Sicherungen, ist
das HTTPS-Zertifikat gültig, stehen Fehler im Protokoll. Zu jedem Punkt steht in einem
Satz, was zu tun ist. Das ist der erste Griff, wenn jemand sagt „es geht nicht".

**Protokoll ansehen** zeigt die Meldungen des Servers — dort steht bei einem Problem fast
immer der Grund. Wählbar sind die letzten 100 Zeilen, nur Fehler und Warnungen, ein
Live-Mitlesen sowie „in eine Datei schreiben", um sie weiterzugeben. Diese Datei enthält
Server-Meldungen und sollte vor dem Weitergeben kurz durchgesehen werden.

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
4. Es öffnet sich ein Fenster mit einer Übersicht (Status, installierte, verfügbare und
   laufende Version, Adressen, Speicherbelegung von Datenbank/Bildern, Backup-Ordner,
   Zertifikaten und Docker-Images) sowie den Knöpfen **„Starten“**, **„Stoppen“** und
   **„Aktualisieren“**.

In der zweiten Knopfreihe stehen **„Selbsttest“** und **„Protokoll ansehen“** — dieselben
Prüfungen und dieselbe Protokollansicht wie unter macOS und Linux (siehe Kapitel 3), nur
als Fenster. Der Selbsttest sagt zu jedem Punkt in einem Satz, was zu tun ist; die
Protokollansicht lässt sich auf Fehler und Warnungen einschränken und in eine Datei
speichern.

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
wird live im Bereich **„Ablauf der Aktionen“** am unteren Fensterrand angezeigt; die
Oberfläche bleibt dabei durchgehend bedienbar. Nicht zu verwechseln mit „Protokoll
ansehen“ — dort stehen die Meldungen des Servers.

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
   4) Selbsttest (prueft, ob alles laeuft)
   5) Protokoll ansehen (bei Problemen)
   6) Erweitert (Erstinstallation/Update, Deinstallation)
   7) Autostart ein-/ausschalten
   8) Beenden
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


## Eigenes Zertifikat hinterlegen

Wer ein eigenes Zertifikat hat — vom Verein, aus einer internen Zertifizierungsstelle
oder von Let's Encrypt —, kann es unter **Einstellungen → Sicherheit → HTTPS-Zertifikat**
hinterlegen. Danach entfällt die Browser-Warnung.

Angenommen werden beide üblichen Formen: Zertifikat, Schlüssel und Zwischenzertifikat als
drei einzelne Dateien, oder eine PEM-Datei, die Zertifikat und Schlüssel zusammen
enthält. Der private Schlüssel darf nicht mit einem Passwort geschützt sein.

Vor dem Übernehmen prüft das Programm, ob die Dateien lesbar sind, ob der Schlüssel zum
Zertifikat gehört und wie lange es noch gilt — ein unpassendes Zertifikat würde den
Web-Teil beim Neustart lahmlegen. Der Knopf **„Nur prüfen"** zeigt das Ergebnis, ohne
etwas zu ändern. Das bisherige Zertifikat wird vor dem Überschreiben zur Seite gelegt.

Nach dem Übernehmen startet der Web-Teil selbsttätig neu; die Seite ist dabei ein paar
Sekunden nicht erreichbar. Das setzt voraus, dass in der Verwaltungs-App
**„Server-Aus/Neustart per Web"** eingerichtet ist. Ist es das nicht, sagt die Meldung
das — dann genügt in der Verwaltungs-App „Stoppen" und „Starten".

Die aktuelle Karte zeigt jederzeit, für welche Namen das Zertifikat gilt, wer es
ausgestellt hat, wie lange es noch läuft und seinen Fingerabdruck.
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

## Zuständigkeit von Materialverwaltern

Einem Materialverwalter lässt sich eine **Zuständigkeit** zuweisen (Abteilung und/oder
Materialklasse) — unter Auswertung → Materialverantwortliche. Ist eine Abteilung
hinterlegt, sieht er nur noch **deren Material**: in der Übersicht, beim Einzelabruf und
beim Scannen einer Nummer.

Zwei Dinge sind dabei bewusst so gelöst:

- **Personen bleiben für alle sichtbar.** Material wird bei Einsätzen
  abteilungsübergreifend ausgegeben; wer nur die eigenen Leute sähe, könnte die Ausgabe
  nicht mehr erledigen.
- **Material ohne Abteilung bleibt sichtbar.** Sonst verschwände noch nicht zugeordnetes
  Material klaglos aus der Übersicht.

Wer **gar keine** Zuständigkeit hinterlegt hat, sieht wie bisher alles.

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

## Dokumente: Pflege, Desinfektion, Bedienungsanleitung

Zu jedem Artikel lassen sich PDF-Dokumente hinterlegen — Pflegehinweis,
Desinfektionshinweis, Bedienungsanleitung, Sicherheitsdatenblatt, Prüfvorschrift,
Nachweis oder Zertifikat. Sie stehen in der Artikelansicht in der Karte **Dokumente**
und lassen sich dort mit einem Klick öffnen.

**Zentrale Ablage.** Was immer wieder gebraucht wird, legt der Administrator einmal ab:
**Einstellungen → Stammdaten → Dokumente**. Am Artikel wird es dann nur noch zugeordnet.
Angenommen werden ausschließlich PDF-Dateien.

**Drei Ebenen**, weil die Wirklichkeit drei kennt:

- an einer **Materialklasse** — gilt für alle Artikel darin, auch für die Unterklassen.
  Die Desinfektionsanleitung für Kleidung hängt hier und gilt damit für alle vierzig
  Jacken.
- an einem **Artikeltyp** — gilt für alle Artikel dieses Typs. Der Platz für die
  Bedienungsanleitung eines Gerätetyps.
- am **einzelnen Artikel** — für das, was nur dieses eine Stück betrifft.

Klassen und Typen hakt der Administrator im Dokument selbst ab, unter **„Gilt für…"**.
Die Zuordnung zu einem einzelnen Artikel erfolgt am Artikel: **Aus der Ablage**.

**Neue Fassung.** Kommt eine aktualisierte Anleitung, wird über **„Neue Fassung"** nur
die Datei getauscht — alle Zuordnungen bleiben bestehen. Das ist der eigentliche Grund
für die zentrale Ablage: wer stattdessen vierzigmal dieselbe PDF anhängt, aktualisiert
sie nie wieder.

**Eigene PDF am Artikel.** Über **„Eigene PDF"** lässt sich direkt am Artikel etwas
hochladen, das es nur einmal gibt: die Rechnung, das Prüfprotokoll des Herstellers, die
Kopie eines Schreibens. Solche Dokumente erscheinen nicht in der zentralen Ablage und
werden mit ihrer letzten Zuordnung gelöscht.

Bei jedem Dokument steht, **woher es kommt** — aus der Materialklasse, aus dem
Artikeltyp oder nur von diesem Artikel. Lösen lässt sich am Artikel nur, was auch dort
zugeordnet wurde; alles andere gehört zur Klasse oder zum Typ und wird in den
Einstellungen geändert. Trifft dasselbe Dokument über mehrere Ebenen zu, steht es
einmal da, mit der speziellsten Herkunft.

Die hinterlegten Dokumente liegen mit im Backup.

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

## Das Ausgabeblatt (Empfangsbestätigung)

Direkt nach einer Ausgabe erscheint das **Ausgabeblatt**: eine Empfangsbestätigung mit
den übergebenen Artikeln, Empfänger, Datum und Unterschriftsfeldern. Es gibt drei Wege
damit umzugehen, alle an derselben Stelle:

- **Drucken** — mit hinterlegtem Server-Drucker direkt, das Pfeilchen daneben öffnet die
  PDF-Vorschau. Wahlweise in zwei Ausfertigungen, eine intern und eine zum Mitgeben.
- **Hier unterschreiben** — beide Unterschriften werden auf dem Gerät geleistet
  (Ausgebender und Empfänger) und in das abgelegte PDF eingebettet. Kein Papier nötig.
- **Unterschriebenes hochladen** — das ausgedruckte und unterschriebene Blatt wird
  fotografiert oder eingescannt und dem Vorgang beigelegt.

Das gilt für die **Einzelausgabe** ebenso wie für die **Sammelausgabe**. In beiden
Fällen führt das Blatt genau die Artikel dieser Übergabe auf — nicht alles, was die
Person am selben Tag sonst noch bekommen hat.

Auf Wunsch lassen sich die **bereits vorhandenen Artikel mitdrucken**, dann steht auf
einem Blatt der komplette Bestand des Helfers. Das Blatt trennt dabei deutlich: unter
„Hiermit übernommen" steht, was gerade übergeben wird — das ist der Teil, der
unterschrieben wird. Darunter folgt „Nachrichtlich: bereits im Besitz", grau abgesetzt
und ausdrücklich als nicht Gegenstand der Bestätigung gekennzeichnet. Über den
Unterschriftsfeldern steht derselbe Hinweis noch einmal im Klartext, mit der Anzahl.

## Bereitstellung: heute zusammenstellen, morgen übergeben

Zusammenstellen und Übergeben fallen oft auseinander — die Einsatzausstattung wird
abends gepackt und am nächsten Morgen abgeholt. Dafür gibt es **Bereitstellungen**
(Navigationspunkt „Bereitstellungen"): Artikel werden einer Person zugeordnet wie in
einem Warenkorb und erst bei der Übergabe tatsächlich ausgegeben.

1. **Anlegen** — Person wählen, Vorgang anlegen. Er bekommt einen Code wie
   `BS-2026-0007`.
2. **Vormerken** — Artikel scannen oder die Nummer eintippen. Sie bekommen den Status
   **Vorgemerkt**. Der ist ein Hinweis, kein Verbot: wer den Artikel anderweitig ausgeben
   will, bekommt eine Rückfrage mit Name und Vorgangscode und kann bestätigen. Ein Artikel
   kann nur auf **einem** offenen Vorgang stehen. Der vorherige Status wird gemerkt und
   kommt zurück, sobald die Vormerkung endet — war ein Teil vorher „Zu waschen", ist es
   das danach wieder.
3. **Bereitstellungsplatz** (optional) — über „alle umlagern" werden sämtliche
   vorgemerkten Artikel auf einmal an einen Lagerort gebucht: den Platz, an dem die
   Ausstattung bis zur Abholung steht. Bei größeren Ausgaben ist das der eigentliche
   Gewinn — einmal zusammenräumen und einmal buchen, statt beim Übergeben durch das ganze
   Lager zu laufen. Und wer einen Artikel sucht, findet ihn dort, wo er wirklich liegt.
4. **Beleg drucken** und zur Ausstattung legen. Er führt alle Artikel auf, hat
   Unterschriftsfelder und trägt den Code als Scancode.
5. **Übergeben** — den Beleg scannen (oder den Vorgang in der Liste öffnen) und
   „Jetzt übergeben" drücken. Alle vorgemerkten Artikel werden auf einmal gebucht, mit
   denselben Prüfungen wie bei der Sammelausgabe. Was nicht durchgeht, bleibt stehen,
   wird gemeldet und bleibt vorgemerkt; der Vorgang gilt erst als ausgegeben, wenn
   nichts mehr offen ist.
6. **Quittieren** — direkt darunter erscheint das Ausgabeblatt: drucken, auf dem Gerät
   unterschreiben oder das unterschriebene Papier fotografiert hochladen. Wer auf Papier
   unterschreiben lässt, nutzt einfach den Bereitstellungsbeleg aus Schritt 4 und lädt
   ihn unterschrieben wieder hoch.

Wird eine Bereitstellung doch nicht gebraucht, hebt **Vormerkung aufheben** sie auf: die
Artikel gehen in ihren vorherigen Status zurück und sind wieder frei planbar. Wurde
umgelagert, fragt das Programm zusätzlich, ob auch der Lagerort zurückgesetzt werden
soll — steht die Ausstattung körperlich am Bereitstellungsplatz, wäre ein stilles
Zurückbuchen schlicht falsch.

Abgelegte Blätter finden sich später in der Personenakte unter **Quittungen**; von dort
lässt sich auch nachträglich eine Ausgabe- oder Rückgabebestätigung über den heutigen
Stand erzeugen.

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
- Eine Person kann **mehreren Abteilungen** angehören (etwa Bereitschaft und
  Jugendrotkreuz). Unter „Bearbeiten" gibt es dafür die **Haupt-Abteilung** und darunter
  die weiteren zum Ankreuzen. Die Haupt-Abteilung ist die, die auf Etiketten und in
  Listen steht, wo nur eine hinpasst; sie gehört immer dazu und lässt sich nicht
  versehentlich abwählen.
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

# 21. Stammdaten verwalten (Materialklassen, Typen, Abteilung, Lagerorte, Logo, Drucker)

## Materialklassen

Die Materialklassen gibt das Programm vor. Es bringt acht mit — Kleidung, Schlüssel,
Funk (mit den Unterklassen Funk-Akkus und Funk-Zubehör), Fahrzeuge, Behälter und
Sonstiges — und jede kommt mit den Feldern, Status und Prüfarten, die dort üblich
sind. Funk zum Beispiel mit Funkrufname, OPTA und ISSI getrennt, dazu
Firmware-Version; Fahrzeuge mit Kennzeichen, Fahrgestellnummer, Erstzulassung und
Indienststellung; Behälter mit Leer- und beladenem Gewicht.

Diese Klassen lassen sich **nicht umbenennen und nicht löschen**. Wird eine nicht
gebraucht, blendet man sie aus: sie taucht bei der Erfassung nicht mehr auf, vorhandene
Artikel bleiben unverändert auffindbar. Das ist die einzige gefahrlose Art, eine Klasse
loszuwerden — beim Löschen würde man Material verlieren.

**Weitere Klassen legt ausschließlich ein Administrator an.** Sie starten leer; die
Felder baut er unter „Zusatzfelder" selbst zusammen, mit demselben Baukasten (Text,
Zahl, Auswahl, Ja/Nein, Datum) und denselben Prüfintervallen wie die mitgelieferten.
Beim Erfassen eines Artikels lässt sich die Klasse deshalb nur noch auswählen, nicht
mehr nebenbei anlegen — sonst entstünden mit der Zeit „Kleidung", „kleidung" und
„Bekleidung" nebeneinander.

Die Standardfelder einer mitgelieferten Klasse darf der Administrator umbenennen und
ausblenden, aber nicht löschen: sonst zeigten bereits erfasste Werte ins Leere.

**Unterkategorien** hängen eine Ebene unter einer Klasse (Funk → Analog, Digital, DME)
und erben deren Standards — auch das Schließanlagen-Kennzeichen, eine Unterklasse unter
„Schlüssel" hat die Schlüssel-Funktionen also sofort.

### Eine eigene Klasse wieder auflösen

Selbst angelegte Klassen lassen sich löschen — aber nicht mitsamt ihrem Inhalt. Der
Knopf **löschen** öffnet einen Dialog, der zeigt, was an der Klasse hängt: alle Artikel
mit Nummer, Typ, Größe und Status, dazu ihre Artikeltypen und Unterklassen. Von dort
wird umgehängt:

- **Einen ganzen Artikeltyp verschieben** ist der schnelle Weg: er behält seinen Namen
  und nimmt alle seine Artikel mit. Das ist der Normalfall, wenn eine Klasse
  versehentlich angelegt wurde.
- **Einzelne Artikel verschieben** geht über die Häkchen — einzeln oder alle auf einmal.
  Dafür ist zusätzlich ein Artikeltyp der Zielklasse zu wählen, denn ohne passenden Typ
  wäre ein Artikel dort nicht einzuordnen.
- **Unterklassen** lassen sich in einem Zug mit unter die Zielklasse hängen.

Erst wenn nichts mehr an der Klasse hängt, lässt sie sich löschen. Kein Artikel geht
dabei verloren, und alle behalten ihre Nummer und ihre Geschichte.

### Die Klasse eines Artikels nachträglich ändern

Wurde die Klasse beim Erfassen falsch gewählt, stellt ein Administrator sie in der
Artikelansicht unter **Materialklasse → ändern** um. Weil die Klasse Zusatzfelder,
Status und Prüfarten bestimmt, wechselt der Artikeltyp zwingend mit — er lässt sich aus
den Typen der neuen Klasse wählen oder gleich dort anlegen.

Der Artikel bleibt derselbe: Nummer, Ausgabehistorie, Prüfprotokolle und Bilder bleiben
erhalten. Zusatzfelder der bisherigen Klasse bleiben gespeichert, werden aber nicht mehr
angezeigt; ein Status, den es in der neuen Klasse nicht gibt, bleibt stehen, bis er
gewechselt wird.

## Status je Klasse

Status gelten jeweils nur für die Klassen, zu denen sie passen. „Zu waschen" und
„Infektiös" gibt es deshalb bei Kleidung, nicht bei Schlüsseln. Das gilt überall: im
Statuswechsel-Dialog eines Artikels, bei den Schnellknöpfen der Materialausgabe und im
Statusfilter der Übersicht, sobald dort eine Klasse gewählt ist. Der Server weist einen
unpassenden Status zusätzlich ab — die Regel steht also nicht nur in der Oberfläche.
Eine Unterklasse erbt die Status ihrer Oberklasse. **Vorgemerkt** setzt das Programm
selbst, sobald ein Artikel auf einer offenen Bereitstellung steht (Kapitel 13); von Hand
gewählt wird er nicht. Mitgeliefert sind:

| Klasse | Status zusätzlich zu Verfügbar, Ausgegeben, In Reparatur, Zu prüfen, Ausgemustert, Verschollen, Entwendet und Vorgemerkt |
|---|---|
| Kleidung | Zu waschen, Beschädigt, Infektiös |
| Schlüssel | Abgebrochen, Verloren, Nachgefertigt, Entwertet/gesperrt, Beim Schlosser |
| Funk | Teildefekt, Gesperrt |
| Fahrzeuge | Außer Dienst, Unfall, Unvollständig |
| Behälter | Defekt/beschädigt, Abgelaufen |

Wo eine Beschreibung nötig ist — Verloren, Abgebrochen, Unfall, Entwendet und ähnliche —
verlangt das Programm sie beim Setzen. Der Administrator kann unter „Status" jeden
Status jeder Klasse zuordnen und eigene ergänzen.

## Übriges

Typen, Modelle, Abteilungen und Lagerorte lassen sich wie bisher anlegen, **umbenennen**
und **löschen** — Löschen jeweils nur, solange kein Artikel den Eintrag mehr verwendet.
Beim Erfassen fragt das Programm weiterhin nach, ob ein noch unbekannter Typ, ein
Modell oder eine Abteilung neu angelegt werden soll; das gilt auch für die
Schnellerfassung bei der Materialausgabe.

Personen werden über die eigene Seite **„Personen"** verwaltet (siehe Kapitel 15),
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

# 24. Lagerorte als Baum und Inventur

## Der Lagerort-Baum

Lagerorte werden als Baum gepflegt: **Standort → Etage → Raum → Schrank → Fach**.
Nicht jede Ebene muss benutzt werden — wer nur „Gerätehaus / Regal 3“ braucht, lässt
die übrigen Ebenen einfach leer. Die Bezeichnungen sind Vorschläge, keine Vorschrift:
„Etage“ kann auch „Garage“ heißen und „Raum“ ein Fahrzeug bezeichnen.

Gepflegt wird der Baum unter **Einstellungen → Stammdaten → Standorte**. Zu jedem
Knoten lassen sich Adresse, Ansprechpartner, Telefon und eine Beschreibung
hinterlegen. Die Beschreibung ist für Hinweise gedacht wie „blaue Kiste unter der
Werkbank“ und erscheint in der Oberfläche als Hilfetext.

Ältere Installationen haben die Ortsangaben noch als freie Textfelder am Artikel
(Etage/Raum/Schrank/Fach). Unter **Einstellungen → Standorte** gibt es einen Knopf,
der diese Angaben einmalig in den Baum überführt.

## QR-Etiketten für Lagerorte

Jeder Knoten des Baums hat eine eigene Nummer mit QR-Code. Über den Knopf **QR** neben
einem Lagerort wird ein einzelnes Etikett erzeugt, über **Alle QR-Etiketten** ein PDF
mit je einem Etikett pro Knoten — praktisch, um einmalig alle Schränke und Fächer zu
bekleben.

## Inventur

Eine Inventur wird unter **Inventur** angelegt. Sie hat einen Namen, einen Umfang
(alle Artikel, bestimmte Materialklassen oder bestimmte Lagerorte) und Teilnehmende.
Optional lassen sich Stationen festlegen — eine geordnete Liste von Lagerorten, die
nacheinander abgearbeitet wird.

Der Ablauf vor Ort: Lagerort-QR scannen, dann alle dort vorhandenen Artikel scannen
oder ihre Nummern eintippen. Das Programm zeigt laufend, was an dieser Station noch
fehlt. Artikel, die an einem anderen als dem erwarteten Ort auftauchen, werden
vermerkt und lassen sich direkt umbuchen.

Die Erfassung funktioniert auch **ohne Netz**: Scans werden auf dem Gerät
zwischengespeichert und automatisch übertragen, sobald die Verbindung wieder steht.
Eine Anzeige oben zeigt, ob das Gerät online ist.

Zum Abschluss erzeugt das Programm einen **Inventurbericht** als PDF oder CSV mit
gefundenen, fehlenden und bewusst ignorierten Artikeln samt Kennzahlen. Inventuren
lassen sich auch als Vorlage speichern und wiederkehrend planen.

# 25. Schlüssel und Schließanlagen

Schlüssel sind keine eigene Artikelart, sondern eine Eigenschaft der Materialklasse.
Erst wenn eine Kategorie das Kennzeichen **Schließanlage** trägt, erscheinen bei ihren
Artikeln die zusätzlichen Felder.

**Einmalig einrichten:** entfällt — die Materialklasse **Schlüssel** bringt das Programm
mit, das Kennzeichen „Schließanlage" ist dort gesetzt. Eine Unterklasse darunter
(zum Beispiel „Zylinderschlüssel") erbt es automatisch.

**Schlüssel erfassen:** wie jeden anderen Artikel, mit der Klasse Schlüssel. Im Formular
erscheinen zusätzlich:

- **Schlüsseltyp** — ein Vorschlagsfeld, in das sich auch Neues eintragen lässt (etwa
  Winkhaus oder Bartschlüssel)
- **Seriennummer / Prägung** — was auf dem Schlüssel steht, darf leer bleiben
- **Name (Alias)** — ein sprechender Name wie „Haupteingang Pfarrheim". Er steht
  **neben** der Artikelnummer, nicht an ihrer Stelle: in der Ausgabeliste, in der
  Artikelansicht und im Schließplan. Die Ausgabeliste sucht auch darin.
- **Schließgruppe** — die Bezeichnung der Anlage, wie sie bei älteren Schließanlagen
  auf dem Schlüssel steht (etwa „HN1"). Ein freies Textfeld ohne Automatik.

**Welche Türen öffnet der Schlüssel?** Das wird bewusst erst nach dem Speichern
festgelegt. In der Artikelansicht gibt es die Karte **Schließungen**: eine
ausklappbare, durchsuchbare Liste, nach Objekt gruppiert.

**Woher kommen die Schließungen?** Der bequeme Weg führt über den Lagerort-Baum: Bei
jedem Lagerort lässt sich **Schließung (im Schließplan)** ankreuzen — der Ort erscheint
dann automatisch als Schließung im Schließplan seines Standorts. Ein Standort mit
markierten Lagerorten wird dadurch selbst zur Schließanlage. Türen, die es als Lagerort
nicht gibt (Außentor, Tresor), ergänzt man unter **Einstellungen → Stammdaten →
Schließanlagen**. Ein Lagerort kann mehrere Zylinder haben, etwa eine Garage mit „Tor“
und „Tür“.

## Schlösser an einem Artikel (Fahrzeug, Behälter)

Manche Gegenstände haben ihre Schlösser selbst dabei. Ein Fahrzeug hat Fahrertür,
Beifahrertür, Heckklappe, Geräteraum 1 bis 4, Zündschloss und Tankdeckel; eine Kiste hat
ein Vorhängeschloss. In der Artikelansicht gibt es dafür die Karte **Schlösser**: dort
lassen sich beliebig viele anlegen, umbenennen und wieder entfernen.

Zusammen bilden sie die **Schließanlage dieses Artikels** — und ausdrücklich nicht die
des Standorts. Das ist der eigentliche Punkt: ein Fahrzeug fährt weg und steht morgen
woanders. Stünden seine Türen im Schließplan des Gerätehauses, wäre der Plan falsch,
sobald das Fahrzeug ausrückt. Auch ein Lagerort *innerhalb* eines Fahrzeugs, der als
Schließung markiert ist (etwa „Geräteraum 1"), gehört deshalb zur Anlage des Fahrzeugs.
Solche abgeleiteten Schließungen sind in der Karte als „aus dem Lagerort" gekennzeichnet
und werden dort umbenannt, wo sie herkommen — im Lagerort-Baum.

Welcher Schlüssel welches Schloss öffnet, wird wie immer **am Schlüssel** festgelegt, in
dessen Karte „Schließungen".

Ob eine Materialklasse überhaupt Schlösser haben kann, steht unter **Einstellungen →
Stammdaten** in der Tabelle der Materialklassen, Spalte **Schlösser**. Sie ist das
Gegenstück zur „Schließanlage": dort *sind* die Artikel Schlüssel, hier *haben* sie
welche. Mitgeliefert ist das Kennzeichen bei **Fahrzeugen** und **Behältern**; für eigene
Klassen setzt es der Administrator.

## Schlüsselbünde

Niemand übergibt sieben Schlüssel einzeln. Unter **Schlüsselbünde** lassen sich Schlüssel
zu einem Bund zusammenfassen — „Gerätehaus komplett", „MTW Fahrer". Jeder Bund bekommt
eine fortlaufende Nummer (SB-0001) für den Anhänger.

Ein Schlüssel hängt an höchstens einem Bund, so wie in Wirklichkeit auch. Hängt er ihn an
einen anderen, wird er am alten automatisch abgenommen.

**Ausgabe:** Der Bund geht als Ganzes hinaus und kommt als Ganzes zurück. Direkt im
Anschluss lässt sich das **Ausgabeblatt über genau diese Übergabe** drucken oder digital
unterschreiben lassen.

Jeder Schlüssel behält dabei trotzdem **seinen eigenen Ausgabevorgang**. Das ist Absicht:
geht einer verloren, muss im Schließplan genau dieser eine stehen — mit allem, was er
öffnet. Ein Bund als einzelner Eintrag könnte diese Frage nicht beantworten.

Klemmt ein einzelner Schlüssel — gesperrter Status, schon woanders, für jemand anderen
vorgemerkt —, wird er gemeldet und die übrigen gehen trotzdem hinaus. Bei einem Hinweis
(nicht bei einer Sperre) lässt sich die Ausgabe mit **Trotzdem ausgeben** bestätigen. Ist
ein Bund nicht vollständig am selben Ort, steht das in der Übersicht, statt unterzugehen.

Der Bund zeigt, **was er insgesamt öffnet**; am einzelnen Schlüssel steht, an welchem Bund
er hängt. In der Schlüssel-Ausgabeliste gibt es dafür die Spalte **Bund**.

**Schließplan:** Je Objekt zeigt eine Matrix Schlüssel gegen Schließung — auf einen
Blick, welcher Schlüssel welche Tür öffnet. Der Plan lässt sich als PDF ausgeben,
wahlweise mit der Spalte „Aktuell bei“, also dem derzeitigen Inhaber.

**Ausgabe:** Schlüssel werden wie anderes Material ausgegeben. Zusätzlich kann ein
**Pfand** erfasst werden, das bei der Rücknahme automatisch als zurückgegeben vermerkt
wird. Für jeden Schlüssel gibt es in der Artikelansicht die Karte **Ausgabedokument**:
ein PDF mit Empfänger, Schlüsseldaten und den geöffneten Türen, das digital
unterschrieben oder ausgedruckt, unterschrieben und wieder hochgeladen werden kann.

**Verlust:** Bei zugeordneten Schließungen zeigt die Schlüsselansicht, welche Türen im
Verlustfall betroffen wären — ein Hinweis darauf, ob umgeschlossen werden muss. Die
Seite **Schlüssel-Ausgabe** listet alle derzeit ausgegebenen Schlüssel mit Halter,
Typ, Seriennummer, geöffneten Türen und Pfand.

# 26. Fahrzeuge und Logbuch

Ein Artikel kann als **Fahrzeug** gekennzeichnet werden. Er bekommt dann zusätzliche
Felder wie Kennzeichen, Fahrgestellnummer und Erstzulassung — und er kann gleichzeitig
**Lagerort** sein: Schränke, Fächer und Rucksäcke im Fahrzeug werden als Knoten
darunter angelegt, sodass sich Material einem Fahrzeug zuordnen lässt.

Jedes Fahrzeug führt ein **Logbuch**. Abgeschlossene Wartungen und Termine erzeugen
dort automatisch einen Eintrag; zusätzlich lassen sich eigene Einträge mit Datum,
Kategorie, Kilometerstand und Notiz erfassen. Das Logbuch kann als PDF ausgegeben
werden.

## Reifen

Reifen werden einzeln erfasst statt in vier festen Feldern — es gibt Fahrzeuge mit
Zwillingsbereifung, Anhänger mit zwei Rädern und überall Reserveräder. Die Position ist
deshalb Freitext („vorne links", „Achse 2 rechts außen", „Reserve"); ein Standardsatz
mit vier Reifen lässt sich mit einem Klick anlegen.

Je Reifen lassen sich **Solldruck**, **Größe** und die **DOT-Nummer** hinterlegen — alles
freiwillig. Aus der DOT-Nummer (Woche und Jahr, „3823" heißt KW 38 aus 2023) errechnet
das Programm das Alter und weist ab sechs Jahren darauf hin. Eine unplausible Nummer
liefert bewusst gar keine Angabe statt einer falschen.

## Fahrzeugschein

Bilder des Fahrzeugscheins werden getrennt von den übrigen Fotos geführt — er wird
gesucht, wenn es darauf ankommt, und soll nicht zwischen Detailaufnahmen liegen. Anders
als ein Schadensbild darf er ersetzt werden, weil Fahrzeuge umgemeldet werden. Er
enthält personenbezogene Daten (Halter); ob er eingestellt wird, entscheidet der Verein.

## Prüfintervalle je Fahrzeug

Wartungsintervalle werden über die Prüf- und Terminarten gepflegt (siehe Kapitel 29).
Mitgeliefert sind Hauptuntersuchung (24 Monate), Sicherheitsprüfung (12 Monate),
Ölwechsel (12 Monate oder 15.000 km), UVV-Prüfung (12 Monate) und eine
Abfahrtkontrolle mit Checkliste.

Das Intervall lässt sich **je Fahrzeug abweichend** setzen: unter „Termine & Wartung" auf
„Termin" klicken und ein eigenes Intervall eintragen — etwa 12 statt 24 Monate für ein
Fahrzeug über 3,5 t, oder jeden anderen Wert. Leeres Feld heißt weiterhin: Vorgabe der
Prüfart. Wird eine Prüfung für ein Fahrzeug gar nicht gebraucht (etwa die
Sicherheitsprüfung), entfernt man sie dort mit „entfernen" — nur für dieses Fahrzeug.

# 27. Behälter: Kisten, Rucksäcke und Taschen

Eine Kiste ist beides — ein Gegenstand, den man inventarisiert und ausgibt, **und** ein
Ort, in dem anderes liegt. Genau so behandelt das Programm sie.

**Einrichten:** Den Artikel in der Klasse **Behälter** anlegen (oder bei einem Artikel
anderer Klasse das Kennzeichen „Behälter" setzen). In der Artikelansicht erscheint dann
die Karte **Behälter**; dort auf **Als Lagerort aktivieren** klicken und den Platz
wählen, an dem die Kiste steht. Danach kann Material darin liegen.

**Verschachtelung** ist erlaubt und beliebig tief: Kiste in Kiste in Fahrzeug. Nur in
sich selbst kann eine Kiste nicht landen.

**Umlagern:** Wandert die Kiste, wandert ihr Inhalt mit — er hängt an der Kiste, nicht am
Raum. Bei einer Raum-Inventur genügt es deshalb, die Kiste zu scannen.

**Bei der Inventur** fragt das Programm dann nach:

- **Als Ganzes bestätigen** — der Inhalt gilt als geprüft, obwohl niemand hineingesehen
  hat. Bewusst eine eigene Entscheidung, sonst hätte man eine Inventur, die grün ist,
  ohne dass jemand nachgesehen hat.
- **Nur den Behälter erfassen** — der Inhalt wird anschließend einzeln gescannt oder
  bestätigt.

**Ausgabe:** Wird die Kiste ausgegeben, geht ihr Inhalt mit. Jeder Artikel darin bekommt
einen eigenen Eintrag — sonst zeigte die Übersicht vierzig Artikel als verfügbar an, die
längst unterwegs sind. In der **Ausgabeliste steht trotzdem nur die Kiste**, mit der
Anzahl und einem Vermerk, falls sie nicht vollständig hinausging (weil einzelne Stücke
schon woanders waren). Die **Rücknahme ist ein einziger Vorgang**.

Ein einzelnes Stück darf weiterhin separat ausgegeben werden, auch aus einer Kiste, die
gerade unterwegs ist.

---

# 28. Inhaltslisten und Einschiebeschildchen

Für jedes Fach, jede Kiste und jede Rucksacktasche lassen sich zwei Dinge drucken. Beide
finden sich unter **Einstellungen → Stammdaten → Standorte** über den Knopf **Inhalt**
neben dem jeweiligen Lagerort.

**Die Inhaltsliste** ist zum Mitnehmen und Abhaken: eine Tabelle mit Bezeichnung, Größe
und **Soll**, während die Spalten **Ist** und **Differenz** frei bleiben. So arbeitet man
vor Ort mit dem Stift und trägt die Zahlen später am Schreibtisch ein — oder füllt gleich
auf und bucht nur noch den Lagerabgang. Auf Wunsch trägt das Programm den gezählten
Ist-Bestand schon ein. Fünf Leerzeilen zum Nachtragen sind immer dabei. Formate: DIN A4
und A5, jeweils hoch oder quer.

**Das Einschiebeschildchen** ist dieselbe Liste im Maß der Tasche, mit Schnittecken zum
Ausschneiden — für die Klarsichthülle an der Tasche. Das Maß lässt sich je Lagerort
einmal hinterlegen (unter „Bearbeiten"); ohne Angabe gilt 74 × 52 mm.

**Woher kommt der Soll-Bestand?** Aus den Mindestbestands-Regeln dieses Lagerorts (siehe
Kapitel 21). Die können bereits Artikeltyp, Größe, Lagerort und Menge — damit ist die
Packliste dieselbe Angabe wie die Warnschwelle: eine Stelle zum Pflegen, und das Programm
meldet von selbst, wenn eine Tasche unvollständig ist. Ist noch kein Soll hinterlegt,
kommt eine leere Liste zum Ausfüllen heraus.

Beim Ist-Bestand zählt mit, was in einer Kiste in der Tasche liegt — es ist ja da.

**Farben: was ist wann zu prüfen?** Zeilen, deren Artikeltyp einer Prüfart der Art
*Verfall* unterliegt, werden **gelb** hinterlegt; Zeilen mit einer Prüfart der Art
*Funktion* **blau**. Gilt beides, geht Gelb vor — was abläuft, ist das Dringendere, und
auf Papier hat eine Zeile nur eine Farbe. Welche Art eine Prüfart hat, wird bei ihr
eingestellt (Kapitel 29). Auf dem Einschiebeschildchen ist statt der Legende ein kleiner
Farbpunkt vor der Zeile, dort ist kein Platz für eine Erklärung.

**Wasserzeichen.** Im selben Dialog lässt sich für diesen Platz ein monochromes
Wasserzeichen wählen — etwa die Blutdruckmanschette für die Sanitätstasche oder die
Schneeflocke für die Winterkiste. Es erscheint blass hinter Liste und Schildchen und
schlägt das Wasserzeichen der Dokumentvorlage. Bleibt es leer, gilt deren Einstellung.
Die Auswahl, eigene Motive und alle Einstellungen sind in Kapitel 32 beschrieben.

Beide Ausgaben lassen sich über **Dokument-Vorlagen** gestalten (Kapitel 32) und hängen
am Druck-Knopf: mit hinterlegtem Server-Drucker wird direkt gedruckt, das Pfeilchen
daneben öffnet die PDF-Vorschau. Mit dem mitgelieferten **Vordruck** sehen Hoch- und
Querformat gleich aus: oben links Fahrzeug und Standort, mittig die Überschrift, unten
Anschrift, Stand, Version, Seitenzahl, Dateiname und die Farblegende.

---

# 29. Prüfungen, Termine und Wartung

**Prüf- und Terminarten** sind wiederverwendbare Vorlagen: ein Name (TÜV, Ölwechsel,
Sichtprüfung), optional eine Checkliste mit Prüfpunkten, eigene Erfassungsfelder
(etwa „Öl-Typ“), ein Standardintervall in Monaten oder Kilometern und wahlweise ein
auslösendes Ereignis. Gepflegt werden sie unter **Einstellungen → Stammdaten**.

Jede Art hat außerdem eine **Art der Prüfung**: *Funktion prüfen* (arbeitet das Teil
noch?) oder *Verfall prüfen* (ist es noch haltbar?). Danach färben sich die Zeilen der
Inhaltslisten — blau beziehungsweise gelb (Kapitel 28).

**Zuordnen** lassen sie sich auf drei Ebenen: für eine ganze Materialklasse, für einen
Artikeltyp oder für einen einzelnen Artikel. So gilt „TÜV alle 24 Monate“ für alle
Fahrzeuge, ohne dass es je Fahrzeug gepflegt werden muss.

In der Artikelansicht zeigt die Karte **Termine & Wartung** alle anstehenden Termine.
Über **Durchführen** wird ein Vorgang gestartet: Die Checkliste wird abgehakt, die
Erfassungsfelder ausgefüllt, und beim Abschluss bestimmt das Programm den Folgetermin —
automatisch aus dem Intervall oder von Hand. Abgeschlossene Vorgänge erscheinen als
Protokoll beim Artikel und lassen sich als PDF ausgeben.

Zu jeder Terminart lassen sich **Erinnerungen** hinterlegen, etwa 30 und 7 Tage vorher.
Die Startseite zeigt die Kachel **Anstehende Termine** für die nächsten 30 Tage; wer
Telegram eingerichtet hat, wird zusätzlich dort benachrichtigt.

# 30. Schadens- und Verlustmeldungen

Über **Schaden / Verlust melden** in der Artikelansicht kann jede und jeder einen
Schaden oder Verlust melden. Erfasst werden Hergang, Ort und Datum — diese drei
Angaben sind Pflicht —, dazu wahlweise ein Foto, Zeugen, ein Schätzwert und bei
Diebstahl ein polizeiliches Aktenzeichen. Fehlen Pflichtangaben, weist das Programm
darauf hin und kennzeichnet die Meldung als unvollständig.

Die Meldung erzeugt ein PDF mit dem Briefkopf der Organisation, das sich bei
Versicherung oder Polizei einreichen lässt.

Zuständige sehen offene Meldungen unter **Meldungen** in ihrem Posteingang und können
sie bearbeiten und abschließen. **Wer eine Meldung sehen darf, ist eingeschränkt:** der
Melder selbst, Administratoren und die für die Materialklasse Zuständigen. Andere
Konten erhalten keinen Zugriff, auch nicht auf das PDF oder das Foto.

# 31. Materialanfragen

Wer Material braucht, aber keine Ausgabeberechtigung hat, kann es über **Anfragen**
anfordern: Typ, Größe, Menge und Zeitraum, dazu eine Bemerkung. Materialverwalter sehen
die Anfragen in ihrem Posteingang und können sie annehmen oder ablehnen, jeweils mit
Begründung. Die Anfrage bleibt nachvollziehbar dokumentiert.

# 32. Dokument-Vorlagen und Drucken am Server

## Dokument-Vorlagen

Unter **Einstellungen → Dokument-Vorlagen** lassen sich Briefkopf, Kopf- und Fußzeile
der erzeugten PDFs frei gestalten — global oder je Dokumentart (Ausgabequittung,
Rückgabequittung, Schlüssel-Ausgabedokument, Schadensmeldung, Prüfprotokoll,
Fahrzeug-Logbuch, Inventarliste, Materialliste, Inventurbericht, Schließplan,
Inhaltsliste).

### Der mitgelieferte Vordruck

Für eine neue Vorlage stehen zwei Startpunkte bereit. **Vordruck übernehmen** legt das
fertige Vereinsblatt an. Oben rechts steht der Briefkopf: die Bildmarke, darunter
**Verband** und **Vereinsname** — bei einem DRK-Ortsverein also „Deutsches Rotes
Kreuz" über „Ortsverein Musterstadt e.V.". Oben links stehen Fahrzeug und Standort,
mittig Überschrift, Untertitel und Lagerort-Pfad, darunter eine Trennlinie. Im Fuß
stehen Organisation und Anschrift links, Stand und Programmversion mittig, Seitenzahl
und Dateiname rechts — und darüber die Farblegende **gelb = Verfall prüfen**,
**blau = Funktion prüfen**. **Schlichte Vorlage erstellen** ist der frühere, nüchterne
Startpunkt.

Der Verband kommt aus **Einstellungen → Etiketten & Drucker → Organisationsdaten**
(Feld „Verband / Dachorganisation"); bleibt er leer, entfällt die Zeile. **Enthält das
hochgeladene Logo den Schriftzug bereits**, lassen sich die beiden Textzeilen im Kopf
der Vorlage einfach entfernen — sonst steht der Name doppelt da.

**Das Logo darf auch ein SVG sein.** Es wird für den Ausdruck in die PDF gezeichnet und
bleibt dabei vektorscharf. Lässt sich eine SVG-Datei nicht umwandeln, steht das als
Hinweis direkt beim Logo in den Einstellungen — dann hilft es, das Logo zusätzlich als
PNG hochzuladen.

Der Vordruck ist **eine** Vorlage für beide Seitenlagen. Das liegt daran, dass der
Abstand `x` immer zu der Kante zählt, an der ein Element hängt: ein rechtsbündiges
Element misst von rechts. Im Querformat wandert es deshalb mit, statt in der
Seitenmitte zu stehen. Mit **Vorschau hoch** und **Vorschau quer** lässt sich in zwei
Klicks prüfen, dass beide Lagen dasselbe zeigen.

### Elemente und Platzhalter

Elemente werden im A4-Vorschaukasten mit der Maus platziert oder millimetergenau
gesetzt. Es gibt fünf Arten: **Text** (mit Größe, Ausrichtung, Fettschrift),
**Logo**, **Linie** (Breite 0 = von Rand zu Rand), **Farblegende** und
**Einzelnes Farbfeld**.

Die **Farblegende** ist eine Liste aus Farbe und Erklärung — im Vordruck „Verfall
prüfen" und „Funktion prüfen". Die Kästchen stehen untereinander in einer Spalte,
die Erklärung jeweils daneben auf gleicher Höhe; Zeilen lassen sich hinzufügen,
umbenennen und einfärben. (Zwei einzelne Farbfelder wären das Gleiche nur
scheinbar: rechtsbündig gesetzt richten sich deren Textenden aus, und die Kästchen
versetzen sich um den Längenunterschied der Wörter.)

Texte enthalten Platzhalter, die beim Druck durch echte Werte ersetzt werden. Der Knopf
**Platzhalter anzeigen** listet alle mit Erklärung und Beispiel auf:

| Platzhalter | Bedeutung |
| --- | --- |
| `{titel}` | Art des Dokuments, z.B. „Inhaltsliste" |
| `{untertitel}` | Worum es konkret geht — Lagerort, Person, Inventur |
| `{lagername}` | Name des Fachs, der Kiste, der Tasche |
| `{pfad}` | Vollständiger Weg dorthin |
| `{fahrzeug}` | Fahrzeug, zu dem der Lagerort gehört |
| `{standort}` | Oberster Lagerort (Gebäude) |
| `{abteilung}` | Abteilung, zu der das Material gehört |
| `{organisation}` | Organisationsname aus den Einstellungen |
| `{adresse}`, `{adresse1}` … `{adresse3}` | Anschrift, einzeilig oder zeilenweise |
| `{datum}`, `{stand}` | Zeitpunkt des Ausdrucks, lang bzw. kurz |
| `{version}` | Version des Programms, das den Ausdruck erzeugt hat |
| `{dateiname}` | Name der erzeugten PDF-Datei |
| `{benutzer}` | Wer den Ausdruck erzeugt hat |
| `{seite}`, `{seiten}` | Seitenzahl und Gesamtzahl |

Ein leerer Platzhalter lässt seine Zeile weg: ein Dokument ohne Fahrzeug druckt keine
leere Fahrzeugzeile. Die Anschrift kommt aus **Einstellungen → Organisation**; jede
Zeile dort wird zu `{adresse1}`, `{adresse2}`, `{adresse3}`.

### Den eigenen Vordruck als Hintergrund verwenden

Wer bereits ein fertiges Blatt hat — aus Excel, Word oder von der Druckerei —, kann es
**hochladen und das Programm nur die veränderlichen Angaben darauf drucken lassen**.
Unter „Eigener Vordruck als Hintergrund" wird die Datei (PDF, vektorscharf, oder ein
Bild) hinterlegt; sie liegt seitenfüllend hinter dem Inhalt. Anschließend bleiben in
der Vorlage nur die Elemente stehen, die sich von Blatt zu Blatt ändern — Lagerort,
Fahrzeug, Stand, Version, Seitenzahl — und werden mit der Maus an die passende Stelle
des Vordrucks gezogen.

Zwei Dinge sind dabei zu beachten:

- **Je Seitenlage eine eigene Datei.** Ein hochkanter Vordruck hinter einer
  Querformat-Liste wäre breitgezogen oder gekippt; deshalb gibt es getrennte Felder für
  Hoch- und Querformat. Ist für eine Lage keine Datei hinterlegt, wird dort auch kein
  Hintergrund gedruckt. Die Datei wird auf die Seitengröße gebracht — ein A4-Vordruck
  passt also auch hinter eine A5-Liste.
- **Was im Vordruck schon als Text steht, steht auch im Ausdruck.** Enthält die Datei
  Beispielwerte wie „Version X.X" oder „Masterfolie", erscheinen die weiter — das Blatt
  liegt ja unverändert dahinter. Entweder den Vordruck an diesen Stellen leer
  exportieren und die Werte als Elemente daraufsetzen, oder die Elemente weglassen, die
  der Vordruck schon zeigt.

Sobald ein Hintergrund hinterlegt ist, erscheint der Knopf **Briefkopf-Elemente
entfernen**. Er nimmt in einem Zug alles heraus, was ein fertiges Blatt schon auf dem
Papier hat — Bildmarke, Schriftzug, Anschrift, Trennlinien und Farblegende — und lässt
nur die veränderlichen Werte stehen. So bleibt das Logo nur dort im Ausdruck, wo es
gebraucht wird: bei den Dokumentarten ohne eigenen Vordruck.

Vorlagen lassen sich aktiv und inaktiv schalten; ohne aktive Vorlage greift das
eingebaute Standardlayout. Auch dann stehen Lagerort, Fahrzeug, Stand und Version auf
dem Blatt — nur eben im Dokumentkopf statt im Briefkopf.

### Monochromes Wasserzeichen

Ein Wasserzeichen liegt blass hinter dem Inhalt und sagt auf einen Blick, wozu ein
Blatt gehört: der Blutstropfen zum Blutspendetermin, die Schneeflocke zum
Winterdienst, die Blutdruckmanschette zur Sanitätstasche. Auf einem Stapel Ausdrucke
findet man das richtige Blatt, ohne zu lesen.

**Monochrom heißt: eine Farbe, frei wählbar.** Das ist Absicht. Ein mehrfarbiges Bild
hinter einer Tabelle macht die Zahlen unleserlich, und auf einem Schwarzweißdrucker
wird ohnehin ein grauer Fleck daraus.

Mitgeliefert sind elf Motive: Blutstropfen (Blutspende), Kreuz, Schneeflocke,
Blutdruckmanschette, Infusionsbeutel mit Leitung, Spritze, gekreuzte Nadeln,
gekreuzte Pflaster, Verbandsrolle, Sauerstoffflasche und Herz mit EKG-Linie. Sie sind
als Zeichnung hinterlegt, nicht als Bilddatei — sie bleiben also in jeder Größe scharf
und lassen sich in jeder Farbe drucken.

**Eigene Motive** lassen sich hochladen (PNG, JPG, WebP, GIF, BMP; bis 10 MB). Beim
Drucken werden sie auf die gewählte Farbe reduziert: dunkle Stellen werden zur
Zeichnung, helle verschwinden. Am besten eignet sich eine klare Strichgrafik. Die
hochgeladenen Motive sind eine gemeinsame Sammlung — einmal hochladen, danach überall
auswählbar. Wird ein Motiv gelöscht, verlieren Vorlagen und Lagerorte, die es
verwenden, ihr Wasserzeichen; es bleibt kein Verweis ins Leere stehen.

Einstellbar sind Farbe, **Deckkraft** (1–60 %), **Größe** (10–400 mm), **Drehung** und
die **Position**: Mitte, eine der vier Ecken oder über die ganze Seite gekachelt. Mehr
als etwa 15 % Deckkraft macht Zahlen in der Tabelle schwer lesbar — das Wasserzeichen
liegt zwar hinter dem Text, färbt aber das Papier ein. **Vorschau hoch** und
**Vorschau quer** zeigen eine leere Seite mit dem Wasserzeichen, bevor 30 Listen damit
gedruckt werden.

**Je Lagerort statt je Vorlage.** Ein Wasserzeichen lässt sich auch für einen einzelnen
Platz festlegen — im Inhalts-Dialog des Lagerorts (Kapitel 28). Dieses schlägt das der
Vorlage. So bekommt die Sanitätstasche die Blutdruckmanschette und die Winterkiste die
Schneeflocke, ohne dass dafür je eine eigene Dokumentvorlage nötig wäre. Bleibt es
leer, gilt das der Vorlage.

## Drucker am Server

Neben dem Etikettendruck am eigenen Gerät (Kapitel 18) kann der Server selbst drucken.
Unter **Einstellungen → Etiketten & Drucker** lassen sich beliebig viele Drucker
hinterlegen, wahlweise als CUPS-Warteschlange oder direkt über IP und Port 9100. Eine
Auto-Erkennung liest die am Server vorhandenen CUPS-Drucker aus; über **CUPS-Drucker
einrichten** lässt sich ein neuer Drucker direkt anlegen.

Jeder Drucker hat einen Typ (Etiketten- oder Papierdrucker), optionale Druckoptionen
und einen **Testdruck**-Knopf. Anschließend wird je **Anwendungsfall** festgelegt,
welcher Drucker verwendet wird: Etiketten, Ausgabequittung, Rückgabequittung, Berichte,
Listen, Schließplan, Ausgabedokument.

Überall dort, wo bisher ein PDF geöffnet wurde, gibt es nun einen **Drucken**-Knopf
und daneben ein kleines Pfeilchen für die PDF-Ansicht. Ist genau ein Drucker
zugeordnet, wird nach Rückfrage direkt gedruckt; bei mehreren erscheint eine Auswahl;
ist keiner hinterlegt, öffnet sich das PDF wie gewohnt.

Der Server-Druck erfordert ein Arbeitsrecht (Artikel, Ausgabe, Export, Inventur oder
Wartung). Konten mit reinem Leserecht können ihn nicht auslösen.

# 33. Fehlerbehebung und häufige Fragen

**Der erste Griff bei „es geht nicht": der Selbsttest.**
Die Verwaltungs-App hat einen Selbsttest (macOS/Linux: Menüpunkt 4, Windows: Knopf
„Selbsttest"). Er prüft der Reihe nach Docker, Installation, Container, Erreichbarkeit,
Versionen, Speicherplatz, Sicherungen, Zertifikat und Protokoll und sagt zu jedem Punkt,
was zu tun ist. Führt das nicht weiter, zeigt „Protokoll ansehen" die Meldungen des
Servers — dort steht der Grund fast immer im Klartext.

**Änderungen kommen nicht an, obwohl ein Update gemacht wurde.**
In der Übersicht der Verwaltungs-App steht neben der installierten und der verfügbaren
Version auch die **laufende** Version, die der Server selbst meldet. Nur sie sagt, was
tatsächlich ausgeführt wird. Weicht sie ab, wurden die neuen Programmdateien kopiert,
aber noch nicht übernommen: „Erweitert" → „Erstinstallation / Update" ausführen.

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

# 34. Datenschutzhinweise

Das Programm erfasst unter anderem, welche Person welchen Kleidungsartikel erhalten
hat. Da unter den erfassten Personen auch Minderjährige sein können, gilt:

- Zugriff auf die Anwendung sollte nur den tatsächlich benötigten Personen mit
  eigenem Konto und angemessener Rolle gewährt werden
- Die Anwendung läuft ausschließlich im lokalen Netzwerk und ist nicht über das
  Internet erreichbar, solange sie nicht bewusst dafür freigegeben wird
- Regelmäßige Backups sollten sicher (z.B. verschlüsselt) aufbewahrt werden
- Nicht mehr benötigte Personendaten (z.B. ausgeschiedene Mitglieder) sollten
  regelmäßig bereinigt werden

## Was das Programm dafür anbietet

**Aufbewahrungsfristen** (Einstellungen → Sicherheit). Für vier Bereiche lässt sich
eine Frist in Tagen hinterlegen; 0 Tage bedeutet „unbegrenzt aufbewahren". Alle sechs
Stunden werden die Fristen angewendet. Neben jedem Feld steht, wie viele Einträge die
eingestellte Frist gerade betreffen würde — so lässt sich eine Frist gefahrlos
einschätzen, bevor sie greift.

| Bereich | Was passiert | Was bleibt |
|---|---|---|
| Ausgabehistorie | Bei zurückgegebenem Material wird entfernt, wer es hatte | Artikel, Zeitraum, Zustand |
| Quittungen | Werden samt Datei gelöscht (enthalten Unterschriften) | nichts |
| Schadens-/Verlustmeldungen | Melder, Zeugen und Kontakt werden entfernt (nur abgeschlossene) | Hergang, Ort, Schadenshöhe |
| Prüfprotokoll | Einträge werden gelöscht | nichts |

Laufende Ausgaben und offene Meldungen werden nie angefasst.

**Auskunft (Art. 15 DSGVO).** Jeder Angemeldete findet unter „Mein Konto" den Punkt
*Meine Daten*: dort steht, was über ihn gespeichert ist, und es lässt sich als Datei
mitnehmen. Für andere Personen erzeugt die Materialverwaltung die Auskunft unter
Personen → Person → Auskunft.

**Löschung/Anonymisierung (Art. 17 DSGVO).** Administratoren können eine Person
anonymisieren: Name und Notizen werden durch ein Pseudonym ersetzt, verknüpfte Konten
deaktiviert und Telegram-Verknüpfungen gelöst. Der Materialverlauf bleibt statistisch
erhalten.

**Telegram.** Telegram ist ein Anbieter außerhalb der EU. Wer sein Telegram-Konto
verknüpfen will, muss deshalb ausdrücklich einwilligen; der Zeitpunkt wird am Konto
festgehalten. Wird die Verknüpfung entfernt, gilt das zugleich als Widerruf — es
gehen sofort keine Nachrichten mehr an dieses Konto. Zusätzlich lässt sich in den
Telegram-Einstellungen die *Datenminimierung* aktivieren: dann stehen in den
Nachrichten keine Klarnamen mehr, sondern nur noch „(vergeben)".

**Echtzeit-Verbindung.** Die Oberfläche hält eine Verbindung zum Server offen, damit
Änderungen sofort erscheinen. Darüber geht nur, *dass* sich in einem Bereich etwas
geändert hat — keine Namen, keine Inhalte, und nicht, wer etwas getan hat. Die Seite
lädt anschließend ganz normal nach, wobei die eigenen Berechtigungen greifen.

Dieses Handbuch stellt keine Rechtsberatung dar. Bei Fragen zur
datenschutzkonformen Nutzung empfiehlt sich Rücksprache mit einer bzw. einem
Datenschutzbeauftragten.
