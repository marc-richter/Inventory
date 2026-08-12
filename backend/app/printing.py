"""
Direktdruck-Unterstuetzung fuer Brother P-touch Etikettendrucker.

Wichtiger Hinweis zur Ehrlichkeit der Funktion (siehe auch Benutzerhandbuch,
Kapitel "Etikettendruck"):

- Der Anwendungsserver laeuft typischerweise in einem Docker-Container im
  lokalen Netz. Ein Container kann grundsaetzlich NUR Geraete ansprechen,
  die selbst im Netzwerk erreichbar sind (WLAN/LAN, TCP/IP). USB- oder
  Bluetooth-Drucker, die direkt an einem PC/Handy angeschlossen sind, kann
  der Server NICHT direkt ansteuern - dafuer muss auf dem jeweiligen Geraet
  weiterhin die erzeugte Etiketten-PDF ueber den normalen Systemdruckdialog
  (mit dem vom Hersteller installierten Brother-Druckertreiber) gedruckt
  werden. Das ist auch technisch der zuverlaessigste Weg, weil dabei der
  offizielle Treiber die Umrechnung in das druckereigene Rasterformat
  uebernimmt.

- Ist der Brother-Drucker dagegen per WLAN/LAN im Netzwerk eingebunden,
  kann der Server versuchen, den Druckauftrag direkt "roh" ueber Port 9100
  (Standard-Rohdruck-Port, auch "JetDirect"/"AppSocket" genannt) an den
  Drucker zu senden. Viele netzwerkfaehige Brother-Etikettendrucker mit
  eingebautem PDF/Direct-Print- bzw. AirPrint-Support akzeptieren darueber
  auch PDF-Daten direkt. Ob das im Einzelfall funktioniert, haengt vom
  konkreten Druckermodell und dessen Firmware ab - deshalb wird diese
  Funktion bewusst als "Direktdruck (Netzwerk, experimentell)" bezeichnet
  und es wird bei Fehlschlag klar auf die PDF-Fallback-Methode verwiesen.
"""
import shutil
import socket
import subprocess


class PrintError(Exception):
    pass


def cups_available() -> bool:
    """True, wenn auf dem Server das CUPS-Drucksystem (lp/lpstat) verfuegbar ist."""
    return shutil.which("lp") is not None and shutil.which("lpstat") is not None


