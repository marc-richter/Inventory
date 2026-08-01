# IT-Grundschutz-Bewertung (BSI) – Inventarprogramm

*Bewertung an den relevanten Bausteinen des BSI IT-Grundschutz-Kompendiums, mit
Status (erfüllt / teilweise / offen) und konkreten Verbesserungen. Bezug: Betrieb als
zwei Docker-Container (nginx-Frontend, FastAPI-Backend, SQLite) auf einem Raspberry Pi
im lokalen Vereinsnetz.*

## Gesamtbild

Für ein selbstgehostetes System im geschlossenen Netz ist das Schutzniveau **solide bis
gut**. Anwendungssicherheit (Auth, Rechte, Eingabevalidierung, Rate-Limit, Security-Header)
und Betrieb (unprivilegierter Anwendungscode, kontrollierte Host-Aktionen, Updates) sind
grundschutzkonform angelegt. Die wesentlichen Lücken liegen bei **Kryptokonzept**
(Datenverschlüsselung im Ruhezustand, echte Zertifikate), **Datensicherung** (Verschlüsselung/
Auslagerung), **Container-Härtung** (root im Backend-Container) und beim organisatorischen
**Sicherheitsmanagement/Dokumentation**.

## Bewertung nach Bausteinen

**APP.3.1 Webanwendung – teilweise.** Positiv: rollen-/rechtebasierte Autorisierung auf
allen Verwaltungs-Endpunkten, serverseitige Eingabevalidierung (Pydantic), ausschließlich
ORM (kein SQL-Injection-Vektor), Ausgabe im UI durch React auto-escaped (kein XSS),
Login-Rate-Limit, Pfad-Traversal-Schutz, Upload-Prüfung. Neu ergänzt: **Security-Header**
(X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, moderate
Content-Security-Policy). Offen/verbesserbar: Das Zugriffs-Token liegt im `localStorage`
(theoretischer XSS-Abgriff); die CSP nutzt noch `'unsafe-inline'` (Nonce-basierte CSP wäre
strenger); die Etiketten-/Bild-Endpunkte sind bewusst ohne Auth (LAN-Kompromiss).

**ORP.4 Identitäts- und Berechtigungsmanagement – teilweise.** Positiv: klare
Rollen/Rechte (least privilege konfigurierbar), Konten deaktivierbar, Passwort-/PIN-Hashing
(bcrypt), Selbstregistrierung mit geringsten Rechten. Verbesserbar: **PIN-Richtlinie**
(4-stellige PINs sind schwach – Mindestlänge anheben bzw. Passwortpflicht für privilegierte
Rollen), regelmäßige **Rezertifizierung** der Admin-Konten, Vier-Augen-Prinzip bei der
automatischen Kontoübernahme (Namensabgleich).

**CON.1 Kryptokonzept – teilweise.** Positiv: TLS 1.2/1.3, bcrypt-Hashes. Verbesserbar:
Das TLS-Zertifikat ist **selbstsigniert** (keine Vertrauenskette; besser eine interne
Vereins-CA oder dokumentierter Fingerprint-Abgleich). Die **Datenbank liegt unverschlüsselt**
auf dem Datenträger → **Datenträgerverschlüsselung (LUKS)** des Pi einrichten. Der
`SECRET_KEY` (JWT-Signatur) sollte **fest** in der `.env` gesetzt sein statt beim Neustart
zufällig.

**CON.3 Datensicherungskonzept – teilweise.** Positiv: automatische Backups mit
Aufbewahrung, manuelle Backups. Verbesserbar: **verschlüsselte** Backups, **Auslagerung**
an einen zweiten Ort (3-2-1-Regel), regelmäßiger **Restore-Test**, Zugriffsschutz auf das
Backup-Verzeichnis.

**OPS.1.1.3 Patch- und Änderungsmanagement – teilweise.** Positiv: Update-Funktion mit
gegen bekannte Tags validierter Zielversion, Update-Protokoll, versioniertes Änderungsprotokoll
(Changelog). Verbesserbar: geplante **Basis-Image-/Abhängigkeits-Updates** (Python-/npm-/
nginx-Images regelmäßig neu bauen), automatisierte Prüfung auf verwundbare Abhängigkeiten.

**SYS.1.6 Containerisierung – teilweise.** Positiv: Der Anwendungscontainer erhält bewusst
**keine Host-Rechte**; privilegierte Aktionen (Herunterfahren/Update) laufen über
kontrollierte Signaldateien und dedizierte Host-Dienste. Verbesserbar: Der **Backend-Container
läuft als `root`** (kein `USER` im Dockerfile) – auf einen unprivilegierten Benutzer umstellen;
zusätzlich `read_only`-Rootfs, `cap_drop`, `no-new-privileges` in der Compose-Datei.

**DER.1 Detektion / Protokollierung – teilweise.** Positiv: **Audit-Log** (wer/was/wann),
einsehbar. Verbesserbar: **Aufbewahrungs-/Rotationskonzept** für Protokolle, gesicherte
**Zeitsynchronisation (NTP)** auf dem Pi, ggf. Schutz der Logs vor Manipulation.

**NET / Netzsicherheit – organisatorisch.** Der Betrieb im lokalen Netz reduziert die
Angriffsfläche. Empfohlen: eigenes **VLAN/Segment** für das Gerät, Host-**Firewall**
(nur benötigte Ports 80/443), kein Zugriff aus unsicheren Netzen/Internet ohne VPN.

**ISMS.1 / ORP.1 Organisation – offen.** Es fehlen die begleitenden Dokumente:
**Sicherheitsleitlinie**, Zuständigkeiten, **Notfall-/Wiederanlaufplan** (Backup-Restore),
Nutzer-Sensibilisierung. Für den Vereinskontext genügt eine schlanke, dokumentierte Fassung.

## Konkrete Verbesserungen – priorisiert

Sofort und mit geringem Aufwand: **`SECRET_KEY` fest setzen**; **Datenträgerverschlüsselung
(LUKS)** des Pi aktivieren; **Backups verschlüsseln** und an einen zweiten Ort kopieren;
**Host-Firewall** auf die Ports 80/443 begrenzen; **NTP** sicherstellen.

Mittelfristig und technisch (kann ich umsetzen): **Backend-Container als nicht-root**
betreiben (Dockerfile + Volume-Rechte, mit Test); **Compose-Härtung** (`no-new-privileges`,
`cap_drop: [ALL]`, ggf. `read_only`); **Audit-Log-Rotation** (automatisches Löschen nach
konfigurierbarer Frist); **PIN-/Passwort-Richtlinie** verschärfen; strengere **CSP**
(Nonce statt `'unsafe-inline'`). Bereits umgesetzt: Security-Header, Login-Rate-Limit,
Pfad-Traversal-Schutz, Upload-Prüfung, Token-Maskierung.

Organisatorisch: schlanke **Sicherheitsleitlinie**, **Wiederanlaufplan** (dokumentierter
Restore-Ablauf inkl. Test), **Rezertifizierung** der Admin-Konten, **Nutzer-Information**.
