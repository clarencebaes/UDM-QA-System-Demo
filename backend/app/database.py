from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal = None


def init_engine():
    """Create the database if needed, then open a pooled connection."""
    global engine, SessionLocal
    db_name = settings.mysql_database

    # Managed providers (e.g. Aiven) hand you a pre-created database and do not
    # grant CREATE DATABASE privileges, so skip that step when asked.
    if not settings.mysql_skip_create_db:
        admin = create_engine(
            settings.server_url,
            connect_args=settings.connect_args,
            pool_pre_ping=True,
        )
        with admin.connect() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
            conn.commit()
        admin.dispose()

    engine = create_engine(
        settings.database_url,
        connect_args=settings.connect_args,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=280,
        pool_timeout=30,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
