import os

import pytest

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["APP_ENV"] = "test"

from app.db import Base, SessionLocal, engine  # noqa: E402


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        yield session
    Base.metadata.drop_all(bind=engine)

