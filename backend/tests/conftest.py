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
    """Create an admin user and return its credentials."""
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