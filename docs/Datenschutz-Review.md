# Datenschutz-Review – Inventarprogramm (DRK/JRK-Materialverwaltung)

*Erstellt aus Sicht eines Datenschutzbeauftragten. Bewertungsmaßstab: DSGVO / BDSG.
Bezieht sich auf den Quellstand des Projekts (Backend FastAPI/SQLite, Frontend React,
Betrieb als Docker-Container im lokalen Netz, optionale Telegram-Anbindung).*

## 1. Gesamteinschätzung

Die Anwendung ist von der Grundarchitektur her **datenschutzfreundlich**: Sie läuft
lokal (kein zentraler Cloud-Dienst), Passwörter und PINs werden mit bcrypt gehasht,
der Zugriff ist rollen- und rechtebasiert, es gibt ein Prüfprotokoll (Audit-Log),
automatischen Logout und – seit dem letzten Review – Brute-Force-Schutz. Die
Datenübertragung im Netz erfolgt über HTTPS.

Der **größte offene Punkt** ist die **Telegram-Anbindung**: Dabei verlassen
personenbezogene Daten (Klarnamen, Zuordnung „wer hat welches Material") das lokale
System und werden an einen Dienst außerhalb der EU übertragen. Daneben fehlen ein
formales **Löschkonzept mit Aufbewahrungsfristen** und Funktionen für die
**Betroffenenrechte** (Auskunft/Löschung/Berichtigung). Diese Punkte sind vor einem
produktiven Einsatz mit echten Mitgliederdaten zu adressieren.

## 2. Verarbeitete personenbezogene Daten

| Datenart | Beispiele | Zweck | Speicherort |
|---|---|---|---|
| Benutzerkonten | Benutzername, Name, Rolle, Passwort-/PIN-Hash | Anmeldung, Berechtigung | DB (`users`) |
| Personen/Empfänger | Vor-/Nachname, Abteilung, Notizen | Materialausgabe an Mitglieder | DB (`persons`) |
| Ausgabe-/Rücknahme-Verlauf | wer hat welchen Artikel wann, Zustand, Bemerkungen | Nachverfolgung des Materials | DB (`issue_records`) |
| Prüfprotokoll (Audit) | Benutzer, Aktion, Objekt, Zeitstempel | Nachvollziehbarkeit/Sicherheit | DB (`audit_log`) |
| Gruppen/Funktionsrollen | Zuordnung Nutzer↔Gruppe | Aufgaben-/Benachrichtigungssteuerung | DB (`user_groups`) |
| Telegram-Verknüpfung | Chat-ID, Telegram-Name/@Username | Benachrichtigung/Abfrage per Bot | DB (Settings), Telegram |
| Bilder | Artikel-/Schadensfotos | Dokumentation | Dateisystem (`images`) |

Besonders sensibel ist die **Verknüpfung Person ↔ Material ↔ Zeit** im Ausgabe-Verlauf
sowie das **Audit-Log** (Verhaltensdaten der Benutzer). Beide sind keine besonderen
Kategorien nach Art. 9, aber schutzbedürftig.

## 3. Rechtsgrundlagen und Zweckbindung

Die Verarbeitung dient der Vereins-internen Materialverwaltung und lässt sich
regelmäßig auf **Art. 6 Abs. 1 lit. b/f DSGVO** (Mitgliedschaftsverhältnis bzw.
berechtigtes Interesse an ordnungsgemäßer Materialverwaltung) stützen. Für die
**Telegram-Nutzung** ist eine gesonderte Grundlage nötig – praktisch am ehesten die
**Einwilligung** der betroffenen Nutzer (Art. 6 Abs. 1 lit. a), da hier Daten an einen
Drittanbieter fließen. Die Selbstregistrierung sollte mit einer Information zur
Datenverarbeitung verbunden sein. Ein **Verzeichnis von Verarbeitungstätigkeiten (VVT,
Art. 30)** ist zu führen; eine Schwellwertanalyse/DSFA ist wegen des überschaubaren
Umfangs vermutlich nicht zwingend, aber zu dokumentieren.

## 4. Architektur und Datenflüsse

Die Anwendung läuft als Docker-Container (Backend + Frontend) typischerweise auf einem
Raspberry Pi im lokalen Vereinsnetz. Die Daten liegen in einer SQLite-Datenbank in
einem Docker-Volume; Bilder und Backups liegen im Dateisystem. Der Zugriff erfolgt per
Browser über HTTPS (selbstsigniertes Zertifikat). Es bestehen drei Außenschnittstellen:

**Telegram (optional):** Der Server kommuniziert mit der Telegram-Bot-API. Dabei werden
Benachrichtigungen und Bot-Antworten versendet, die **Klarnamen** und die Zuordnung
„wer hat welches Material" enthalten können, sowie auf Anforderung die **komplette
Inventarliste als PDF**. Telegram ist ein Anbieter außerhalb der EU → **Drittlandtransfer**.

**GitHub (Updates):** Für die Update-Funktion ruft der Server öffentlich die
GitHub-API/Releases ab. Dabei werden **keine** personenbezogenen Daten übertragen (nur
Versionsabfrage/Code-Download).

**Lokales Netz:** Etiketten-, QR- und Bild-Endpunkte sind bewusst ohne Anmeldung
abrufbar (technisch nötig für Druck/Bildanzeige). Im LAN vertretbar, aber es bedeutet,
dass wer im Netz ist, Etiketten/Bilder abrufen kann.

## 5. Technische und organisatorische Maßnahmen (Art. 32)

Vorhanden und positiv zu bewerten: **Transportverschlüsselung** (HTTPS),
**Passwort-/PIN-Hashing** (bcrypt), **rollen-/rechtebasierte Zugriffskontrolle**,
**Prüfprotokoll**, **automatischer Logout** nach Inaktivität, **Brute-Force-Schutz**
beim Login, Absicherung des Bots (nur freigeschaltete Chats, Blacklist, Kopplung an das
Benutzerkonto, rein lesende Abfragen), sowie ein bewusst rechtefreier Container, der
privilegierte Host-Aktionen nur über kontrollierte Signaldateien anstößt.

Verbesserungswürdig: Die **Datenbank liegt unverschlüsselt** auf dem Datenträger (bei
Diebstahl des Geräts/der SD-Karte sind alle Daten lesbar). Das **Zertifikat ist
selbstsigniert** (keine echte Vertrauenskette, Browser-Warnung). Der **`SECRET_KEY`**
sollte fest in der `.env` gesetzt sein. **Backups** enthalten alle personenbezogenen
Daten und müssen zugriffsgeschützt und möglichst verschlüsselt aufbewahrt werden.

## 6. Zentrale Risiken und Handlungsbedarf

**6.1 Telegram – Drittlandtransfer und Auftragsverarbeitung.** Mit dem Bot verlassen
Klarnamen und Nutzungsdaten das lokale System. Es besteht kein belastbarer
AV-Vertrag/Angemessenheitsbeschluss mit Telegram. Empfehlung, in dieser Reihenfolge:
(a) **Datenminimierung** – standardmäßig keine Klarnamen an Telegram senden, sondern
nur Artikelnummern/IDs bzw. abstrahierte Meldungen; personenbezogene Auskünfte per Bot
nur an eng begrenzte, berechtigte Empfänger. (b) **Einwilligung** der Nutzer einholen,
deren Daten über Telegram verarbeitet werden, samt Information über den Drittlandbezug.
(c) Telegram als **optionales Feature** klar kennzeichnen und ohne es voll nutzbar
halten (ist der Fall). (d) Prüfen, ob eine interne Alternative (nur In-App-Glocke,
E-Mail über eigenen Server) den Zweck ebenso erfüllt.

**6.2 Fehlendes Löschkonzept / Aufbewahrungsfristen.** Audit-Log und Ausgabe-Verlauf
wachsen unbegrenzt; Personen werden nur **deaktiviert**, nicht gelöscht. Es sind
**Aufbewahrungsfristen** zu definieren (z. B. Audit-Log rollierend nach X Monaten,
Ausgabe-Historie nach Vereinsbedarf) und eine **Anonymisierung/Löschung** ausgeschiedener
Mitglieder vorzusehen.

**6.3 Betroffenenrechte (Art. 15–18).** Es fehlen Funktionen für **Auskunft** (Export
aller Daten zu einer Person), **Berichtigung** (teils vorhanden über Bearbeiten) und
**Löschung/Einschränkung**. Für die Praxis sollte es einen Weg geben, zu einer Person
alle gespeicherten Daten auszugeben und sie auf Wunsch zu löschen/anonymisieren.

**6.4 Identitätsabgleich bei Selbstregistrierung.** Die automatische Kontoübernahme bei
exakter Vor-/Nachname-Übereinstimmung kann dazu führen, dass sich jemand mit einem
fremden, gleichnamigen Konto verbindet. Das ist abschaltbar; für sensible Umgebungen
sollte die Bestätigung durch einen Verantwortlichen erwogen werden.

**6.5 Nicht löschbare Dokumentationsbilder.** Schadensfotos sind aus Nachweisgründen
nicht löschbar. Sofern darauf Personen erkennbar sein können, kollidiert das mit dem
Löschanspruch – hier ist eine Abwägung/Regelung nötig (möglichst keine Personen auf
Doku-Fotos).

## 7. Empfehlungen (priorisiert)

Kurzfristig und organisatorisch: **Verzeichnis von Verarbeitungstätigkeiten** anlegen;
**Datenschutzinformation** für Nutzer (spätestens bei Registrierung) bereitstellen;
**Aufbewahrungs-/Löschfristen** festlegen; **Backups** verschlüsselt und zugriffsbeschränkt
lagern; **`SECRET_KEY`** setzen; Telegram nur mit **Einwilligung** und **ohne Klarnamen**
betreiben.

Mittelfristig und technisch (kann ich auf Wunsch umsetzen): **Audit-Log-Rotation**
(automatisches Löschen alter Einträge nach konfigurierbarer Frist); **Personen-Datenexport
und -Anonymisierung** als DSGVO-Funktion; **Telegram-Datenminimierung** (Option, in
Meldungen keine Klarnamen zu verwenden); **Datenträgerverschlüsselung** des Pi (LUKS,
außerhalb der Anwendung einzurichten).

## 8. Fazit

Für den internen Vereinsbetrieb im lokalen Netz ist der Datenschutz-Grundstock solide.
Vor einem breiteren produktiven Einsatz mit echten Mitgliederdaten sind vor allem die
**Telegram-Datenflüsse** (Drittland, Klarnamen), ein **Löschkonzept** und die
**Betroffenenrechte** zu klären bzw. umzusetzen. Die genannten technischen Punkte lassen
sich innerhalb der bestehenden Architektur ergänzen.

---

## Nachtrag 12.09.2026 - geschlossene Zugriffsluecken (Version 1.99.0)

Eine Durchsicht aller 341 Schnittstellen hat vier Stellen gefunden, an denen die Oberflaeche etwas
verbarg, das die Schnittstelle jedem offen liess. Alle vier sind behoben:

1. Personenliste, einzelne Personen und deren Ausgabehistorie waren fuer jedes angemeldete Konto
   abrufbar. Jetzt nur mit dem Recht "Personen verwalten" oder "Ausgeben / Zurücknehmen".
2. Schaden-/Verlustmeldungen (PDF, Foto, Meldungen je Artikel) waren fuer jedes angemeldete Konto
   einsehbar - einschliesslich Hergang, Ort, Zeugen, Aktenzeichen und Schaetzwert. Jetzt nur fuer
   den Melder, Administratoren und die fuer die Materialklasse Zustaendigen.
3. Die QR-Etiketten aller Lagerorte und die Artikel-Etiketten waren ohne jede Anmeldung abrufbar und
   gaben damit die komplette Standortstruktur preis. Jetzt nur angemeldet.
4. Die detaillierte Systemdiagnose war ohne Anmeldung abrufbar. Jetzt nur fuer Administratoren.

Offen und bewusst so belassen: Artikelbilder sind weiterhin ohne Anmeldung abrufbar, weil sie in
vielen `<img>`-Elementen stecken. Die Dateinamen enthalten eine Zufallskennung und sind nicht
erratbar; wer im selben Netz keinen Zugriff haben soll, braucht hier dennoch eine Loesung mit
kurzlebigen signierten Verweisen. Die uebrigen Punkte dieses Reviews - Telegram-Uebertragung,
Loeschkonzept mit Aufbewahrungsfristen und Betroffenenrechte - sind unveraendert offen.

---

## Nachtrag 12.09.2026 (2) - Loeschkonzept, Einwilligung, Betroffenenrechte (Version 1.101.0)

Die drei im Review als offen benannten Punkte sind jetzt umgesetzt.

### Loeschkonzept mit Aufbewahrungsfristen (Art. 5 Abs. 1 lit. e)

Neu in `backend/app/datenschutz.py`, einstellbar unter Einstellungen -> Sicherheit,
angewendet alle sechs Stunden durch den Zeitplan:

| Einstellung | Wirkung | Erhalten bleibt |
|---|---|---|
| `issue_retention_days` | Zurueckgegebene Ausgaben verlieren den Personenbezug (Person, Freitext-Empfaenger, Notizen, ausgebender/annehmender Benutzer) | Artikel, Zeitraum, Zustand |
| `receipt_retention_days` | Quittungen werden samt Datei geloescht | nichts |
| `report_retention_days` | Abgeschlossene Schadens-/Verlustmeldungen verlieren Melder, Zeugen und Rueckfrage-Kontakt | Hergang, Ort, Schadenshoehe |
| `audit_retention_days` | Pruefprotokoll wird geloescht (bestand bereits) | nichts |

Alle Fristen stehen im Auslieferungszustand auf 0 (unbegrenzt), damit sich bei einem
Update an bestehenden Installationen nichts von selbst aendert - die Entscheidung
trifft die verantwortliche Stelle. Laufende Ausgaben und offene Meldungen werden nie
angefasst. Eine Vorschau (`GET /api/v1/settings/aufbewahrung/vorschau`) zeigt vor dem
Speichern, wie viele Datensaetze eine Frist betreffen wuerde.

Grundsatz: anonymisieren statt loeschen, wo der Vorgang fuer die Materialverwaltung
weiter gebraucht wird. Bei Quittungen nicht - sie enthalten Unterschriften und werden
tatsaechlich geloescht.

### Telegram: Einwilligung (Art. 6 Abs. 1 lit. a, Art. 44 ff.)

Die Verknuepfung eines Telegram-Kontos setzt jetzt eine ausdrueckliche Einwilligung
voraus. Der Einwilligungstext steht im Programm (`EINWILLIGUNGSTEXT` in
`telegram_router.py`) und wird in der Oberflaeche genau so angezeigt; der Zeitpunkt
wird am Konto festgehalten (`users.telegram_consent_at`) und ist damit nachweisbar
(Art. 7 Abs. 1). Das Erteilen und der Widerruf stehen im Pruefprotokoll.

Der Widerruf wirkt sofort und an einer Stelle: `telegram.is_allowed()` liefert fuer
einen Chat, der zu einem Benutzerkonto gehoert, ohne Einwilligung False - auch dann,
wenn der Chat zusaetzlich vom Administrator freigeschaltet ist. Damit greift der
Widerruf ueber alle Versandwege (Benachrichtigungen, Bot-Antworten, Erinnerungen),
ohne dass jemand die Chat-Kennung von Hand entfernen muss.

Bestehende Verknuepfungen gelten als "noch nicht eingewilligt" und erhalten bis zur
Bestaetigung keine Nachrichten mehr. Das ist bewusst so: eine Einwilligung, die nie
eingeholt wurde, kann nicht unterstellt werden. Wer die Pruefung fuer den Uebergang
aussetzen will, setzt `telegram_consent_required` auf false - das sollte die Ausnahme
und dokumentiert sein.

### Betroffenenrechte (Art. 15, Art. 17)

Die Auskunft nach Art. 15 war bisher nur ueber ein Administratorkonto erreichbar. Das
Recht steht aber der betroffenen Person selbst zu: unter "Mein Konto" -> "Meine Daten"
sieht jeder Angemeldete Konto, Stammdaten und eigene Ausgabehistorie und kann sie als
Datei mitnehmen (`GET /api/v1/auth/meine-daten`). Fremde Daten sind nicht enthalten,
Passwort- und PIN-Hashes ebenfalls nicht. Der Abruf wird protokolliert.

Die Anonymisierung nach Art. 17 bestand bereits und wurde um die Telegram-Einwilligung
ergaenzt.

### Echtzeitverbindung

Neu hinzugekommen ist eine dauerhafte Verbindung zwischen Browser und Server, die das
bisherige Nachfragen im Sekundentakt abloest. Datenschutzseitig ist sie bewusst
minimal gehalten: uebertragen wird nur der Bereich einer Aenderung (z.B. "artikel"),
nie Namen, Inhalte oder wer etwas getan hat (siehe `models.ChangeEvent` - die Tabelle
hat gar keine Spalte fuer einen Benutzer). Die Oberflaeche laedt anschliessend
regulaer nach, wobei die Rechte des Angemeldeten greifen. Der Sitzungsschluessel
wandert nicht mehr in die Adresszeile - dort stand er zuvor als Abfrageparameter und
waere in Server-Protokollen und im Browserverlauf gelandet -, sondern geht als erste
Nachricht ueber die bereits stehende Verbindung. Die Vermerke werden nach einer Stunde
automatisch geloescht.

### Weiterhin offen

Artikelbilder sind unveraendert ohne Anmeldung abrufbar (Dateinamen mit Zufallskennung,
nicht erratbar). Fuer eine saubere Loesung braeuchte es kurzlebige signierte Verweise
in allen Bild-Elementen. Ebenfalls offen bleiben die organisatorischen Punkte, die
Software nicht leisten kann: Verzeichnis von Verarbeitungstaetigkeiten (Art. 30),
Auftragsverarbeitung/Drittlandbewertung fuer Telegram und die Information der
Betroffenen bei der Aufnahme (Art. 13).
