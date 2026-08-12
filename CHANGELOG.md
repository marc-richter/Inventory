# Änderungsprotokoll (Changelog)

Ab Version 1.0.0 wird für jede inhaltliche Änderung am Programm eine neue
Versionsnummer vergeben (Format: MAJOR.MINOR.PATCH). Die aktuelle Version steht
in der Datei `VERSION` im Projektordner. Die Verwaltungs-Apps (siehe
`installer/`) vergleichen diese Versionsnummer beim Erstinstallation/Update-Dialog
mit der Version, die zuletzt tatsächlich installiert/gestartet wurde, und zeigen
an, ob ein Update verfügbar ist.

## 1.86.0

- **Schlüssel-Kategorie standardmäßig vorhanden:** Bei einer Neuinstallation wird – wie „Kleidung" –
  automatisch eine Kategorie „Schlüssel" angelegt (mit aktiviertem Schließanlagen-Kennzeichen), sodass
  die Schlüssel-Funktionen sofort bereitstehen.
- **Aufgeräumte Stammdaten-Einstellungen:** Kategoriespezifische Einstellungen (Typen, Unterkategorien,
  Zusatzfelder, Modelle, Standards, Mindestbestände, Prüf-/Wartungszuordnungen, Ausgebbar/Schließanlage)
  werden erst nach Auswahl einer Kategorie angezeigt und dann auf diese Kategorie gefiltert. Allgemeine
  Stammdaten (Kategorien, Abteilungen, Standorte, Größenarten, Checklisten, Prüf-/Wartungsarten,
  Schließanlagen) bleiben immer sichtbar.

## 1.85.0

- **Schließplan-Matrix:** Je Objekt/Schließanlage gibt es (Einstellungen › Stammdaten) eine Matrix
  Schlüssel × Schließung – auf einen Blick, welcher Schlüssel welche Türen öffnet.
- **Verlust-Impact:** In der Schlüssel-Ansicht wird bei zugeordneten Schließungen angezeigt, welche
  Türen/Anlagen bei Verlust betroffen wären (Hinweis auf mögliches Umschließen). Schaden-/Verlust­
  meldungen stehen für Schlüssel wie für alle Artikel bereit.
- **Schlüssel-Ausgabeliste:** Neue Seite mit allen aktuell ausgegebenen Schlüsseln (Halter, Typ,
  Seriennummer, geöffnete Türen, Pfand, seit wann), durchsuchbar – erreichbar über Navigation und Suche.
- **Stammdaten nach Kategorie gruppiert:** Die Zusatzfelder-Verwaltung ist jetzt nach Kategorie
  gruppiert dargestellt (übersichtlicher bei vielen Kategorien).

## 1.84.0

- **Schlüssel – Erfassung & Zuordnung (Oberfläche):** Bei Kategorien mit Kennzeichen „Schließanlage"
  erscheinen im Erfassungsformular jetzt Schlüsseltyp (Vorschlagsfeld mit Neuanlage) und Seriennummer.
  In der Artikelansicht gibt es die Karte „Schließungen" mit ausklappbarer Checkbox-Liste (mit Suche,
  nach Objekt gruppiert), um festzulegen, welche Türen der Schlüssel öffnet. Schaden-/Verlustmeldungen
  stehen für Schlüssel wie für alle Artikel zur Verfügung.
- **Stammdaten:** In den Einstellungen › Stammdaten lassen sich Objekte/Schließanlagen (optional mit
  Standort) und ihre Schließungen (Türen) pflegen; je Materialklasse ist „Schließanlage" umschaltbar.
- **Pfand bei der Ausgabe:** Beim Ausgeben eines Schlüssels kann ein Pfand/Kaution-Betrag erfasst
  werden; bei der Rücknahme wird er automatisch als zurückgegeben vermerkt.

## 1.83.0

- **Schlüssel/Schließanlagen – Grundlage (Backend):** Neue Kategorie-Eigenschaft „Schließanlage".
  Ist sie gesetzt, bekommen Artikel dieser Kategorie die Schlüssel-Felder: Schlüsseltyp (Lookup mit
  Vorschlägen, z. B. Winkhaus/Bartschlüssel) und Seriennummer/Prägung (durchsuchbar, darf leer sein).
  Neu sind Objekte/Schließanlagen (frei benannt oder mit Standort/Fahrzeug verknüpft) mit ihren
  Schließungen (Türen/Schlösser) sowie die n:m-Verknüpfung „welcher Schlüssel öffnet welche Schließung".
  Rückansicht je Schließung (welche Schlüssel, wer hat sie), Schlüssel-Ausgabeliste und Pfand/Kaution
  pro Ausgabe (auf der Quittung nachvollziehbar, bei Rücknahme als zurückgegeben markiert).
  Die Oberfläche (Erfassung, Schließungs-Auswahl, Verwaltung) folgt in den nächsten Versionen.

## 1.82.0

