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
