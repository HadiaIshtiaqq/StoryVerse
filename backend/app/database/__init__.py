from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_connect(dbapi_conn, _record):  # pragma: no cover - trivial
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
            dbapi_conn.isolation_level = None  # let SQLAlchemy emit BEGIN (needed for SAVEPOINT)

        @event.listens_for(engine, "begin")
        def _sqlite_begin(conn):  # pragma: no cover - trivial
            conn.exec_driver_sql("BEGIN")

    return engine


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(bind: Engine | None = None) -> None:
    from app import models  # noqa: F401  (register tables)

    Base.metadata.create_all(bind or engine)
