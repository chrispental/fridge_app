"""Shared test fixtures.

Unit tests run on in-memory SQLite via `create_all` for speed;
`tests/test_migrations.py` proves that shortcut matches the Alembic head.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.auth import DEFAULT_LOCAL_USER_ID, AuthUser
from app.database import Base

# The single-user-mode user. Routers are called directly with `user=LOCAL_USER`.
LOCAL_USER = AuthUser(id=DEFAULT_LOCAL_USER_ID)
OTHER_USER = AuthUser(id="11111111-1111-1111-1111-111111111111", email="other@example.com")


def make_session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([models.User(id=LOCAL_USER.id), models.User(id=OTHER_USER.id)])
    session.commit()
    return session


@pytest.fixture
def db():
    session = make_session()
    yield session
    session.close()
