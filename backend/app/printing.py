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
import socket


class PrintError(Exception):
    pass


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
