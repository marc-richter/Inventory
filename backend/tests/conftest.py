import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment variables BEFORE importing app
test_data_dir = tempfile.mkdtemp()
os.environ["DATA_DIR"] = test_data_dir
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["DEFAULT_ADMIN_PASSWORD"] = "admin1234"
os.environ["DEFAULT_ADMIN_USERNAME"] = "admin"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "720"
os.environ["WEB_PORT"] = "8080"
os.environ["WEB_TLS_PORT"] = "8443"
os.environ["BACKUP_HOST_PATH"] = "./backups"
os.environ["INITIAL_ASSETS_DIR"] = test_data_dir
os.environ["CONTROL_DIR"] = test_data_dir

from app.main import app
from app.database import Base, get_db
from app import models
from app.security import hash_secret, verify_secret


@pytest.fixture(scope="session")
def engine():
    """Create a test SQLite database in memory."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    # Standard-Stammdaten einmalig anlegen (Kategorien "Kleidung"/"Schluessel",
    # Status, Groessenarten, Administrator). Im Betrieb macht das der Server beim
    # ersten Start; ohne das schlugen Tests auf vorhandene Standardwerte fehl.
    from app.seed import seed
    Session = sessionmaker(bind=engine)
    grund = Session()
    try:
        seed(grund)
    finally:
        grund.close()
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(engine):
    """Create a fresh database session for each test."""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with overridden DB dependency."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session):
    """Der Administrator der Testdatenbank.

    Die Grunddaten legen bereits einen an (wie bei einer frischen Installation);
    nur falls er fehlt, wird er hier erzeugt.
    """
    vorhanden = db_session.query(models.User).filter(models.User.username == "admin").first()
    if vorhanden:
        # Die Grunddaten vergeben keine PIN - die Anmeldetests brauchen eine.
        if not vorhanden.pin_hash:
            vorhanden.pin_hash = hash_secret("1234")
            vorhanden.pin_length = 4
            db_session.commit()
        return vorhanden
    user = models.User(
        username="admin",
        full_name="Admin User",
        roles=["admin"],
        password_hash=hash_secret("admin1234"),
        pin_hash=hash_secret("1234"),
        pin_length=4,
        active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(client, admin_user):
    """Get auth headers for admin user."""
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(auth_headers):
    """Gleiche Anmeldedaten wie auth_headers - die Integrationstests in
    test_core.py verwenden diesen Namen."""
    return auth_headers


@pytest.fixture
def kleidung_type(client, admin_headers):
    """Kategorie + Artikeltyp fuer Kleidung, ueber die Schnittstelle angelegt.

    Die Integrationstests in test_core.py erwarten ein Paar (Kategorie-Nummer,
    Typ-Nummer) - der Weg ueber die Schnittstelle stellt sicher, dass dabei auch
    die Voreinstellungen der Kategorie greifen.
    """
    kat = client.post("/api/v1/categories",
                      json={"name": "Kleidung", "issuable_default": True},
                      headers=admin_headers)
    assert kat.status_code == 200, kat.text
    cat_id = kat.json()["id"]
    typ = client.post("/api/v1/types",
                      json={"name": "Einsatzjacke", "category_id": cat_id},
                      headers=admin_headers)
    assert typ.status_code == 200, typ.text
    return cat_id, typ.json()["id"]


@pytest.fixture
def test_category(db_session):
    """Create a test category."""
    cat = models.Category(name="Test Kategorie", issuable_default=True)
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


@pytest.fixture
def test_type(db_session, test_category):
    """Create a test article type."""
    atype = models.ArticleType(name="Test Typ", category_id=test_category.id)
    db_session.add(atype)
    db_session.commit()
    db_session.refresh(atype)
    return atype


@pytest.fixture
def test_organization(db_session):
    """Create a test organization."""
    org = models.Organization(name="Test Abteilung")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def test_storage_location(db_session):
    """Create a test storage location."""
    loc = models.StorageLocation(name="Test Lagerort")
    db_session.add(loc)
    db_session.commit()
    db_session.refresh(loc)
    return loc