- **CUPS-Drucker direkt in der Software einrichten:** Neben der Auto-Erkennung gibt es jetzt einen
  Dialog „CUPS-Drucker einrichten". Das Programm listet die am Server erreichbaren Geräte (`lpinfo -v`)
  und die verfügbaren Treiber (`lpinfo -m`, durchsuchbar) auf; nach Eingabe eines Namens wird der
  Drucker per `lpadmin` in CUPS angelegt und gleich als Drucker-Profil übernommen. Treiber leer lassen
  = CUPS wählt automatisch (bzw. „driverless").
- **Fallback CUPS-Weboberfläche:** Sollte die Einrichtung per `lpadmin` nicht klappen (z. B. fehlende
  Rechte des Server-Prozesses), verweist die Fehlermeldung darauf – und es gibt einen jederzeit
  sichtbaren Link zur CUPS-Weboberfläche (`http://<server>:631/admin`), um den Drucker dort selbst
  einzurichten. Danach erscheint er in der Auto-Erkennung.

## 1.81.0

- **Mehrere Server-Drucker:** In den Einstellungen (Etiketten & Drucker) lassen sich jetzt beliebig
  viele Drucker hinterlegen – wahlweise als **CUPS-Warteschlange** oder direkt per **IP:Port (9100)**.
  Eine Auto-Erkennung liest die auf dem Server vorhandenen CUPS-Drucker aus. Jeder Drucker hat einen
  Typ (Etikettendrucker/Papierdrucker), optionale `lp`-Standardoptionen und einen **Testdruck-Knopf**;
  der zuletzt gemeldete Status wird angezeigt. Gedruckt wird direkt vom Server, nicht vom Endgerät.
- **Anwendungsfälle → Drucker:** Unter der Drucker-Liste wird je Anwendungsfall (Etiketten,
  Ausgabe-/Rückgabequittung, Berichte/Protokolle, Listen) festgelegt, welche Drucker verwendet werden.
  Papierdrucker sind nicht auf ein Format festgelegt – Format/Schacht wird je Anwendungsfall (oder beim
  Drucken) über `lp`-Optionen bestimmt (z. B. für den Kyocera TASKalfa mit mehreren Papierschächten).
- **Drucken-Knöpfe:** Überall dort, wo bisher ein PDF geöffnet wurde, gibt es jetzt einen
  „Drucken"-Knopf plus **PDF-Pfeilchen (↗)**. Ist genau ein Drucker zugeordnet, wird nach Bestätigung
  direkt gedruckt; bei mehreren erscheint eine Auswahl; ist kein Drucker hinterlegt, öffnet das
  PDF wie bisher zum Druck am Endgerät.

## 1.80.0

- **Nicht inventarisierten Artikel bei der Ausgabe schnell erfassen:** Wird auf der Materialausgabe
  (Scannen) eine Nummer gescannt/eingegeben, die noch nicht im Bestand ist, bietet das Programm jetzt
  an, den Artikel direkt als **vorläufigen** Artikel anzulegen (Typ wählen, optional Modell/Größe/
  Abteilung) und ihn anschließend sofort auszugeben. Ein Berechtigter kann die Angaben später
  ergänzen und den Artikel freigeben.

## 1.79.0

- **Monochrome Menü-Icons:** Die bunten Emoji in der Navigationsleiste und im Kachel-Startmenü
  (Handy/Tablet) wurden durch einheitliche, einfarbige Linien-Symbole ersetzt. Das Menü wirkt
  dadurch ruhiger und professioneller und sieht in hellem wie dunklem Design gleich aus.

## 1.78.0

- **Abteilungen in der globalen Suche:** Die Suche (Lupe oben) findet jetzt auch Abteilungen. Ein
  Klick auf eine Abteilung öffnet die Gesamtübersicht, gefiltert auf diese Abteilung.
- **Enter = Trefferliste + Attributsuche:** Drückt man in der Suche Enter (oder klickt die Lupe),
  öffnet sich die Gesamtübersicht wie gewohnt – gefiltert nach dem eingegebenen Text. Dabei werden
  Größen-Angaben automatisch erkannt: „orange L" filtert z.B. auf Modell „orange" und Größe „L".
  Ohne Größen-Angabe wird breit über die Freitextsuche gesucht.
- **Personen ausblenden:** Einzelne Personen (z.B. das System-/Admin-Konto) lassen sich aus der
  Personenliste ausblenden, ohne sie zu deaktivieren. Ausgeblendete Personen tauchen weder in der
  Liste noch in der globalen Suche auf; über „Ausgeblendete Personen anzeigen" bleiben sie
  erreichbar und lassen sich wieder einblenden.

## 1.77.0

- **Mindestbestand-Warnung sichtbarer:** Unterschrittene Mindestbestände erscheinen jetzt auch als
  Kachel auf der Startseite und als Hinweis in der Glocke (im Zuständigkeitsbereich), zusätzlich zur
  bisherigen Auswertung und Telegram-Meldung.
- **Ausgebender im Verlauf:** Der Ausgabe-Verlauf eines Artikels zeigt jetzt die Spalte „Ausgegeben
  von" (und ggf. wer zurückgenommen hat).

## 1.76.0

- **Klickbare Kennzahlen in der Auswertung:** Kennzahlen, Balken und Säulen lassen sich anklicken
  und öffnen ein Pop-up mit genau den Artikeln, die dahinterstecken – z.B. „Artikel im Bestand",
  „Bestand nach Status" (je Status), „Nach Abteilung", „Auslastung je Typ" und die Größen-Matrix
  (Typ + Größe). Von dort geht es direkt zum Artikel.
- **Dokumente im Artikel:** Die Artikelansicht hat eine neue Karte „Dokumente", die die erzeugten
  PDFs bündelt: Schaden-/Verlustmeldungen (PDF + Foto) und Ausgabe-/Rückgabequittungen der
  betreffenden Person(en). Prüf-/Wartungsprotokolle sind wie bisher direkt am Artikel einsehbar.
- Ergänzung: Die Karte „Historie" (Tagebuch) listet weiterhin alle Ereignisse chronologisch
  (Anlage, Status-Änderungen inkl. Reparatur/Verlust, Ausgabe/Rücknahme, Prüfungen, Wartungen,
  Meldungen, Logbuch); die Ausgabe-Tabelle heißt „Ausgabe-Verlauf".

## 1.74.0

- **Leihgaben / temporäre Ausgaben:** Ausgaben mit Rückgabedatum werden jetzt als Leihgaben
  geführt. Die Startseite zeigt eine Kachel „Leihgaben / Rückgaben" (überfällige hervorgehoben),
  überfällige Rückgaben erscheinen zusätzlich in der Glocke.
- **Lagerort-Kurzbeschreibung sichtbar:** Die in den Stammdaten hinterlegte Beschreibung eines
  Lagerorts (z.B. „Kiste", „Tasche") lässt sich in der Artikelansicht über ein „?" (Hover/Klick)
  und in der Lagerort-Inventur direkt einsehen.

## 1.73.0

- **Ausgabequittung – neu vs. bereits vorhanden:** Auf der Ausgabequittung sind jetzt „Neu
  ausgegebene Artikel" und (optional) „Bereits beim Helfer" getrennt aufgeführt. Über eine
  Checkbox lässt sich der vorhandene Helferbestand wahlweise mitdrucken.

## 1.72.0

- **Kachel-Startmenü für Handy/Tablet:** Auf dem Smartphone gibt es jetzt ein Kachel-Menü (zwei
  Kacheln breit) mit Symbol und Name je Kachel. Gruppen (Übersicht, Artikel, Materialwart, Admin)
  öffnen ihre Unterkacheln; eine breite „Zurück"-Leiste unten führt zurück. Die Kacheln richten
  sich nach den Rechten des Nutzers.
- **Profil oben rechts:** „Mein Konto" und „Abmelden" liegen jetzt hinter einem Profil-Kreis
  (Initialen) oben rechts.

## 1.71.0

- **Inventur per Lagerort-QR:** Jeder Lagerort (Standort, Etage, Raum, Schrank, Fach …) hat jetzt
  einen scannbaren Code mit QR/Barcode. Über die neue Seite **„Lagerort-Inventur"** wählt man einen
  Lagerort (per QR-Scan oder Auswahl), sieht dessen QR-Code zum Ausdrucken/Aushängen und scannt bzw.
  tippt anschließend die enthaltenen Artikel ein. Die erfassten Artikel werden dem Lagerort
  **zugeordnet** und als **inventarisiert** markiert; eine Zusammenfassung zeigt Zugeordnete/neu
  Verschobene und nicht gefundene Nummern.

## 1.70.0

- **Fehlerbehebungen (Bug-Runde):**
  - **Artikel-Historie:** Neue Karte „Historie" in der Artikelansicht zeigt jetzt alle Ereignisse
    des Artikels chronologisch (Anlage, Status-Änderungen, Ausgabe/Rücknahme, Prüfungen,
    Wartungen, Meldungen, Logbuch …) – nicht mehr nur einen Eintrag. Die bisherige Tabelle heißt
    jetzt „Ausgabe-Verlauf".
  - **Scanner am Handy:** Das Scan-Fenster hat einen dauerhaft sichtbaren „Schließen"-Knopf; der
    Inhalt scrollt jetzt sauber innerhalb des Fensters, sodass es sich auf dem Smartphone immer
    schließen lässt.

## 1.69.0

- **Fahrzeug-Logbuch:** Fahrzeuge haben jetzt ein Logbuch. Erledigte Wartungen/Termine erzeugen
  **automatisch** einen Eintrag (mit Datum, Kilometerstand und erfassten Angaben), zusätzlich
  können Berechtigte **manuelle Einträge** anlegen (Fahrt, Schaden, Hinweis, Sonstiges – mit
  Titel, Notiz, Datum, Kilometerstand). Das gesamte Logbuch lässt sich als **PDF** mit
  Organisations-Briefkopf ausgeben. Anzeige in der Artikelansicht des Fahrzeugs.

## 1.68.0

- **Modelle unter einem Typ:** Zu jedem Artikeltyp lässt sich eine verwaltete Modell-Liste
  pflegen (z.B. Handfunkgerät → „Motorola XY", „Hytera Z") – Verwaltung in den Stammdaten (neue
  Karte „Modelle"). Beim Erfassen eines Artikels wird das Modell als Auswahl angeboten (mit
  Möglichkeit, direkt ein neues anzulegen). Bereits genutzte Modelle werden beim Löschen nur
  archiviert. Der Modellname bleibt weiterhin in der Artikelübersicht/Suche sichtbar.

## 1.67.0

- **Mengenerfassung übernimmt Standardeinstellungen:** Beim Anlegen mehrerer Artikel gelten nun
  die Typ-Voreinstellungen für alle erzeugten Artikel – der **PSA-Haken** wird aus der
  Typ-Voreinstellung vorbelegt (und ist im Formular umstellbar), der Ausgebbar-Standard greift
  wie gehabt automatisch. Zusätzlich lassen sich die **Zusatzfelder** (je Kategorie/Typ) einmal
  ausfüllen und werden für alle angelegten Artikel übernommen.

## 1.66.0

- **Standard-Einstellungen je Typ:** In den Stammdaten (neue Karte „Typ-Voreinstellungen") lässt
  sich je Artikeltyp festlegen, ob neue Artikel dieses Typs standardmäßig **ausgebbar** sind
  (sonst gilt der Kategorie-Standard) und ob der **PSA-Haken** gesetzt ist. Beim Erfassen eines
  Artikels werden diese Werte automatisch vorbelegt, sobald der Typ gewählt ist; Einzelartikel
  können weiterhin abweichen. (Prüf-/Wartungsregeln sind wie bisher pro Typ konfigurierbar.)

## 1.65.0

- **Eigene Felder je Typ/Kategorie:** In den Stammdaten lassen sich frei definierbare Zusatzfelder
  anlegen (Text, Zahl, Auswahl, Ja/Nein, Datum) und einer Kategorie oder einem Artikeltyp zuordnen –
  z.B. „Frequenzbereich" oder „Rufname" für Funkgeräte. Einer Kategorie zugeordnete Felder gelten
  auch für deren Unterkategorien. Felder können als Pflichtfeld markiert und archiviert werden.
- Beim Erfassen und in der Artikelansicht werden die passenden Zusatzfelder automatisch angezeigt
  und je Artikel gespeichert.

## 1.64.0

- **Termin-Erinnerungen:** Je Prüf-/Terminart lassen sich in den Stammdaten beliebig viele
  Erinnerungen hinterlegen (X Tage vor dem Termin, mit Dringlichkeit niedrig/normal/hoch). Rückt
  ein Termin näher, geht automatisch eine Telegram-Benachrichtigung raus (neues Ereignis „Termin /
  Wartung fällig"); überfällige Termine werden besonders markiert. Doppelversand wird vermieden,
  bei Terminänderung werden Erinnerungen wieder freigegeben.
- **Fälligkeits-Übersicht:** Die Startseite zeigt eine Kachel „Anstehende Termine" (nächste 30
  Tage, überfällige hervorgehoben) im Zuständigkeitsbereich; die Zahl erscheint zusätzlich in der
  Glocke.
- **Wartungsprotokolle am Artikel:** Abgeschlossene Termine/Wartungen erscheinen jetzt auch bei
  Nicht-PSA-Artikeln (z.B. Fahrzeugen) im Protokollverlauf der Karte „Termine & Wartung".

## 1.63.0

- **Termine durchführen / abhaken:** In der Karte „Termine & Wartung" gibt es neben jedem Termin
  einen Knopf **„durchführen"** (Recht „Termine/Wartung pflegen"). Damit lässt sich die Prüfung
  jederzeit – auch vorzeitig – erledigen: die hinterlegte Checkliste wird Punkt für Punkt
  abgehakt, die Erfassungsfelder (z.B. Öl-Typ, Kilometerstand) ausgefüllt, eine Gesamtbemerkung
  und optional ein Beleg/Protokoll hinterlegt.
- **Folgetermin wählbar:** Beim Abschluss wird der nächste Termin bestimmt – **automatisch aus
  dem Intervall** (Monate und/oder Kilometer), **Termin behalten**, **eigenes Datum/km** oder
  **kein Folgetermin**. „Zuletzt erledigt" wird am Artikel vermerkt.
- Technisch nutzt das Abhaken dieselbe Prüf-/Protokoll-Maschinerie wie die PSA-Prüfungen; der
  Artikelstatus bleibt dabei unverändert.

## 1.62.0

- **Größenwerte je Größenart:** Zu jeder Größenart lassen sich in den Stammdaten die erlaubten
  Werte festlegen (z.B. Shirt: S, M, L, XL, XXL; Handschuhe: 6, 7, 8, 9, 10, 11). Im
  Größenprofil (Person bzw. eigenes Konto) wird dann eine Auswahlliste angeboten; ohne
  hinterlegte Werte bleibt es ein Freitextfeld.
- **Materialverwalter-Zuständigkeit klarer:** Die Kategorie-Auswahl beim Festlegen von
  Materialverwaltern zeigt Unterkategorien jetzt mit ihrer Oberkategorie an („Funk / Digital").
  Damit lassen sich Materialverwalter für eine komplette Abteilung (Kategorie = alle) oder gezielt
  für eine (Unter-)Kategorie – auch innerhalb einer Abteilung – festlegen.

## 1.61.0

- **Unterkategorien:** Kategorien können jetzt eine Ebene an Unterkategorien haben (z.B. Funk →
  Analog, Digital, DME, FME). Eine Unterkategorie **erbt** die Standards und Stammdaten der
  Oberkategorie und kann sie überschreiben:
  - der Ausgebbar-Standard wird beim Anlegen übernommen (danach je Unterkategorie einstellbar),
  - Wartungs-/Terminzuweisungen der Oberkategorie gelten auch für Artikel der Unterkategorie,
  - wer für die Oberkategorie zuständig ist (Materialverwalter), ist es auch für die Unterkategorien
    (Aufgaben-Eingang, Meldungen, Auswertung).
  Artikel und Typen können wahlweise an der Ober- oder an einer Unterkategorie hängen. Verwaltung
  in den Einstellungen → Stammdaten (neue Karte „Unterkategorien").

## 1.60.0

- **Wartung/Termine zuweisen – Kategorie, Typ oder Einzelartikel:** Prüf-/Terminarten lassen sich
  grundsätzlich einer **Kategorie** oder einem **Artikeltyp** zuweisen (gilt dann für alle Artikel
  darin). Am **Einzelartikel** kann davon abgewichen werden: zusätzliche Arten hinzufügen oder
  geerbte für diesen Artikel entfernen.
- **Termine je Artikel:** In der Artikelansicht zeigt die neue Karte „Termine & Wartung" alle
  geltenden Prüfarten (mit Herkunft Kategorie/Typ/Artikel). Berechtigte (Recht „Termine/Wartung
  pflegen") tragen je Art den **fälligen Termin** (Datum und – bei km-basierten Arten –
  Kilometerstand) ein; überfällige Termine werden hervorgehoben.
- (Das Abhaken/Durchführen der Termine samt Protokoll und Auto-Folgetermin folgt in v1.61.)

## 1.59.0

- **Prüf-/Terminarten (Wartung) – Stammdaten:** Neue Stammdatenliste für wiederkehrende
  Prüfungen/Termine (z.B. TÜV, Ölwechsel, Inspektion). Je Art lassen sich eine Checkliste
  (Checkpunkte, wiederverwendet aus dem Prüfwesen), **Erfassungsfelder** (z.B. „Öl-Typ",
  „Kilometerstand"), ein **Standard-Intervall** in Monaten und/oder Kilometern (km-basiert
  optional) sowie ein **Ereignis-Auslöser** (bei Rückgabe / nach Reparatur-Rücknahme) hinterlegen.
  Arten können archiviert statt gelöscht werden.
- **Neues Recht „Termine/Wartung pflegen":** eigenes, pro Rolle und pro Benutzer schaltbares Recht
  (`maintenance`) – Grundlage für das Eintragen und Abhaken von Terminen (folgt in v1.60).

## 1.58.0

- **Fahrzeug als Lagerort (Grundlage):** Ein Artikel kann als **Fahrzeug** gekennzeichnet werden
  (mit Kennzeichen, Fahrgestellnummer und Erstzulassung). Ein Fahrzeug ist damit zugleich ein
  Lagerort im Baum: In der Artikelansicht lässt es sich „als Lagerort aktivieren" und einem
  Standort unterordnen. Anschließend kann das Fahrzeug eigene Unterknoten (Schränke, Fächer,
  Taschen) und Artikel enthalten – wie jeder andere Lagerort.
- Vorbereitung für die nächsten Schritte: Wartungszyklen (TÜV/Öl/Inspektion) und Logbuch folgen
  in eigenen Versionen.

## 1.57.0

- **Meldungen versicherungs-/polizeitauglich:** Schadens- und Verlustmeldungen erfassen jetzt
  alle für eine Versicherung bzw. Anzeige bei der Polizei nötigen Angaben: Datum/Uhrzeit des
  Vorfalls, Ort bzw. letzter bekannter Standort, Hergang, bei Verlust „Diebstahl" mit
  Polizei-Aktenzeichen, geschätzter Wert/Schadenshöhe, Zeugen und Rückfrage-Kontakt.
- **Organisations-Briefkopf:** Die Meldungs-PDFs tragen jetzt Logo, Name, Anschrift, Vorstand
  und Kontakt der Organisation. Diese Daten pflegt der Admin unter Einstellungen → „Etiketten &
  Drucker" (Abschnitt „Organisationsdaten").
- **Pflichtangaben & Vollständigkeit:** Pflicht sind Datum, Ort und Hergang. Fehlt etwas, wird die
  Meldung als **unvollständig** markiert (deutlicher Hinweis auf dem PDF „nicht zur Vorlage
  geeignet"). Zuständige Materialverantwortliche sehen unvollständige Meldungen als Hinweis in der
  Glocke und können sie jederzeit vervollständigen; Polizei-Aktenzeichen und Wert lassen sich
  nachträglich ergänzen – das PDF aktualisiert sich automatisch.
- **Nachfrage bei fehlenden Pflichtangaben:** Beim Melden werden fehlende Pflichtfelder
  aufgelistet; der Meldende kann wählen, ob er die Meldung trotzdem als unvollständig speichert
  oder zurück zum Korrigieren geht. Der Melde-Dialog lässt sich jederzeit abbrechen (z. B. bei
  versehentlichem Antippen), ohne dass eine Meldung angelegt wird.

## 1.56.0

- **Schadens-/Verlustmeldungen:** Über einen neuen Knopf „Schaden / Verlust melden" (in der
  Artikelansicht und unter „Meine Artikel") können berechtigte Nutzer einen Schaden oder Verlust
  melden – mit Beschreibung und optionalem Foto. Automatisch passiert dabei:
  - **Statuswechsel** des Artikels: Schaden → „In Reparatur", Verlust → „Verschollen".
  - **Aufgabe im Eingang** der zuständigen Materialverantwortlichen (neue Seite „Schaden/Verlust")
    mit „erledigt"-Funktion; die Zahl offener Meldungen erscheint in der Glocke.
  - **PDF-Meldung** (Schadens-/Verlustmeldung) – ansehbar, druck- und exportierbar.
  - **Telegram-Benachrichtigung** der Materialverantwortlichen inklusive des PDF-Dokuments.
  - Das Melden ist ein eigenes, pro Rolle und pro Benutzer abschaltbares Recht.

## 1.55.0

- **Prüfprotokoll als PDF:** Zu jeder abgeschlossenen Prüfung lässt sich ein sauberes
  Protokoll-PDF erzeugen (Artikel, Ergebnis, Prüfer/Datum, alle Checklisten-Punkte mit
  „i.O./nicht i.O." und Anmerkungen, Gesamt-Bemerkung, Unterschriftsfeld). Abrufbar direkt
  nach Abschluss der Prüfung und jederzeit über die Prüfprotokoll-Liste in der Artikelansicht
  – zusätzlich zum optionalen Upload eines externen Dokuments.

## 1.54.0

- **Prüfregeln je Einzelartikel (Override):** In der Artikelansicht kann für einen einzelnen
  PSA-Artikel „Eigene Prüfregeln" aktiviert werden. Ist das gesetzt, gelten ausschließlich die
  am Artikel hinterlegten Regeln statt der Typ-Regeln. Zusätzlich zu den bekannten Auslösern
  (bei Rückgabe / nach X Ausleihen / nach X Wäschen / alle X Monate) gibt es hier den Auslöser
  **„einmalig bei nächster Rückgabe"** – die Prüfung wird genau einmal fällig und danach nicht
  wieder.

## 1.53.1

- **Ausgegebene PSA prüfbar:** Prüfungen werden jetzt auch für **ausgegebene** PSA-Artikel
  ausgelöst und können durchgeführt werden, ohne die laufende Ausleihe zu beenden. Fällige
  Artikel sind über ein neues Merkmal „prüfpflichtig" markiert – verfügbare Artikel werden
  weiterhin über den Status „zu prüfen" für die Ausgabe gesperrt, ausgegebene bleiben
  ausgegeben. Der Auslöser „nach X Ausleihen" greift bereits bei der Ausgabe, der Monats-Auslöser
  auch bei ausgegebenen Artikeln.
- **Dashboard „Zu prüfen":** Die Gesamtübersicht zeigt oben eine Kachel mit allen aktuell
  prüfpflichtigen PSA-Artikeln (inkl. Hinweis „ausgegeben") und verlinkt direkt zur Prüf-Seite.
  Zusätzlich taucht die Zahl fälliger Prüfungen in den Benachrichtigungen (Glocke) auf.
- **Robuster Prüfvorgang:** Abgeschlossene Prüfungen sind gegen versehentlichen Doppelabschluss
  bzw. nachträgliche Änderungen geschützt. Eine versehentlich gestartete Prüfung kann jetzt über
  „Verwerfen" abgebrochen werden – der Artikel bleibt dabei prüfpflichtig.

## 1.53.0

- **Geführter Prüfvorgang:** Fällige PSA-Artikel (Status „Zu prüfen") erscheinen unter dem
  neuen Menüpunkt **Prüfungen**. Die zugeordnete Checkliste wird Punkt für Punkt abgearbeitet:
  jeder Punkt lässt sich als „in Ordnung" ✓ oder „nicht in Ordnung" ✗ mit optionaler Anmerkung
  markieren; zusätzlich gibt es ein Freitextfeld für eine Gesamtbemerkung. Die Prüfung kann
  jederzeit **pausiert** und später fortgesetzt werden.
- **Prüfergebnis bestimmt Folgestatus:** Beim Abschluss wählt die prüfende Person „bestanden"
  (Artikel wird wieder „Verfügbar") oder „nicht bestanden" (Folgestatus „In Reparatur" oder
  „Ausgemustert"). Die abschließende Person wird als Prüfer vermerkt.
- **Prüfprotokolle im Artikel:** Jede abgeschlossene Prüfung wird dauerhaft am Artikel
  gespeichert (Datum, Prüfer, Ergebnis, alle Checklisten-Punkte samt Anmerkungen) und ist in
  der Artikelansicht einsehbar. Ein externes Prüfprotokoll (z. B. PDF/Foto) kann zusätzlich
  je Prüfung hochgeladen werden.
- **Benachrichtigung „Prüfung fällig":** Wird ein Artikel prüfpflichtig, geht eine
  Telegram-Benachrichtigung an die materialverantwortlichen Empfänger sowie – sofern verknüpft –
  direkt an die zuletzt ausleihende bzw. zurückgebende Person.

## 1.52.0

- **Prüfwesen (PSA) – Grundlage:** Artikel können als „PSA" gekennzeichnet werden. Je
  Artikeltyp lassen sich in den Stammdaten Prüfregeln festlegen – Auslöser „bei jeder
  Rückgabe", „nach X Ausleihen", „nach X Wäschen" oder „alle X Monate" – jeweils mit einer
  zugeordneten Prüf-Checkliste (mehrere Regeln je Typ möglich). Prüf-Checklisten werden
  ebenfalls in den Stammdaten angelegt.
- **Nutzungszähler & Auto-Status „Zu prüfen":** Artikel zählen Ausleihen (bei Ausgabe) und
  Wäschen (neuer „Gewaschen"-Knopf in der Artikelansicht). Wird eine Prüfregel fällig,
  wechselt der PSA-Artikel automatisch in den neuen Status „Zu prüfen" und ist bis zur
  Freigabe für die Ausgabe gesperrt. (Die geführte Checklisten-Abarbeitung folgt im
  nächsten Schritt; bis dahin gibt der Status-Wechsel den Artikel wieder frei.)

## 1.51.0

- **Rechte einzeln je Benutzer entziehbar:** Der Admin kann jedem Benutzer – unabhängig von
  dessen Rolle – einzelne Rechte entziehen (Einstellungen → Benutzer → bearbeiten →
  „Einzelne Rechte entziehen"), z.B. bei Missbrauch. Das entzogene Recht wird zusätzlich zu
  den Rollen-Rechten abgezogen; die restlichen Rechte der Rolle bleiben bestehen.

## 1.50.0

- **Materialanfragen als Berechtigung:** Ob jemand Materialanfragen stellen darf, ist jetzt
  ein eigenes, vom Admin je Rolle einstellbares Recht (Einstellungen → Rollen & Rechte →
  „Materialanfragen stellen"). Standardmäßig für Materialverwalter, Helfer, Nur-lesend und
  Eigen-Nutzer aktiv; der Menüpunkt und das Anfrageformular erscheinen nur mit dem Recht
  (der Bearbeitungs-Eingang bleibt den zuständigen Materialverwaltern/Admins vorbehalten).

## 1.49.0

- **Materialanfragen / Reservierung:** Neuer Menüpunkt „Anfragen" – jeder Nutzer kann selbst
  Material anfragen (Art, Größe, Menge, optionaler Wunsch-Zeitraum, Bemerkung). Die Anfrage
  erscheint bei den zuständigen Materialverwaltern (nach Materialklasse) und bei
  Administratoren als Aufgabe im „Eingang" und kann dort genehmigt, als erledigt markiert
  oder mit Begründung abgelehnt werden. Der Bestand wird dabei nicht geblockt.
- **Benachrichtigung:** Neue Anfragen können per Telegram gemeldet werden (neues Ereignis
  „Neue Materialanfrage" in der Benachrichtigungssteuerung).

## 1.48.0

- **Ausgabe-/Rückgabe-Quittungen:** Pro Person lassen sich Quittungen als PDF erzeugen –
  die Ausgabe-Quittung listet die aktuell an die Person ausgegebenen Artikel, die
  Rückgabe-Quittung die heute zurückgegebenen sowie die weiterhin verbleibenden Artikel.
  Mit Unterschriftsfeldern für ausgebende Person und Empfänger; wahlweise in zwei
  Ausfertigungen (intern + zum Mitgeben).
- **Digitale Unterschrift oder Papier:** Die Unterschrift kann direkt am Gerät geleistet
  werden (wird in die PDF eingebettet und abgelegt) – alternativ Quittung ausdrucken,
  unterschreiben und als Foto/Scan hochladen.
- **Ablage & Einsicht:** Abgelegte Quittungen sind bei der Person (Personen-Seite) und für
  den Empfänger unter „Mein Konto" einsehbar/herunterladbar; die ausgebende Person ist
  vermerkt.

## 1.47.0

- **Verwaltbare Größenarten:** Die Größenfelder im Personenprofil sind jetzt in den
  Stammdaten frei verwaltbar (z.B. „Krawatte" ergänzen, umbenennen, aus-/einblenden). Die
  bisherigen festen Felder (Oberteil, Hose, Schuhe, Kopf, Handschuhe) sind als Standard
  angelegt; vorhandene Werte werden automatisch übernommen. Person, Konto-Selbstpflege und
  der Ausgabe-Hinweis nutzen die konfigurierten Arten.

## 1.46.0

- **Ausgebbar-/Zuordnungs-Kennzeichen:** Pro Materialklasse ist in den Stammdaten
  einstellbar, ob Artikel ausgegeben/persönlich zugeordnet werden können; einzelne Artikel
  können das überschreiben (im Erfassungsformular). Nicht-ausgebbare Artikel bieten keine
  Ausgabe an, und die Ausgabe wird serverseitig blockiert.
- **Personen-Größenprofil:** Feste Größenfelder je Person (Oberteil, Hose, Schuhe, Kopf,
  Handschuhe). Pflegbar durch die Person selbst („Mein Konto") und durch Admin/
  Materialverwalter (Personen-Seite). Bei der Materialausgabe werden die Größen des
  Empfängers als Hinweis angezeigt.

## 1.45.0

- **Auswertung nur für Berechtigte, mit Zuständigkeit:** Die Auswertung ist jetzt nur noch
  für Administratoren und ernannte Materialverwalter sichtbar. Materialverwalter werden in
  den Einstellungen (Benutzer) je Abteilung und Materialklasse zugewiesen und sehen im
  Dashboard ausschließlich ihre Abteilung(en) und Klasse(n); Administratoren sehen alles.
  Der Menüpunkt erscheint nur bei Zugriff.
- **Mindestbestand feiner steuerbar:** Mindestbestände werden jetzt pro Typ – optional pro
  Größe (z.B. „T-Shirt Größe M") – über den Gesamtbestand festgelegt und lassen sich
  zusätzlich für einen Lagerplatz beliebiger Ebene abweichend überschreiben. Pflege in den
  Stammdaten (0 = aus, weiterhin Standard aus). Bestehende Typ-Mindestbestände werden
  automatisch übernommen.
- **Benachrichtigung bei Unterschreitung:** Unterschreitet der verfügbare Bestand eine
  Schwelle, geht (zusätzlich zur Dashboard-Warnung) eine Telegram-Meldung an die für das
  neue Ereignis „Mindestbestand unterschritten" ausgewählten Empfänger (Personen/Gruppen/
  Rollen) – je Unterschreitung genau einmal, erneut erst nach Wiederauffüllung.

## 1.44.0

- **Rückgabedatum terminierbar:** Bei der Ausgabe (einzeln, aus der Artikelseite und in der
  Sammelausgabe) lässt sich optional ein „Rückgabe bis"-Datum festlegen. Überschrittene
  Termine erscheinen im Dashboard unter „Überfällige Rückgaben".
- **Mindestbestand je Typ (Standard aus):** In den Stammdaten kann pro Artikeltyp ein
  Mindestbestand gesetzt werden (0 = aus, so ist die Funktion standardmäßig deaktiviert,
  auch für Kleidung). Unterschreitet der verfügbare Bestand die Schwelle, warnt das
  Dashboard.
- **Erweitertes Auswertungs-Dashboard:** Neue Kennzahlen übersichtlich angeordnet –
  Mindestbestand-Warnung, überfällige Rückgaben, Auslastung je Typ (verfügbar/ausgegeben),
  verfügbare Stück nach Größe, Aktivität der letzten 12 Monate (Zugänge/Ausgaben/Rücknahmen)
  und Fundquote je Inventur – zusätzlich zu Status-, Lagerort-, Abteilungs- und
  Top-Ausgaben-Übersicht.

## 1.43.0

- **Auswertung (Dashboard):** Neuer Menüpunkt „Auswertung" mit Kennzahlen auf einen Blick –
  Gesamtbestand und vorläufige Artikel, Verteilung nach Status, Top-Lagerorte, Verteilung
  nach Abteilung und die meistausgegebenen Artikel (mit Balken und Direktlinks).
- **Datenqualitäts-Check:** Zweiter Reiter der Auswertung listet Auffälligkeiten zum
  Aufräumen: Artikel ohne Lagerort, ohne Foto, noch vorläufige, verschollene sowie mögliche
  Doppelerfassungen (gleiche Merkmale am selben Ort). Jeder Eintrag ist direkt zum Artikel
  verlinkt.

## 1.42.0

- **Termin-ICS ohne Wiederholungsregel:** Für Inventuren wird bewusst nur EINE Kalenderdatei
  mit genau EINEM Termin verschickt – bei jeder Änderung des Zeitplans und mit jeder
  Erinnerung neu, jeweils auf den nächsten Termin. Durch eine stabile Kennung entsteht im
  Kalender genau ein Eintrag, der automatisch auf den jeweils nächsten Termin rückt (statt
  einer Serie). Auch Vor-Erinnerungen bringen den passenden Einzeltermin als .ics mit.
- **Mehr Wiederholungs-Muster für Zeitpläne:** Neben „alle X Tage", „jede X. Woche" und
  „alle X Monate (fester Tag)" gibt es jetzt „jeden x. Wochentag im Monat" – z.B. „jeden
  zweiten Dienstag im Monat" oder „jeden letzten Freitag" (auch alle X Monate). Der nächste
  Termin wird automatisch korrekt berechnet.

## 1.41.0

- **Einstellbare Erinnerung vor einer Inventur:** Zu jeder geplanten Inventur (und jedem
  Zeitplan) lässt sich eine Standard-Vorlaufzeit hinterlegen (Tage vorher). Zusätzlich kann
  jede Person unter „Mein Konto" eine eigene Vorlaufzeit festlegen oder den Standardwert der
  Inventur übernehmen. Rechtzeitig vor dem Termin verschickt der Bot je Person genau eine
  Telegram-Erinnerung (verknüpftes Konto vorausgesetzt).
- **Regelmäßige Inventuren – nur ein Serientermin:** Für wiederkehrende Inventuren wird nur
  noch EINE Kalenderdatei (.ics) mit Wiederholungsregel verschickt – beim Anlegen bzw. bei
  Änderung des Zeitplans. Der Kalender zeigt damit automatisch alle künftigen Termine, ohne
  bei jeder Durchführung eine neue Datei zu schicken. Einmalig geplante Inventuren erhalten
  weiterhin genau einen Termin.

## 1.40.0

- **Inventur-Chronik über Telegram:** Berechtigte Nutzer (verknüpftes Konto mit
  Inventur-Recht) können im Bot per Menü „📚 Inventur-Chronik" oder Befehl `/chronik` die
  Liste vergangener Inventuren abrufen und zu jeder einzelnen den Abschlussbericht direkt
  als PDF ins Telegram bekommen. Für nicht berechtigte Chats bleibt die Chronik gesperrt.
- **Termin-Datei (.ics) bei Inventur-Erinnerungen:** Wenn eine geplante Inventur automatisch
  ansteht/angelegt wird, verschickt der Bot zusätzlich eine Kalenderdatei (.ics), die sich
  mit einem Tipp in den eigenen Kalender übernehmen lässt.
- **Symbole in der Navigationsleiste:** Alle Menüpunkte haben jetzt ein Symbol – oben in der
  Kopfzeile, in der Handy-Fußleiste und im „Mehr"-Menü –, was die Orientierung erleichtert.

## 1.39.0

- **Robustere Telegram-Benachrichtigungen:** Ausgehende Ereignis-Meldungen werden nicht
  mehr direkt im Ablauf verschickt, sondern in eine Hintergrund-Warteschlange gelegt und
  mit automatischer Wiederholung zugestellt. Aktionen (z.B. Inventur abschließen) sind
  dadurch sofort fertig, und kurze Telegram-/Netzstörungen führen nicht mehr zu verlorenen
  Meldungen.
- **Bilder beim Upload verkleinern (admin-einstellbar):** In Einstellungen → Sicherheit
  lässt sich eine automatische Verkleinerung großer Fotos aktivieren und konfigurieren
  (maximale Kantenlänge und JPEG-Qualität). Das spart Speicherplatz auf dem Server und
  beschleunigt die Detailansicht. Standardmäßig aus; gilt für neu hochgeladene Bilder.
- **Bessere Bedienbarkeit/Barrierefreiheit:** Deutlich sichtbarer Fokusrahmen bei
  Tastaturbedienung (Tab-Taste), Beschriftungen für Screenreader an den Symbol-Schaltflächen
  (Suche, Glocke, Design, Schließen).

## 1.38.0

- **Berichte-Archiv:** Beim Abschließen einer Inventur wird der Bericht dauerhaft
  archiviert (PDF im Datenverzeichnis + Snapshot in der Datenbank). Unter Inventur →
  „Archiv" lassen sich vergangene Inventuren jederzeit online einsehen – mit Kennzahlen,
  den Listen fehlend/gefunden/ignoriert und PDF-Download –, unabhängig davon, ob sich der
  Bestand später ändert. Ein Bericht kann auch jederzeit manuell archiviert werden.
- **Status „Verschollen" + Wiederfund-Meldung:** Nach einer Inventur können alle noch
  fehlenden Artikel per Knopfdruck auf „Verschollen" gesetzt werden. Taucht so ein Artikel
  später wieder auf (erneutes Scannen in einer Inventur oder Statuskorrektur), wird er
  automatisch wieder auf „Verfügbar" gesetzt und es geht eine Telegram-Benachrichtigung
  („Wiedergefunden …") raus. Verschollene Artikel lassen sich nicht ausgeben.
- **Materialliste je Person (PDF):** Auf der Personen-Seite gibt es pro Person „Liste (PDF)"
  und „drucken" – eine Liste der aktuell an diese Person ausgegebenen Artikel (Nummer, Typ,
  Größe, Lagerort, Ausgabedatum) mit Unterschriftszeile, zum Ablegen oder direkten Drucken.

## 1.37.0

- **Inventur-Abschlussbericht:** Zu jeder Inventur gibt es jetzt einen Bericht als PDF
  (zum Ausdrucken/Ablegen) und CSV (zur Weiterverarbeitung) – mit den Listen gefundene,
  fehlende und ignorierte Artikel, dem Fundort je Artikel sowie Kennzahlen (erwartet,
  gefunden, fehlend, Fortschritt). Buttons in der Inventuransicht; auch als Zwischenstand
  während der laufenden Inventur abrufbar.
- **Offline-fähige Inventur:** Fällt bei schwachem WLAN (Keller, Fahrzeughalle) die
  Verbindung aus, werden Scans lokal zwischengespeichert und automatisch gesendet, sobald
  wieder online. Ein Online/Offline-Hinweis und die Zahl wartender Scan-Pakete werden
  angezeigt („jetzt senden" möglich). Ein schlanker Artikel-Zwischenspeicher hält das
  Nachschlagen der Artikelnummern auch offline am Laufen.
- **Robuster & schneller:** SQLite läuft nun im WAL-Modus (mehrere Helfer können
  gleichzeitig scannen, ohne sich zu blockieren); das Frontend lädt große Seiten erst bei
  Bedarf (schnellerer Start, v.a. auf Tablets); abgeschlossene/abgesagte Inventuren werden
  in der Liste standardmäßig ausgeblendet (einblendbar).
- **Automatische Tests:** Neue pytest-Tests für die Kernabläufe (Anmeldung, Rechte,
  Ausgabe/Rücknahme, Inventur-Fortschritt/Stationen/Bericht, DSGVO-Anonymisierung) fangen
  Fehler künftig früher ab. Sie laufen automatisch im Verifikationsschritt mit, sofern die
  Test-Abhängigkeiten vorhanden sind.

## 1.36.0

- **Standort-Bestätigung im geführten Rundgang:** Springt die Inventur zur nächsten
  Station, muss der Helfer erst den Standort-QR dieser Station scannen – so ist
  sichergestellt, dass er wirklich am richtigen Ort steht. Bis zur Bestätigung ist das
  Erfassen gesperrt und ein Hinweis fordert zum Scannen auf; „erledigt → nächste" wird
  erst nach der Bestätigung frei. Für Ausnahmefälle gibt es „ohne QR bestätigen".
- **Zwischenstopp mit Sicherheitsabfrage:** Scannt der Helfer versehentlich einen anderen
  Standort-QR, erscheint eine Sicherheitsabfrage. Er kann diesen abweichenden Ort dann
  bewusst als Zwischenstopp inventarisieren (statt zwingend zum vorgesehenen Standort
  zurückzumüssen); die geführte Station bleibt offen und kann danach normal fortgesetzt
  werden.

## 1.35.0

- **Geführte, geplante Inventur (Rundgänge):** Eine Inventur kann jetzt aus geordneten
  Stationen bestehen. Die Reihenfolge legt man per Ziehen (Drag-and-drop) fest; während
  der Inventur führt die App Station für Station – „erledigt" springt automatisch zur
  nächsten, jede Station zeigt ihren eigenen Fortschritt (erfasst/offen) und lässt sich
  direkt als Scan-Ziel setzen. Stationen lassen sich einzeln anlegen oder in einem Schritt
  aus dem Geltungsbereich erzeugen.
- **Vorlagen (speicherbar & kombinierbar):** Ein Rundgang lässt sich als Vorlage speichern
  (auch direkt aus einer laufenden Inventur) und für neue Inventuren wiederverwenden.
  Mehrere Vorlagen können kombiniert werden – ihre Stationen werden zusammengeführt
  (doppelte Lagerorte automatisch entfernt). Neue Reiter „Vorlagen" und „Zeitpläne" im
  Inventur-Bereich.
- **Wiederkehrende Termine:** Zeitpläne erzeugen aus einer oder mehreren Vorlagen
  automatisch wiederkehrend Inventuren (z.B. „alle 3 Monate"), inklusive vorab
  freigeschalteter Teilnehmer und optionaler Telegram-Benachrichtigung beim Anlegen.
  „Jetzt anlegen", Pausieren/Aktivieren und Terminfortschreibung inbegriffen.
- **Spürbar schneller (Laufzeit/UX):** Datenbank-Indizes für die häufigsten Filter
  (Kategorie, Typ, Status, Standort, Ausgaben); N+1-Abfragen bei der Artikel-Übersicht,
  beim Export und in der Typ-Übersicht beseitigt (Standort-Baum wird einmal vorgeladen);
  Live-Aktualisierungen pausieren, wenn der Tab im Hintergrund liegt; nginx komprimiert
  jetzt (gzip) und cacht die Programm-Dateien dauerhaft. Details und weitere Vorschläge in
  `docs/Verbesserungsvorschlaege.md`.

## 1.34.0

- **Typ-Übersicht nach Standort gliederbar:** In der Typ-Übersicht gibt es die neue
  Aufschlüsselung „nach Standort (Pfad)" – zeigt je Artikeltyp die Verteilung über den
  vollständigen Lagerort-Pfad (Standort › Etage › … › Fach). Zeilen sind wie gewohnt
  filter-/sortierbar; Klick öffnet die gefilterte Gesamtübersicht.
- **Zentrale Suche (Lupe im Kopfbereich):** Neue globale Suche über die Lupe oben rechts
  (oder Tastenkürzel Strg/Cmd+K). Durchsucht in einem Feld alles, worauf der angemeldete
  Nutzer Zugriff hat – Artikel (Nummer, Typ, Modell, Größe, Eigenschaften, Bemerkungen),
  Personen, Lagerorte/Standorte (mit vollständigem Pfad), Benutzer und Gruppen sowie die
  Seiten und Einstellungsbereiche. Die Rechte werden serverseitig geprüft: „eigen"-Nutzer
  sehen nur ihre eigenen Artikel, Personen erscheinen nur mit Personen-/Ausgabe-Recht,
  Benutzer und Gruppen nur für Administratoren. Treffer sind angeklickt sofort verlinkt.

## 1.33.0

- **DSGVO – Protokoll-Aufbewahrung:** Einstellbare Aufbewahrungsfrist fürs Prüfprotokoll
  (Einstellungen → Sicherheit). Ältere Einträge werden automatisch gelöscht
  (Speicherbegrenzung); 0 = unbegrenzt.
- **DSGVO – Auskunft & Löschung von Personen:** Auf der Personen-Seite (für Admins)
  „Daten exportieren" (Auskunft nach Art. 15 als JSON) und „Anonymisieren" (Art. 17):
  Name/Notizen werden entfernt, verknüpfte Konten deaktiviert und Telegram-Verknüpfungen
  gelöst, während die Historie statistisch erhalten bleibt.
- **DSGVO – Telegram-Datenminimierung (standardmäßig aus):** Optional sendet der Bot
  keine Klarnamen mehr – Personennamen in Antworten und Meldungen werden durch
  „(vergeben)" bzw. „einem Nutzer" ersetzt. Empfohlen wegen des Drittland-Transfers.

## 1.32.0

- **Security-Header (Grundschutz/OWASP):** Der Webserver setzt jetzt Schutz-Header –
  gegen Clickjacking (X-Frame-Options/CSP frame-ancestors), MIME-Sniffing
  (X-Content-Type-Options), Referrer-Weitergabe und mit einer moderaten
  Content-Security-Policy; der Kamerazugriff für den Scanner bleibt erlaubt.
- **Datenschutz- & IT-Grundschutz-Bericht:** Zwei Bewertungsdokumente unter `docs/`
  (`Datenschutz-Review.md`, `BSI-Grundschutz-Bewertung.md`) mit Datenkatalog,
  Datenflüssen, Risiken und priorisierten, konkreten Verbesserungen.

## 1.31.0

- **Inventur auf beliebiger Ebene:** Beim Anlegen einer Inventur mit Geltungsbereich
  „nur bestimmte Lagerorte" lässt sich jetzt **jeder** Knoten wählen – nicht nur
  oberste Standorte, sondern auch eine einzelne Etage, ein Raum, ein Schrank oder ein
  Fach – jeweils inklusive allem darunter. Auswahl mit vollem Pfad zur eindeutigen
  Zuordnung. (Ziel-Standort per QR abscannen und geräteübergreifende Live-Anzeige des
  Fortschritts sind bereits vorhanden.)

## 1.30.0

- **Sicherheits-Härtung (Review):** Schutz gegen wiederholtes Passwort-/PIN-Raten
  (Rate-Limit beim Login: nach zu vielen Fehlversuchen kurze Sperre); Pfad-Traversal
  bei der Bild-Auslieferung ausgeschlossen; Bild-Upload prüft jetzt Dateigröße
  (max. 20&nbsp;MB) und ob es wirklich ein Bild ist; Bot-Token wird in der allgemeinen
  Einstellungs-Abfrage maskiert; längerer, schwer zu erratender Telegram-Verknüpfungs-
  Code. (Geprüft: keine SQL-/Command-Injection – durchgängig ORM –, kein XSS im UI,
  neutrale Login-Fehlermeldungen, alle Verwaltungs-Endpunkte rechtebeschränkt, Bot nur
  lesend und nur für freigeschaltete Chats.)

## 1.29.0

- **PDF-Auswertung per Telegram:** Freigeschaltete Chats können die Inventarliste als
  PDF anfordern – über den Menüpunkt „📄 PDF-Auswertung" oder den Befehl `/pdf`. Der
  Bot erzeugt die Liste und schickt sie als Dokument.

## 1.28.0

- **Gezielte Telegram-Benachrichtigungen:** Unter Einstellungen → Telegram lässt sich
  je Ereignis festlegen, wer es bekommt – alle freigeschalteten Chats und/oder
  bestimmte **Gruppen**, **Rollen** oder **Einzelpersonen**. Personen-/Gruppen-/
  Rollen-Empfänger erreichen nur Nutzer mit verknüpftem Telegram-Konto; gesperrte,
  pausierte oder deaktivierte Chats werden übersprungen.

## 1.27.0

- **Funktionsgruppen für Benutzer:** Neuer Bereich Einstellungen → „Gruppen". Frei
  definierbare Gruppen/Funktionsrollen (z.&nbsp;B. „Materialwart", „Abteilung JRK",
  „Zugführer") – unabhängig von den Berechtigungs-Rollen. Nutzer werden per
  Namenssuche zugeordnet. Das vereinfacht die Aufgabenzuteilung und ist die Basis für
  die gezielte Telegram-Benachrichtigung (folgt).

## 1.26.0

- **Telegram: sperren, pausieren, ans Konto koppeln.** Wartende Anfragen lassen sich
  jetzt auch **blockieren** (Blacklist) – solche Chats werden dauerhaft ignoriert und
  tauchen nicht mehr als Anfrage auf. Freigeschaltete Chats kann man **pausieren**
  (vorübergehend aus, ohne zu entfernen) oder wieder fortsetzen. Ist ein Chat mit
  einem Benutzerkonto verknüpft, ist der Telegram-Zugriff **an das Konto gekoppelt**:
  Wird das Konto deaktiviert, ist auch der Bot-Zugriff automatisch aus. Gesperrte,
  pausierte oder deaktivierte Chats erhalten auch keine Benachrichtigungen mehr.

## 1.25.0

- **Telegram-Freigabe per Klick:** Schreibt jemand dem Bot, ohne freigeschaltet zu
  sein, erscheint er unter Einstellungen → Telegram als „Wartende Verbindungsanfrage"
  mit Name, @Username und Chat-ID – der Admin kann ihn mit einem Klick freischalten
  oder verwerfen. Kein manuelles Eintippen der Chat-ID mehr nötig.
- **Namen bei freigeschalteten Chats:** Freigeschaltete Chats werden jetzt mit dem aus
  Telegram bekannten Namen angezeigt (statt nur der Chat-ID).

## 1.24.0

- **Beschreibung je Standort/Lagerort:** Jeder Knoten im Standort-Baum (bis zur Tasche)
  kann eine freie Beschreibung / Inhalts-Kurzübersicht bekommen (Einstellungen →
  Stammdaten). Sie wird im Baum angezeigt.
- **Testnachricht anpassbar & gezielt:** Vor dem Senden lässt sich der Text der
  Telegram-Testnachricht bearbeiten (mit vorgeschlagenem Standardtext) und wahlweise
  an alle freigeschalteten Chats oder gezielt an einen einzelnen Chat schicken.

## 1.23.0

- **Scanner mit Zielpunkt:** Der Web-Scanner zeigt jetzt einen Zielpunkt in der
  Bildmitte und liest gezielt den mittigen Code – so lässt sich bei mehreren Codes im
  Bild der gewünschte anpeilen.
- **Inventur-Teilnehmer per Namenssuche:** Statt langer Auswahlliste tippt man den
  Namen und bekommt passende Personen als Vorschlag.
- **Standorte per Drag-and-drop verschieben:** Im Standort-Baum (Einstellungen →
  Stammdaten) lassen sich Knoten durch Ziehen auf einen anderen Knoten verschieben;
  die Ebene wird automatisch angepasst.

## 1.22.0

- **Schnelle Mini-Bilder in der Übersicht:** Vorschaubilder werden serverseitig
  verkleinert und zwischengespeichert (`?w=64`) – die Liste lädt spürbar schneller.
- **QR-Codes robuster scannbar:** Erzeugte QR-Codes nutzen jetzt die höchste
  Fehlerkorrektur (~30 %), und der Web-Scanner verwendet – wo verfügbar – den nativen
  Browser-Barcode-Detektor sowie eine größere Scanfläche. Damit lassen sich auch
  aufgebügelte/matte/leicht gewölbte Codes zuverlässiger scannen (näher am Verhalten
  der normalen Kamera-App).
- **Standort-Etiketten mehrzeilig:** Lange Lagerort-Pfade werden auf dem QR-Etikett
  jetzt umgebrochen statt abgeschnitten.
- **Neue optionale Lagerort-Ebene „Tasche"** unterhalb von „Fach" (z.&nbsp;B. Fach →
  Tasche 1/2). Jede Ebene bleibt optional.

## 1.21.0

- **Suche mit Teilbegriffen:** Die Übersicht findet jetzt auch Teiltreffer – z.&nbsp;B.
  „X" findet „XS", „6" findet „164". Das allgemeine Suchfeld durchsucht zusätzlich
  Modell, Größe, Eigenschaften und Typ.
- **Übersicht aktualisiert sich live:** Änderungen (auch von anderen Geräten) und neue
  Standort-Zuordnungen aus der Inventur erscheinen automatisch, ohne neu zu laden.
- **Kleinere UI-Verbesserungen:** Benachrichtigungs-Fenster (Glocke) per „✕" schließbar;
  hinterlegtes Logo wird auch als Favicon/Browser-Icon genutzt; größere, besser
  lesbare Fußleiste am Handy.
- **Update-Diagnose:** Neuer Bereich „Update-Protokoll" unter Einstellungen → Update,
  der den letzten Update-Lauf des Host-Dienstes anzeigt – so ist sichtbar, warum ein
  Update ggf. nicht durchläuft (meist: Host-Update-Dienst noch nicht aktiviert).

## 1.20.0

- **Telegram: facettierte, überspringbare Suche im Menü.** Der geführte Bot-Flow
  (/menu → „Suchen / Bestand") lässt jetzt nach Typ zusätzlich nach **Größe, Modell,
  Eigenschaft (z.&nbsp;B. Farbe) und Lagerort** einschränken – jedes Kriterium ist
  optional und mit „alle" überspringbar. So sieht man z.&nbsp;B. wahlweise nur orange
  T-Shirts oder alle T-Shirts, nur eine Größe oder alle Größen. Am Ende „Ergebnis
  anzeigen" listet Anzahl verfügbar + Verteilung auf die Lagerorte.

## 1.19.0

- **Gesamtübersicht erweitert:** Jede Zeile zeigt jetzt vorne ein Mini-Bild des
  Artikels und alle Werte – u.&nbsp;a. das bisher fehlende **Modell**, den vollen
  **Lagerort-Pfad**, „Aktuell bei" und Eigenschaften. Die Tabelle ist horizontal
  scrollbar, sodass am Handy nichts mehr ausgeblendet wird. Zusätzlicher Filter
  „Lagerort (Pfad)" und Sortierung auch nach Modell/Lagerort/Aktuell bei.
- **Lagerort-Eingabe mit Autovervollständigung:** Beim Erfassen/Bearbeiten und in der
  Inventur wird der Lagerort je Ebene durch Tippen gesucht, mit Vorschlägen passender
  vorhandener Ebenen. Gibt es die Bezeichnung noch nicht, fragt das Programm vor dem
  Anlegen nach („… neu anlegen?").
- **Import in die Einstellungen verschoben:** Der Import ist jetzt unter Einstellungen
  → Import/Export erreichbar; der separate Menüpunkt „Import" entfällt.
- **QR-Druck im Standort-Baum:** In der Standort-Baumansicht (Einstellungen →
  Stammdaten) lässt sich je Knoten das QR-Etikett drucken („QR" je Zeile) sowie alle
  Standort-QR-Codes auf einmal.
- **Etiketten-Aufdruck erweitert:** Auf das Etikett lassen sich jetzt zusätzlich ein
  **Freitext** (z.&nbsp;B. „Eigentum DRK Ortsverein …"), die **Artikel-Eigenschaften**
  und der volle **Lagerort-Pfad** drucken – auswählbar unter Einstellungen → Etiketten
  & Drucker. Gilt für PDF- und P-touch-Druck.
- **Brother P-touch Direktdruck (PT-E550W u.&nbsp;a., experimentell):** Neben dem
  bisherigen PDF-Direktdruck gibt es jetzt einen nativen Raster-Druckmodus für
  Brother-P-touch-Netzwerkdrucker (PT-E550W/P750W/P710BT), die kein PDF verstehen.
  Umschaltbar unter Einstellungen → Etiketten & Drucker (Druckprotokoll „P-touch
  Raster") inkl. Bandbreite, Etikettenlänge, Auto-Schnitt und Korrektur-Schaltern
  (drehen/spiegeln). Der Druck erfolgt gemäß Brothers offizieller Raster-Referenz
  direkt über Port 9100.

## 1.18.0

- **Kritischer Fehler behoben (Backend-Start):** In `issues.py` beendete ein gerades
  Anführungszeichen innerhalb einer Fehlermeldung die Zeichenkette vorzeitig
  (Python-SyntaxError). Dadurch konnte das Backend seit Version 1.10.0 nicht starten.
  Behoben; zusätzlich prüft und blockiert das interne Verify-Skript jetzt auch bei
  Python-Syntaxfehlern (vorher war nur der Frontend-Build maßgeblich).

## 1.17.0

- **Automatischer Logout nach Inaktivität:** Nach einer einstellbaren Zeit ohne
  Aktivität (Maus, Tastatur, Tippen) werden Nutzer automatisch abgemeldet und beim
  nächsten Aufruf mit einem Hinweis zur Neuanmeldung geführt. Die Zeit legt der Admin
  unter Einstellungen → Sicherheit fest (0 = deaktiviert).
- **Telegram selbst verknüpfen:** Gibt der Admin es frei (Einstellungen → Telegram),
  können Nutzer unter „Mein Konto" ihr Telegram-Konto eigenständig verknüpfen – per
  erzeugtem Code, den sie dem Bot als `/link CODE` senden (mit Schritt-für-Schritt-
  Anleitung). Verknüpfte Nutzer dürfen den Bot abfragen, ohne dass der Admin ihre
  Chat-ID manuell freischalten muss.

## 1.16.0

- **Telegram-Menüführung per Buttons:** Statt Befehle zu tippen, führt `/menu` (oder
  `/start`) durch antippbare Schaltflächen: „Bestand prüfen" → Typ wählen → Größe
  wählen → Ergebnis, dazu „Offene Ausgaben" und „Hilfe". Nach jeder Antwort gibt es
  einen „‹ Menü"-Knopf zurück. So ist die Bedienung auch ohne Kenntnis der Befehle
  möglich.

## 1.15.0

- **Telegram-Anbindung – ausgehende Benachrichtigungen:** Der Server kann Ereignisse
  an Telegram melden – neue vorläufige Artikel sowie Start/Abschluss einer Inventur
  (je Ereignis an-/abschaltbar). Einrichtung unter Einstellungen → Telegram.
- **Telegram-Einrichtungsassistent:** Schritt-für-Schritt-Anleitung inkl. der
  Telegram-Seite (Bot per @BotFather anlegen, Token holen, Bot anschreiben,
  Chat-ID freischalten) plus Testnachricht. Der Bot antwortet einem noch nicht
  freigeschalteten Chat automatisch mit dessen Chat-ID – so ist die Einrichtung
  ohne technische Kenntnisse möglich.
- **Interaktiver Bot (nur Abfragen):** Freigeschaltete Chats können den Bestand
  abfragen, ohne Änderungen vornehmen zu können:
  `/bestand <Typ> [Größe]` (z.&nbsp;B. „haben wir T-Shirt Größe S" → Anzahl verfügbar
  und an welchen Lagerorten), `/artikel <Nummer>`, `/wer <Nummer>` (wer hat den
  Artikel), `/helfer <Name>` (was hat eine Person gerade), `/suche <Text>`, `/offen`.
  Nur freigeschaltete Chats erhalten Antworten.

## 1.14.0

- **Live-Aktualisierung bei gleichzeitiger Nutzung:** Ändert eine andere Person einen
  Artikel, den man gerade geöffnet hat, erscheint ein kleiner Hinweis („… hat diesen
  Artikel gerade geändert") und die Ansicht aktualisiert sich automatisch. Bearbeitet
  man selbst gerade, wird erst nach dem Speichern/Abbrechen neu geladen, damit keine
  Eingaben verloren gehen. Auch in einer laufenden Inventur werden Fortschritt und
  Fehlliste laufend nachgeladen, sodass mehrere Teilnehmer die Scans der anderen
  in Echtzeit sehen.

## 1.13.0

- **Bestandsübersicht je Lagerort:** Im Standort-Baum (Einstellungen → Stammdaten)
  wird pro Knoten angezeigt, wie viele Artikel enthalten sind (gesamt und direkt) und
  wie viele Unterebenen es gibt – z.&nbsp;B. „wie viele Artikel im Schrank" und „wie
  viele Fächer hat der Schrank".
- **Erinnerung beim Ortswechsel:** Wechselt man in einer laufenden Inventur zum
  nächsten Lagerort (Auswahl oder QR-Scan) und am zuvor bearbeiteten Ort werden noch
  Artikel erwartet, die nicht erfasst wurden, erscheint ein kurzes Pop-up mit genau
  diesen Artikeln.

## 1.12.0

- **Fest verwaltete Standort-Objekte (Lagerort-Baum):** Standorte sind jetzt ein
  richtiger Baum aus verwalteten Objekten – Standort → Etage → Raum → Schrank → Fach.
  Jede Ebene ist ein eigener Datensatz mit stabiler ID; Standorte tragen zusätzlich
  Adresse und Kontaktdaten. Verwaltung im Einstellungen-Bereich „Stammdaten"; beim
  Erfassen/Bearbeiten von Artikeln und in der Inventur wird der Lagerort per Kaskade
  gewählt (neue Ebenen direkt anlegbar). Bestehende Standorte werden als Wurzelknoten
  übernommen; die Unterebenen baut man frisch auf. Der Lagerort-Pfad erscheint in der
  Artikel-Detailseite und im Export.
- **QR-Etiketten pro Standort-Knoten:** Jeder Knoten – bis zum Fach – kann ein eigenes
  QR-Etikett bekommen (stabile ID). In der Inventur lässt sich der Ziel-Standort damit
  einfach abscannen statt auswählen. Druckbar einzeln oder alle Knoten auf einmal.
- **Inventur als eigenständige Vorgänge:** Neuer Bereich „Inventuren". Eine Inventur
  ist ein Objekt mit **Geltungsbereich** – Gesamtinventur, nur bestimmte Lagerorte
  (inkl. Unterebenen) oder nur bestimmte Klassen (z.&nbsp;B. nur Kleidung). Ein
  Startzeitpunkt ist **nicht** zwingend; ein Termin kann geplant, verschoben,
  pausiert, fortgesetzt, abgeschlossen oder abgesagt werden.
- **Scannen & Fehlliste je Inventur:** In einer laufenden Inventur scannt man Standort
  für Standort die vorhandenen Artikel; jeder erfasste Artikel gilt als „gefunden".
  Was im Geltungsbereich nicht erfasst wurde, bleibt als Fehlliste „offen / örtlich
  nicht zugeordnet". Status wie ausgegeben/Reparatur/ausgemustert werden dabei
  ignoriert (je Inventur konfigurierbar) und separat angezeigt. Mehrere Personen
  können gleichzeitig scannen – „viele Hände, schnelles Ende".
- **Eigenes Recht „Inventur" + Teilnehmer je Inventur:** Verantwortliche mit dem neuen
  Recht „Inventuren planen & leiten" (Standard: Admin, Materialverwalter) legen
  Inventuren an und steuern sie. Ein Leiter kann für eine **einzelne** laufende
  Inventur weitere Personen freischalten – die dürfen dann dort mitscannen, auch ohne
  globales Inventur-Recht.
- **Benachrichtigungen:** Laufende, pausierte und geplante Inventuren erscheinen im
  Benachrichtigungszentrum (Glocke) für die zuständigen bzw. beteiligten Personen –
  inkl. Anzahl noch offener Artikel.
- **Bestandsschutz:** Die Umstellung auf den Standort-Baum ist rein additiv – vorhandene
  Artikel und ihre bisherigen Lagerort-Angaben bleiben erhalten und werden weiter
  angezeigt, bis sie (z.&nbsp;B. per Inventur) einem Knoten neu zugeordnet werden.

## 1.11.0

- **Mehrstufiger Standort:** Der Lagerplatz ist jetzt gegliedert in **Standort**
  (oberste Ebene, verwaltete Liste **mit Adresse und Kontaktdaten** – Ansprechpartner,
  Telefon, Fax, E-Mail) plus die frei belegbaren Ebenen **Etage / Raum / Schrank /
  Fach** je Artikel (jede optional; „Etage" kann auch eine Garage sein, „Raum" ein
  Auto). Angezeigt wird der Pfad „Standort › Etage › …" (leere Ebenen werden
  weggelassen) – in der Artikel-Detailseite und im Export.
- **Standorte verwalten:** In den Einstellungen (Stammdaten & Erfassung) lassen sich
  Standorte inkl. Adresse und Kontakt anlegen/bearbeiten.
- **Klarere Begriffe:** Der bisherige „Aktuelle Standort" (wo der Artikel gerade
  ist, z.B. bei wem er ausgegeben ist) heißt jetzt **„Aktuell bei"**, damit er nicht
  mit dem Lager-Standort verwechselt wird.
- **Geführte Zuordnung bestehender Lagerorte:** Nach dem Update wird dem
  Administrator beim nächsten Login eine Zuordnung angezeigt. Für jeden bisherigen
  Lagerort wählt er die passende Ebene (Standort/Etage/Raum/Schrank/Fach) und – bei
  Unterebenen – den zugehörigen Standort (auswählbar oder neu anlegen) samt der
  darüberliegenden Ebenen. Die Artikel werden dabei automatisch umgehängt.

## 1.10.2

- **Aufgeräumte Einstellungen:** Die Einstellungen sind jetzt übersichtlich in
  Kategorien gegliedert (Konten & Rechte / Stammdaten & Erfassung / Daten &
  Protokoll / System) – auf PC/Tablet als Seitenleiste, am Handy als gruppiertes
  Auswahlmenü, statt einer langen Reihe von Reitern.

## 1.10.1

- **Zahlen-Tastatur bei Inventarnummern:** Bei der Eingabe einer Inventarnummer
  erscheint am Handy standardmäßig die Zahlen-Tastatur (Numpad); per Knopf („ABC")
  lässt sich auf die normale Tastatur umstellen (z.B. für den Bindestrich). Gilt in
  Erstinventarisierung, Materialausgabe, Sammelausgabe und Schnell-Inventarisierung.

## 1.10.0

- **Sammelausgabe per Scan:** An eine Person mehrere Artikel auf einmal ausgeben –
  auf der Personen-Ansicht („Details anzeigen" → „Sammelausgabe") und auf der
  Materialausgabe-Seite (erst Empfänger wählen). Artikel nacheinander scannen (oder
  Nummer manuell), dann je Zeile mit grünem Haken oder unten „Alle gesammelt
  bestätigen" ausgeben. Bereits woanders ausgegebene Artikel werden markiert und
  können per „Zurücknehmen & neu" umgebucht werden.
- **Vorläufige Inventarisierung + Genehmigung:** Wird eine unbekannte Nummer
  gescannt (oder ein Artikel ohne Etikett ausgegeben), lässt er sich sofort
  vorläufig anlegen – auch ohne Artikel-Recht. Ein Berechtigter prüft solche Artikel
  später unter „Vorläufige Artikel": genehmigen, Details ändern (Artikel öffnen)
  oder überspringen; einzelne lassen sich einem Nutzer zuweisen. Die Glocke oben
  rechts zeigt offene bzw. zugewiesene vorläufige Artikel an.
- **Ausgabe-Regeln je Status konfigurierbar:** Pro Status einstellbar, ob Artikel
  darin direkt, nur nach Bestätigung oder gar nicht ausgegeben werden dürfen
  („Ausgemustert" bleibt immer gesperrt; erst Status zurücknehmen). Voreinstellung:
  „Verfügbar" direkt, andere nach Bestätigung, „Ausgemustert" gesperrt.

## 1.9.1

- **Terminal-Update vereinfacht:** Die „Update"-Aktion der Linux-Verwaltungs-App
  holt jetzt selbst die neueste Version (git pull) und baut neu – ein Schritt statt
  zweier Befehle. Nach Erstinstallation und nach jedem Terminal-Update wird der
  Update-Dienst („Software-Update per Web") erklärt und – sofern noch nicht aktiv –
  gleich mit eingerichtet (mit Opt-out), damit künftige Updates ohne Terminal per
  Klick in der Weboberfläche laufen.

## 1.9.0

- **Software-Update aus der Weboberfläche:** Neuer Bereich Einstellungen → „Update".
  Die Anwendung prüft eigenständig das GitHub-Repository auf neue stabile Versionen
  (x.y.0-Releases), zeigt die installierte und die neueste Version, listet
  verfügbare Versionen und bietet die Installation per Klick an – der Server holt
  die gewählte Version und baut sich neu auf.
- **Benachrichtigung über die Glocke:** Ist eine neue Version verfügbar, erscheint
  oben rechts an der Glocke ein Hinweis mit direktem Link zum Update-Bereich.
- **Experimentelle Versionen:** Zusätzlich lässt sich der `dev`-Branch
  (Entwicklungsstand, ggf. halbfertig) installieren – mit deutlicher Warnung.
- **Neues Recht „Software-Updates"** (über die Rollen-/Rechte-Matrix vergebbar,
  Administrator hat es automatisch). Das eigentliche Update übernimmt ein optionaler
  Host-Dienst, der einmalig in der Linux-Verwaltungs-App aktiviert wird
  („Software-Update per Web") – der Container selbst erhält bewusst keine Host-Rechte.

## 1.8.0

- **Moderneres, responsives Layout mit Light-/Dark-Mode:** Umschalter oben rechts
  (hell / dunkel / automatisch nach Systemeinstellung), aufgeräumte Kopfzeile mit
  Logo/Organisation, Benachrichtigungs-Glocke (Grundgerüst) und Konto-Menü. Am
  Handy neu eine feste untere Navigationsleiste (Tab-Bar) plus „Mehr"-Menü; auf
  Tablet/PC klassische Navigation.
- **Drill-down aus der Typ-Übersicht:** Klick auf eine Zeile öffnet die (gefilterte)
  Gesamtübersicht aller Artikel dieser Zeile; Klick auf eine Status-Zahl zeigt nur
  die Artikel in diesem Status. Die Gesamtübersicht hat dafür jetzt auch einen
  Modell- und Größen-Filter und übernimmt Filter aus der Adresszeile.
- **Scanner lässt sich am Handy zuverlässig schließen:** Der Scanner ist jetzt eine
  feste Ebene mit immer sichtbarem „Schließen", der Hintergrund scrollt nicht mehr
  weg.

## 1.7.0

- **Artikelbilder verwalten:** Bilder sind anklickbar und öffnen sich groß
  (Lightbox) mit Herunterladen sowie – ab Materialverwalter/Admin – Ersetzen und
  Löschen. Dokumentationsbilder (z.B. Schadens-/Verschmutzungsfotos aus dem
  Statuswechsel „Beschädigt") sind aus Nachweisgründen geschützt und können nur
  angesehen/heruntergeladen werden; sie sind in der Galerie mit „Schaden" markiert.
- **Typ-Übersicht nach Modell + Filter/Sortierung:** Zusätzliche Aufschlüsselung
  nach Modell. Jede aufgeschlüsselte Spalte ist filter- und (per Klick auf die
  Überschrift) auf-/absteigend sortierbar; auch die Status-Spalten und „Gesamt"
  lassen sich sortieren. „Filter/Sortierung zurücksetzen" ergänzt.
- **Export mit mehr Feldern:** CSV enthält jetzt u.a. Modell, Eigenschaften,
  aktuellen Standort, Reparaturgrund, voraussichtliche Rückgabe, Aussonderungsgrund
  und „Angelegt von". Das PDF zeigt zusätzlich Modell, Eigenschaften und aktuellen
  Standort (mit umbrechenden Spalten, damit alles auf A4-Querformat passt).
- **PDF-Export kompakter:** Das Logo steht jetzt neben der Überschrift (statt
  darüber) und spart so vertikalen Platz; die Kopfzeile nennt zusätzlich die Anzahl
  der Artikel. Der Übersichts-Export (CSV/PDF) berücksichtigt weiterhin die aktiven
  Filter – es wird also nur das angezeigte, ggf. gefilterte Inventar exportiert.

## 1.6.3

- **Benutzer = Person (jetzt beidseitig):** Beim Anlegen eines Benutzers wird –
  sofern keine bestehende Person ausgewählt ist – automatisch ein Personen-Datensatz
  aus dem Namen angelegt und verknüpft. Dadurch funktionieren „Meine Artikel" und
  die Empfänger-/Leser-Zuordnung auch für manuell angelegte Konten (vorher blieb das
  ohne manuelle Verknüpfung leer).
- **Bestehende Daten werden angeglichen:** Beim Start ergänzt ein einmaliger
  Abgleich fehlende Verknüpfungen – bestehende Benutzer ohne Person erhalten eine
  Person, bestehende aktive Personen ohne Konto ein (passwortloses) Benutzerkonto.

## 1.6.2

- **Scharfer Scan bei mehreren Kameras (z.B. iPhone):** Der Scanner wählt jetzt
  standardmäßig die normale Hauptkamera (statt Ultraweit/Tele) und bietet ein
  Auswahlmenü, um live zwischen den Kameras zu wechseln; zusätzlich wird eine
  höhere Auflösung angefragt, damit auch kleine QR-Codes aus fokussierbarem
  Abstand scharf werden.

## 1.6.1

- **Kamera-Start behoben:** Der Scanner startet wieder – der Fehler
  „'cameraIdOrConfig' object should have exactly 1 key … found 5 keys" ist behoben.
  Die höhere Auflösung und der Autofokus werden jetzt korrekt als
  `videoConstraints` übergeben (Fokus als optionale Vorgabe, um Startfehler auf
  Geräten ohne Unterstützung zu vermeiden).
- **Strichcodes funktionieren jetzt wirklich:** Code 128 / Code 39 werden als
  Vektor ins Etikett-PDF gezeichnet und in der Vorschau als SVG angezeigt – der
  Server erzeugte zuvor immer nur QR-Codes, weil dem schlanken Container der
  Raster-Renderer fehlte.
- **Reine Leser sehen nur „Meine Artikel":** Für Nutzer mit reiner Leserolle sind
  die Gesamt-Übersichten (Übersicht, Typ-Übersicht, Offene Ausgaben) ausgeblendet;
  die Startseite führt sie direkt zu ihren eigenen Materialien.

## 1.6.0

- **Fehlerbehebung Stammdaten:** Gelöschte Beispiel-Stammdaten (Abteilungen,
  Typen, Beispiel-Status) werden nicht mehr bei jedem Neustart neu angelegt – sie
  werden nur noch bei der Erstinstallation erzeugt. Eingebaute Status bleiben
  weiterhin immer vorhanden.
- **Lagerorte/Abteilungen löschbar:** Sind sie noch mit Artikeln/Personen
  verknüpft, meldet die Anwendung dies mit Anzahl und bietet ein Löschen mit
  automatischem Entfernen der Verknüpfungen an.
- **Empfänger-Suche in „Offene Ausgaben":** Suche findet jetzt auch den Namen der
  verknüpften Person (Vor-/Nachname), nicht nur den Freitext-Empfänger.
- **Logo auf PDF-Export:** Das hinterlegte Logo und der Organisationsname
  erscheinen im Kopf der Inventarlisten-PDF.
- **Scanner verbessert:** Höhere Auflösung und kontinuierlicher Autofokus für ein
  schärferes Bild; sofern das Gerät es unterstützt, lässt sich die Taschenlampe
  ein-/ausschalten.
- **Benutzer löschen/zusammenführen:** Benutzerkonten sind endgültig löschbar
  (mit Fehlermeldung, wenn noch Material ausgegeben ist) und lassen sich direkt in
  den Einstellungen zusammenführen.
- **Selbstregistrierung:** Nach dem Anlegen wird man direkt angemeldet – die
  Registrierung funktioniert damit vollständig eigenständig, ohne den automatisch
  vergebenen Benutzernamen kennen zu müssen.
- **Server-Steuerung per Web:** Über die Rechte-Matrix vergebbares Recht „Server
  herunterfahren / neu starten" mit eigener Seite. Das eigentliche Ausschalten
  übernimmt ein optionaler, in der Linux-Verwaltungs-App einrichtbarer
  Systemdienst (der Container selbst erhält bewusst keine Host-Rechte).
- **Zugangsblatt drucken:** Druckbares A4-/A5-Blatt mit Serveradresse (HTTP und
  HTTPS) als QR-Code zum Einscannen mit dem Handy.
- **Stabileres Nachladen:** Nach einem Update/Abmelden wird kein veralteter Stand
  mehr ausgeliefert (index.html ohne Cache, überarbeiteter Service-Worker); ein
  Fehlerbildschirm mit „Neu laden" ersetzt den bisherigen schwarzen Bildschirm.
  Rollen/Rechte werden beim Start frisch geladen (neu vergebene Admin-Rechte
  greifen sofort).

## 1.5.0

- **Etikett-Code konfigurierbar:** Das Format des maschinenlesbaren Codes der
  Inventarnummer (QR-Code, Strichcode Code 128 oder Code 39) ist in den
  Einstellungen wählbar; ein Beispielbild wird direkt daneben angezeigt.
- **Etikett-Inhalt konfigurierbar:** Frei einstellbar, welche Felder auf das
  Etikett gedruckt werden (u.a. jetzt auch das Modell) und wie viele Zeichen je
  Feld maximal (Standard Modell 10). Diese Begrenzung gilt nur für den Aufdruck –
  im Artikel selbst bleibt der volle Wert erhalten.
- **Neuer Artikel – zwei Schaltflächen:** „Anlegen und weiter" (direkt den
  nächsten Artikel erfassen, gemeinsame Angaben bleiben erhalten) und „Anlegen und
  anschauen" (wie bisher zur Detailseite).
- **Status „Beschädigt":** Beim Setzen ist eine Beschreibung (Freitext) Pflicht;
  optional kann ein Bild (Schadensbild) angehängt werden. Ob ein Status eine
  Pflicht-Beschreibung und/oder einen Bild-Anhang verlangt, ist je Status einstellbar.
- **Reparatur mit Reparaturort:** Beim Wechsel auf „In Reparatur" wird zusätzlich
  erfasst, wohin der Artikel gegeben wird; dieser Ort wird als aktueller
  Standort/Lagerort vermerkt.
- **Rollen-Hilfe:** In den Einstellungen erklärt ein „?" hinter jeder Rolle deren
  Bedeutung und aktuelle Rechte.
- **Rolle „Nur lesend" auf eigene Ausgaben beschränkt:** Konten mit der Rolle
  „lesend" sehen nur die an sie selbst ausgegebenen Materialien.
- **Zusammenführen inkl. Benutzerkonten:** Beim Zusammenführen zweier Personen
  werden auch deren Benutzerkonten vereint (Zugangsdaten/Rollen übernommen,
  Duplikate deaktiviert).
- **Selbstregistrierung mit Namensabgleich:** Bei exakter Übereinstimmung von Vor-
  und Nachname verbindet sich die Registrierung mit einem bereits (z.B. bei einer
  Ausgabe) angelegten, passwortlosen Konto – so sind frühere Ausgaben sofort
  sichtbar. Die bei der Registrierung eingegebene PIN/das Passwort wird dabei auf
  dieses Konto übernommen, sodass die Anmeldung damit möglich ist. In den
  Einstellungen abschaltbar.
- **Benutzername ändern:** Benutzernamen lassen sich nachträglich ändern; dabei
  wird auf bereits vergebene Namen hingewiesen.
- **Import & reiner Datenexport in den Einstellungen:** Der Import-Assistent ist
  nun über die Einstellungen erreichbar; dort steht auch der reine Datenexport der
  Inventarliste (CSV/PDF) zur Verfügung.

## 1.4.0

- **Komplett-Backup (alles):** Der Administrator kann in den Einstellungen ein
  vollständiges Backup aller Daten – Artikel, Personen/Benutzer, Einstellungen,
  Organisationsname, Logo, Status, Verlauf und Bilder – als eine ZIP-Datei
  herunterladen (zusätzlich zum reinen Inventar-Export als CSV/PDF).
- **Wiederherstellung:** Ein solches Komplett-Backup kann sowohl in der
  Weboberfläche (Einstellungen → Datensicherung) als auch in der Verwaltungs-App
  eingespielt werden – bei der Erstinstallation und jederzeit dazwischen. Jede
  Wiederherstellung ist durch zwei „Bist du sicher?"-Abfragen abgesichert und
  ersetzt alle vorhandenen Daten; die Anwendung startet anschließend automatisch
  neu, damit die wiederhergestellte Datenbank sauber geladen wird.
- **Listen alphabetisch sortierbar:** Auch die Ansicht „Offene Ausgaben" lässt
  sich per Klick auf jede Spaltenüberschrift auf- und absteigend sortieren
  (natürliche Sortierung, z. B. bei Inventarnummern).

## 1.3.0

- **Konfigurierbare Rollen-Rechte** (Einstellungen → „Rollen & Rechte"): Der
  Administrator legt je Rolle die erlaubten Aktionen fest. Neudefinition der
  Standardrollen: Materialverwalter darf Artikel anlegen/bearbeiten/aussondern
  sowie aus- und zurückgeben; Helfer und „Nur lesend" sind lesend.
- **Aussondern mit Pflicht-Grund:** Beim Status „ausgemustert" muss ein Grund
  (Freitext) angegeben werden; er wird gespeichert und in der Detailansicht gezeigt.
- **Person = Benutzer:** Beim Anlegen einer Person (auch bei der Ausgabe) wird
  automatisch ein Benutzerkonto mit Standardrolle (lesend) und automatisch
  erzeugtem Benutzernamen angelegt. Selbstregistrierung fragt Vor-/Nachname ab,
  der Benutzername wird automatisch vergeben.
- **Personen/Benutzer zusammenführen:** Administratoren können doppelt angelegte
  Personen zusammenführen (Ausgaben/Verlauf umhängen, Quelle deaktivieren).
- **Schnelle Materialausgabe:** Empfänger per Autocomplete (Vor- oder Nachname)
  mit Rückfrage bei Neuanlage; die Ausgabe wird direkt fortgeführt.
- **Übersicht nach Artikeltyp:** Mengen je Typ, wahlweise zusätzlich nach Größe/
  Abteilung/Lagerort, aufsummiert je Status.
- **Listen sortierbar** (Klick auf Spaltenüberschrift); in der Personen-Ansicht
  wird zusätzlich die Artikelgruppe (Typ) angezeigt.
- **Protokoll (Audit-Log)** zeigt lesbare Objekte (Inventarnummer/Benutzername/
  Name); Artikel sind zur Detailansicht verlinkt.
- **Fehlerbehebungen:** Der Neuanlage-Dialog (Typ/Abteilung/Lagerort) beendet das
  Artikelformular nicht mehr vorzeitig – neu angelegte Einträge werden korrekt
  übernommen, keine Doppelabfrage mehr; der Etikett-PDF-Button funktioniert wieder.
- Projekt unter **AGPL-3.0-or-later** lizenziert (LICENSE, THIRD-PARTY-LICENSES.md).

## 1.2.0

- **Neue Artikelfelder Modell und Eigenschaften** (Erst- und Mengenerfassung,
  Artikel-Detailseite).
- **Automatischer Standort bei Ausgabe:** Wird ein Artikel ausgegeben, ist sein
  aktueller Standort automatisch der Name der Empfänger-Person; der
  Stammdaten-Lagerort bleibt als Rückgabeort erhalten.
- **Bearbeiten mit Speichern-Button:** Änderungen an Artikeldetails werden erst
  nach Klick auf „Speichern" übernommen; „Ersteintrag" und „Angelegt von" sind
  nicht mehr nachträglich änderbar.
- **Konfigurierbare Status:** Neue Status (z.B. „Zu waschen", „Beschädigt",
  „Infektiös") lassen sich in den Einstellungen anlegen, je Artikelklasse
  zuordnen und wieder entfernen; eingebaute Status sind geschützt.
- **Schnelle Materialausgabe (Scannen):** Artikel scannen oder Inventarnummer
  eingeben, alle Infos anzeigen und direkt ausgeben, zurücknehmen oder einen
  Status setzen; für Helfer auch „An mich" ausgeben.
- **Übersicht/Dashboard:** Mengen je Status (nach Klasse filterbar) sowie Anzeige
  der aktuell angemeldeten Nutzer (für Administratoren mit Namen; die
  Verwaltungs-Apps können die reine Anzahl anzeigen).
- **Selbstregistrierung:** Neue Helfer können sich auf der Anmeldemaske selbst
  anlegen (geringste Rechte: nur eigene Artikel). Pflichtangaben legt der
  Administrator fest; Standard: Nutzername + 8-stellige PIN, Passwort optional.
- **Direktdruck-Wahl:** Etiketten-Direktdruck wahlweise an den hinterlegten
  Netzwerkdrucker oder an eine mitgegebene (mobil erreichbare) Drucker-IP.
- **Autostart (macOS/Linux):** Bei der Erstinstallation abfragbar und jederzeit
  im Menü ein-/ausschaltbar (macOS via LaunchAgent, Linux via systemd-User-Service).

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
