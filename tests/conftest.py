import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models import Base, User


@pytest.fixture(autouse=True)
def pricing_defaults(monkeypatch):
    """Pin money settings so results never depend on a developer's local .env file."""
    monkeypatch.setattr(settings, "base_rate", 2.0)
    monkeypatch.setattr(settings, "rate_per_kg", 1.0)
    monkeypatch.setattr(settings, "volumetric_divisor", 5000.0)
    monkeypatch.setattr(settings, "commission_rate", 0.10)
    monkeypatch.setattr(settings, "currency", "ZMW")


@pytest.fixture(autouse=True)
def buyer_email_policy(monkeypatch):
    """Keep buyer signup tests aligned with the Gmail-only signup policy."""
    monkeypatch.setattr(settings, "allowed_email_suffixes", ".gmail.com")


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(session_factory):
    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(session_factory):
    """Create a verified user directly in the database; returns (user_id, auth_headers)."""
    def _make(email, **flags):
        with session_factory() as session:
            if flags.get("is_admin"):
                flags.setdefault("account_type", "admin")
            elif flags.get("is_seller"):
                flags.setdefault("account_type", "seller")
            user = User(email=email, password_hash="x", campus="Campus", dorm="Hall", is_verified=True, **flags)
            session.add(user)
            session.commit()
            return user.id, {"Authorization": f"Bearer {create_access_token(user.id)}"}
    return _make
