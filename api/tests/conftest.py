import os

# Settings for the tests. These must be set before the app is imported.
os.environ["JWT_SECRET"] = "test-secret-at-least-32-characters-long"
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://mystash:mystash@localhost:5432/mystash_test"
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture
def client():
    """A test client with fresh, empty tables for every test."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return TestClient(app)