def list_cups_printers() -> list:
    """Liefert die auf dem Server in CUPS eingerichteten Drucker-Warteschlangen.
    Gibt eine leere Liste zurueck, wenn CUPS nicht installiert ist oder kein
    Drucker eingerichtet wurde (kein Fehler - Auto-Erkennung ist optional)."""
    if not shutil.which("lpstat"):
        return []
    try:
        out = subprocess.run(["lpstat", "-a"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return []
    names = []
    for line in (out.stdout or "").splitlines():
        line = line.strip()
        if line:
            # Format: "<queue> accepting requests since ..."
            names.append(line.split(" ", 1)[0])
    return names


def list_cups_devices() -> list:
    """Ermittelt am Server erreichbare Druck-Geraete (lpinfo -v) fuer die
    CUPS-Einrichtung. Liefert [{uri, kind}]; leere Liste, wenn lpinfo fehlt."""
    if not shutil.which("lpinfo"):
        return []
    try:
        out = subprocess.run(["lpinfo", "-v"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return []
    devices = []
    for line in (out.stdout or "").splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and "://" in parts[1]:
            devices.append({"kind": parts[0], "uri": parts[1]})
    return devices


def list_cups_drivers(query: str = "", limit: int = 60) -> list:
    """Liefert verfuegbare Druckertreiber/PPDs (lpinfo -m), optional nach `query`
    gefiltert. [{ppd, name}]; leere Liste, wenn lpinfo fehlt."""
    if not shutil.which("lpinfo"):
        return []
    try:
        out = subprocess.run(["lpinfo", "-m"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return []
    q = (query or "").lower().strip()
    res = []
    for line in (out.stdout or "").splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        ppd, name = parts[0], parts[1]
        if q and q not in name.lower() and q not in ppd.lower():
            continue
        res.append({"ppd": ppd, "name": name})
        if len(res) >= limit:
            break
    return res


def cups_add_printer(name: str, uri: str, ppd: str = "", timeout: float = 30.0):
    """Legt einen Drucker in CUPS an bzw. aktualisiert ihn (lpadmin) und aktiviert
    ihn (Jobs annehmen + eingeschaltet). Wirft PrintError bei Problemen - z.B. wenn
    dem Server die Rechte fuer lpadmin fehlen; der Aufrufer kann dann auf die
    CUPS-Weboberflaeche verweisen."""
    import re
    if not shutil.which("lpadmin"):
        raise PrintError(
            "lpadmin ist auf dem Server nicht verfuegbar. Bitte den Drucker ueber "
            "die CUPS-Weboberflaeche einrichten."
        )
    if not name or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        raise PrintError("Ungueltiger Druckername (erlaubt: Buchstaben, Ziffern, _.-, keine Leerzeichen).")
    if not uri:
        raise PrintError("Kein Geraet/URI angegeben.")
    cmd = ["lpadmin", "-p", name, "-v", uri, "-E"]
    if ppd:
        cmd += ["-m", ppd]
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise PrintError(f"lpadmin fehlgeschlagen ({exc}).")
    if res.returncode != 0:
        err = (res.stderr or b"").decode("utf-8", "replace").strip()
        raise PrintError(
            f"CUPS/lpadmin lehnte die Einrichtung ab: {err or 'unbekannter Fehler'}. "
            "Moeglicherweise fehlen dem Server die Rechte fuer lpadmin - bitte den "
            "Drucker ueber die CUPS-Weboberflaeche einrichten."
        )


def send_pdf_to_cups(queue: str, data: bytes, options: str = "", timeout: float = 30.0):
    """Sendet ein PDF ueber CUPS (lp) an die angegebene Warteschlange. `options`
    sind zusaetzliche lp-Optionen (z.B. 'media=A4 InputSlot=Tray2'), jeweils als
    '-o key=value' uebergeben. Wirft PrintError bei jedem Problem."""
    if not queue:
        raise PrintError("Keine CUPS-Warteschlange angegeben")
    if not shutil.which("lp"):
        raise PrintError(
            "CUPS ist auf dem Server nicht installiert (Befehl 'lp' fehlt). "
            "Bitte CUPS einrichten oder den Drucker per IP:Port anbinden - "
            "alternativ die PDF ueber den Systemdruckdialog drucken."
        )
    cmd = ["lp", "-d", queue]
    for tok in (options or "").split():
        if "=" in tok:
            cmd += ["-o", tok]
    try:
        res = subprocess.run(cmd, input=data, capture_output=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise PrintError(f"Druckauftrag an CUPS-Warteschlange '{queue}' fehlgeschlagen ({exc}).")
    if res.returncode != 0:
        err = (res.stderr or b"").decode("utf-8", "replace").strip()
        raise PrintError(
            f"CUPS lehnte den Druckauftrag an '{queue}' ab: {err or 'unbekannter Fehler'}. "
            "Pruefen Sie, ob der Drucker eingeschaltet und in CUPS erreichbar ist."
        )


def send_raw_to_network_printer(ip: str, data: bytes, port: int = 9100, timeout: float = 5.0):
    """Sendet Rohdaten (hier: PDF-Bytes) per TCP-Socket an Port 9100 eines
    netzwerkfaehigen Druckers. Wirft PrintError bei jedem Verbindungs- oder
    Uebertragungsproblem, damit der Aufrufer dem Benutzer eine klare
    Fehlermeldung mit Fallback-Hinweis anzeigen kann."""
    if not ip:
        raise PrintError("Keine Drucker-IP-Adresse hinterlegt")
    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            sock.sendall(data)
    except (OSError, socket.timeout) as exc:
        raise PrintError(
            f"Verbindung zum Drucker {ip}:{port} fehlgeschlagen ({exc}). "
            "Pruefen Sie, ob der Drucker eingeschaltet, im gleichen Netzwerk "
            "erreichbar ist und Rohdruck ueber Port 9100 unterstuetzt. "
            "Alternativ die Etiketten-PDF ueber den normalen Druckdialog drucken."
        )
