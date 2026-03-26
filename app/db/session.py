from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_sqlalchemy_engine(database_url: str):
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_sqlalchemy_engine(database_url)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    db = session_factory()
    try:
        yield db
    finally:
        db.close()

