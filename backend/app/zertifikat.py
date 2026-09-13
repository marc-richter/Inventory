"""Eigenes HTTPS-Zertifikat hinterlegen.

Beim Installieren erzeugt das Programm ein selbstsigniertes Zertifikat. Der
Browser warnt davor - was auf jedem neuen Geraet einmal weggeklickt werden muss
und Nutzer daran gewoehnt, Zertifikatswarnungen zu ignorieren. Wer ein eigenes
Zertifikat hat (vom Verein, aus einer internen Zertifizierungsstelle oder von
Let's Encrypt), kann es hier hinterlegen.

Angenommen werden beide ueblichen Formen:

* Zertifikat, Schluessel und Zwischenzertifikat einzeln, oder
* eine PEM-Datei, die alles zusammen enthaelt.

Vor dem Uebernehmen wird geprueft, ob die Dateien lesbar sind, ob der Schluessel
zum Zertifikat passt und ob das Zertifikat ueberhaupt noch gilt. Ein Zertifikat,
das nicht passt, wuerde den Web-Teil beim naechsten Start lahmlegen - deshalb
wird lieber vorher abgelehnt.
"""

import datetime as dt
import re
from typing import Dict, List, Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization

from .logging_config import get_logger

log = get_logger("zertifikat")

_ZERT_MUSTER = re.compile(
    rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", re.S)
_SCHLUESSEL_MUSTER = re.compile(
    rb"-----BEGIN (?:RSA |EC |ENCRYPTED )?PRIVATE KEY-----.*?"
    rb"-----END (?:RSA |EC |ENCRYPTED )?PRIVATE KEY-----", re.S)


class ZertifikatFehler(ValueError):
    """Das Hochgeladene ist als Zertifikat nicht brauchbar."""


def teile_pem(inhalt: bytes) -> Tuple[List[bytes], Optional[bytes]]:
    """Zerlegt eine PEM-Datei in Zertifikate und (hoechstens) einen Schluessel."""
    zertifikate = _ZERT_MUSTER.findall(inhalt or b"")
    treffer = _SCHLUESSEL_MUSTER.search(inhalt or b"")
    return zertifikate, (treffer.group(0) if treffer else None)


def _lade_zertifikat(pem: bytes) -> x509.Certificate:
    try:
        return x509.load_pem_x509_certificate(pem)
    except Exception as exc:
        raise ZertifikatFehler(f"Zertifikat nicht lesbar: {exc}") from exc


def _lade_schluessel(pem: bytes):
    try:
        return serialization.load_pem_private_key(pem, password=None)
    except TypeError as exc:
        raise ZertifikatFehler(
            "Der private Schlüssel ist mit einem Passwort geschützt. Bitte ohne "
            "Passwort exportieren (z.B. mit openssl rsa -in schluessel.pem -out "
            "schluessel-offen.pem)."
        ) from exc
    except Exception as exc:
        raise ZertifikatFehler(f"Privater Schlüssel nicht lesbar: {exc}") from exc


def _namen(zert: x509.Certificate) -> List[str]:
    namen = []
    try:
        for attribut in zert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME):
            namen.append(str(attribut.value))
    except Exception:
        pass
    try:
        san = zert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        for eintrag in san.value.get_values_for_type(x509.DNSName):
            if eintrag not in namen:
                namen.append(eintrag)
        for eintrag in san.value.get_values_for_type(x509.IPAddress):
            text = str(eintrag)
            if text not in namen:
                namen.append(text)
    except x509.ExtensionNotFound:
        pass
    except Exception:
        pass
    return namen


def _text(name) -> str:
    try:
        return name.rfc4514_string()
    except Exception:
        return str(name)


def pruefen(zert_pem: bytes, schluessel_pem: bytes,
            kette_pem: bytes = b"") -> Dict[str, object]:
    """Prueft Zertifikat und Schluessel und liefert die Eckdaten zurueck.

    Wirft ZertifikatFehler, wenn etwas nicht zusammenpasst - dann wird gar nichts
    gespeichert. Ein abgelaufenes Zertifikat wird angenommen, aber deutlich
    gemeldet: manchmal will man es bewusst vorab einspielen.
    """
    zertifikate, schluessel_aus_datei = teile_pem(zert_pem)
    if not zertifikate:
        raise ZertifikatFehler(
            "In der Zertifikatsdatei steht kein Zertifikat (erwartet wird PEM, "
            "beginnend mit -----BEGIN CERTIFICATE-----).")

    zert = _lade_zertifikat(zertifikate[0])

    # Schluessel: entweder eigene Datei oder in derselben PEM-Datei enthalten.
    roh = schluessel_pem or schluessel_aus_datei
    if not roh:
        raise ZertifikatFehler(
            "Es fehlt der private Schlüssel. Entweder als eigene Datei hochladen "
            "oder eine PEM-Datei verwenden, die Zertifikat und Schlüssel enthält.")
    schluessel = _lade_schluessel(roh)

    # Passen Schluessel und Zertifikat zusammen? Vergleich ueber den oeffentlichen
    # Teil - der ist in beiden identisch, wenn sie zusammengehoeren.
    oeffentlich_zert = zert.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    oeffentlich_key = schluessel.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    if oeffentlich_zert != oeffentlich_key:
        raise ZertifikatFehler(
            "Der private Schlüssel gehört nicht zu diesem Zertifikat. Bitte prüfen, "
            "ob beide Dateien aus demselben Vorgang stammen.")

    if kette_pem:
        weitere, _ = teile_pem(kette_pem)
        if not weitere:
            raise ZertifikatFehler(
                "In der Datei mit dem Zwischenzertifikat steht kein Zertifikat.")

    jetzt = dt.datetime.now(dt.timezone.utc)
    try:
        gueltig_ab = zert.not_valid_before_utc
        gueltig_bis = zert.not_valid_after_utc
    except AttributeError:      # aeltere cryptography-Fassungen
        gueltig_ab = zert.not_valid_before.replace(tzinfo=dt.timezone.utc)
        gueltig_bis = zert.not_valid_after.replace(tzinfo=dt.timezone.utc)

    return {
        "subject": _text(zert.subject),
        "issuer": _text(zert.issuer),
        "names": _namen(zert),
        "valid_from": gueltig_ab.isoformat(),
        "valid_to": gueltig_bis.isoformat(),
        "days_left": (gueltig_bis - jetzt).days,
        "expired": gueltig_bis < jetzt,
        "not_yet_valid": gueltig_ab > jetzt,
        "self_signed": zert.subject == zert.issuer,
        "fingerprint": zert.fingerprint(hashes.SHA256()).hex(":").upper(),
        "chain_count": len(teile_pem(kette_pem)[0]) if kette_pem else max(0, len(zertifikate) - 1),
    }


def zusammenbauen(zert_pem: bytes, kette_pem: bytes = b"") -> bytes:
    """Zertifikat + Zwischenzertifikate in EINE Datei, wie nginx sie erwartet.

    Reihenfolge zaehlt: erst das eigene Zertifikat, dann die Kette nach oben.
    Ein privater Schluessel, der versehentlich in derselben Datei steckt, wird
    dabei entfernt - er gehoert in die Schluesseldatei.
    """
    zertifikate, _ = teile_pem(zert_pem)
    if kette_pem:
        zertifikate += teile_pem(kette_pem)[0]
    return b"\n".join(z.strip() for z in zertifikate) + b"\n"
