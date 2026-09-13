"""Eigenes HTTPS-Zertifikat hinterlegen."""

import datetime as dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app import zertifikat


def _paar(name="inventar.example", tage_gueltig=365, start_offset=-1):
    schluessel = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subjekt = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    jetzt = dt.datetime.now(dt.timezone.utc)
    zert = (x509.CertificateBuilder()
            .subject_name(subjekt).issuer_name(subjekt)
            .public_key(schluessel.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(jetzt + dt.timedelta(days=start_offset))
            .not_valid_after(jetzt + dt.timedelta(days=tage_gueltig))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(name)]), critical=False)
            .sign(schluessel, hashes.SHA256()))
    zert_pem = zert.public_bytes(serialization.Encoding.PEM)
    key_pem = schluessel.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption())
    return zert_pem, key_pem


# --- Pruefung ---------------------------------------------------------------

def test_gueltiges_paar_wird_angenommen():
    zert, key = _paar("pfarrheim.local")
    info = zertifikat.pruefen(zert, key)
    assert "pfarrheim.local" in info["names"]
    assert info["self_signed"] is True
    assert info["expired"] is False
    assert info["days_left"] > 300


def test_schluessel_und_zertifikat_muessen_zusammenpassen():
    zert, _ = _paar("a.local")
    _, fremder_key = _paar("b.local")
    with pytest.raises(zertifikat.ZertifikatFehler) as fehler:
        zertifikat.pruefen(zert, fremder_key)
    assert "gehört nicht zu diesem Zertifikat" in str(fehler.value)


def test_fehlender_schluessel_wird_gemeldet():
    zert, _ = _paar()
    with pytest.raises(zertifikat.ZertifikatFehler) as fehler:
        zertifikat.pruefen(zert, b"")
    assert "private Schlüssel" in str(fehler.value)


def test_unsinn_wird_abgelehnt():
    with pytest.raises(zertifikat.ZertifikatFehler):
        zertifikat.pruefen(b"das ist kein zertifikat", b"")


def test_alles_in_einer_datei():
    """Viele Anbieter liefern Zertifikat und Schluessel in EINER PEM-Datei."""
    zert, key = _paar("kombi.local")
    zusammen = zert + b"\n" + key
    info = zertifikat.pruefen(zusammen, b"")
    assert "kombi.local" in info["names"]


def test_abgelaufenes_zertifikat_wird_gemeldet_aber_nicht_verweigert():
    zert, key = _paar("alt.local", tage_gueltig=-1, start_offset=-400)
    info = zertifikat.pruefen(zert, key)
    assert info["expired"] is True
    assert info["days_left"] < 0


def test_zusammenbauen_entfernt_den_schluessel():
    """Steckt der Schluessel versehentlich in der Zertifikatsdatei, darf er nicht
    in der Datei landen, die nginx als Zertifikat ausliefert."""
    zert, key = _paar()
    gebaut = zertifikat.zusammenbauen(zert + b"\n" + key)
    assert b"PRIVATE KEY" not in gebaut
    assert b"BEGIN CERTIFICATE" in gebaut


def test_zusammenbauen_haengt_die_kette_an():
    zert, _ = _paar("blatt.local")
    kette, _ = _paar("zwischen.local")
    gebaut = zertifikat.zusammenbauen(zert, kette)
    assert gebaut.count(b"BEGIN CERTIFICATE") == 2
    # Das eigene Zertifikat steht zuerst - die Reihenfolge zaehlt fuer nginx.
    assert gebaut.index(b"BEGIN CERTIFICATE") < gebaut.rindex(b"BEGIN CERTIFICATE")


# --- Schnittstelle ----------------------------------------------------------

def test_nur_admin_kommt_an_die_zertifikatsverwaltung(client, admin_headers, db_session):
    from app import models
    from app.security import hash_secret
    db_session.add(models.User(username="verw_zert", roles=["verwalter"], active=True,
                               password_hash=hash_secret("egal1234")))
    db_session.commit()
    token = client.post("/api/v1/auth/login",
                        json={"username": "verw_zert", "password": "egal1234"}).json()["access_token"]
    assert client.get("/api/v1/settings/certificate",
                      headers={"Authorization": f"Bearer {token}"}).status_code == 403
    assert client.get("/api/v1/settings/certificate", headers=admin_headers).status_code == 200


def test_pruefen_ueber_die_schnittstelle(client, admin_headers):
    zert, key = _paar("api.local")
    r = client.post("/api/v1/settings/certificate/pruefen",
                    files={"cert": ("cert.pem", zert, "application/x-pem-file"),
                           "key": ("key.pem", key, "application/x-pem-file")},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert "api.local" in r.json()["names"]


def test_unpassendes_paar_wird_ueber_die_schnittstelle_abgelehnt(client, admin_headers):
    zert, _ = _paar("x.local")
    _, fremd = _paar("y.local")
    r = client.post("/api/v1/settings/certificate/pruefen",
                    files={"cert": ("cert.pem", zert, "application/x-pem-file"),
                           "key": ("key.pem", fremd, "application/x-pem-file")},
                    headers=admin_headers)
    assert r.status_code == 400
    assert "gehört nicht" in r.json()["detail"]


def test_speichern_legt_die_dateien_ab(client, admin_headers, tmp_path, monkeypatch):
    from app.routers.settings import certificate as modul
    monkeypatch.setattr(modul, "CERTS_DIR", tmp_path / "certs")
    monkeypatch.setattr(modul, "CONTROL_DIR", tmp_path / "control")

    zert, key = _paar("speichern.local")
    r = client.post("/api/v1/settings/certificate",
                    files={"cert": ("cert.pem", zert, "application/x-pem-file"),
                           "key": ("key.pem", key, "application/x-pem-file")},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    assert (tmp_path / "certs" / "cert.pem").exists()
    assert (tmp_path / "certs" / "key.pem").exists()
    # Der Neustart des Web-Teils wird ueber eine Signaldatei angefordert.
    assert (tmp_path / "control" / "frontend-reload.request").exists()
    # Der private Schluessel geht niemanden sonst etwas an.
    assert oct((tmp_path / "certs" / "key.pem").stat().st_mode)[-3:] == "600"


def test_altes_zertifikat_wird_vorher_gesichert(client, admin_headers, tmp_path, monkeypatch):
    from app.routers.settings import certificate as modul
    monkeypatch.setattr(modul, "CERTS_DIR", tmp_path / "certs")
    monkeypatch.setattr(modul, "CONTROL_DIR", tmp_path / "control")

    for name in ("erstes.local", "zweites.local"):
        zert, key = _paar(name)
        client.post("/api/v1/settings/certificate",
                    files={"cert": ("cert.pem", zert, "application/x-pem-file"),
                           "key": ("key.pem", key, "application/x-pem-file")},
                    headers=admin_headers)
    sicherungen = list((tmp_path / "certs").glob("cert.pem.vorher-*"))
    assert sicherungen, "das bisherige Zertifikat sollte zur Seite gelegt werden"
