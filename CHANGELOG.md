# Änderungsprotokoll (Changelog)

Ab Version 1.0.0 wird für jede inhaltliche Änderung am Programm eine neue
Versionsnummer vergeben (Format: MAJOR.MINOR.PATCH). Die aktuelle Version steht
in der Datei `VERSION` im Projektordner. Die Verwaltungs-Apps (siehe
`installer/`) vergleichen diese Versionsnummer beim Erstinstallation/Update-Dialog
mit der Version, die zuletzt tatsächlich installiert/gestartet wurde, und zeigen
an, ob ein Update verfügbar ist.

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
