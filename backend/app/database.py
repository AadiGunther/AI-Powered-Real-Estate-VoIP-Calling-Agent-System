"""Database connections for SQLite."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)


async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def _migrate_calls_table(connection) -> None:
    inspector = sa_inspect(connection)
    try:
        columns = {col["name"] for col in inspector.get_columns("calls")}
    except Exception:
        return

    dialect = connection.dialect.name

    def _add_column_sqlite(name: str, column_def: str) -> None:
        connection.execute(text(f"ALTER TABLE calls ADD COLUMN {name} {column_def}"))

    def _add_column_postgres(name: str, column_def: str) -> None:
        connection.execute(text(f"ALTER TABLE calls ADD COLUMN IF NOT EXISTS {name} {column_def}"))

    def _add_column_generic(name: str, column_def: str) -> None:
        connection.execute(text(f"ALTER TABLE calls ADD COLUMN {name} {column_def}"))

    def _add_column(
        name: str,
        sqlite_def: str,
        pg_def: str | None = None,
        generic_def: str | None = None,
    ) -> None:
        if name in columns:
            return
        if dialect == "sqlite":
            _add_column_sqlite(name, sqlite_def)
        elif dialect == "postgresql":
            _add_column_postgres(name, pg_def or sqlite_def)
        else:
            _add_column_generic(name, generic_def or sqlite_def)

    if "webhook_processed_at" not in columns:
        try:
            _add_column("webhook_processed_at", "DATETIME", "TIMESTAMPTZ", "TIMESTAMP")
        except Exception:
            return

    to_add: list[tuple[str, str, str, str]] = [
        ("parent_call_sid", "VARCHAR(50)", "VARCHAR(50)", "VARCHAR(50)"),
        ("answered_at", "DATETIME", "TIMESTAMPTZ", "TIMESTAMP"),
        ("ended_at", "DATETIME", "TIMESTAMPTZ", "TIMESTAMP"),
        ("duration_seconds", "INTEGER", "INTEGER", "INTEGER"),
        ("handled_by_ai", "BOOLEAN", "BOOLEAN", "BOOLEAN"),
        ("escalated_to_human", "BOOLEAN", "BOOLEAN", "BOOLEAN"),
        ("escalated_to_agent_id", "INTEGER", "INTEGER", "INTEGER"),
        ("escalation_reason", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)"),
        ("recording_url", "VARCHAR(500)", "VARCHAR(500)", "VARCHAR(500)"),
        ("recording_sid", "VARCHAR(50)", "VARCHAR(50)", "VARCHAR(50)"),
        ("recording_duration", "INTEGER", "INTEGER", "INTEGER"),
        ("transcript_text", "TEXT", "TEXT", "TEXT"),
        ("transcript_summary", "TEXT", "TEXT", "TEXT"),
        ("reception_status", "VARCHAR(20)", "VARCHAR(20)", "VARCHAR(20)"),
        ("reception_timestamp", "DATETIME", "TIMESTAMPTZ", "TIMESTAMP"),
        ("caller_username", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)"),
        ("structured_report", "TEXT", "TEXT", "TEXT"),
        ("outcome", "VARCHAR(50)", "VARCHAR(50)", "VARCHAR(50)"),
        ("outcome_notes", "TEXT", "TEXT", "TEXT"),
        ("lead_id", "INTEGER", "INTEGER", "INTEGER"),
        ("lead_created", "BOOLEAN", "BOOLEAN", "BOOLEAN"),
        ("properties_discussed", "TEXT", "TEXT", "TEXT"),
        ("sentiment_score", "REAL", "DOUBLE PRECISION", "DOUBLE"),
        ("customer_satisfaction", "INTEGER", "INTEGER", "INTEGER"),
    ]

    for name, sqlite_def, pg_def, generic_def in to_add:
        try:
            _add_column(name, sqlite_def, pg_def, generic_def)
        except Exception:
            return


def _migrate_notifications_table(connection) -> None:
    inspector = sa_inspect(connection)
    try:
        columns = {col["name"] for col in inspector.get_columns("notifications")}
    except Exception:
        return

    dialect = connection.dialect.name

    def _add_column_sqlite(name: str, column_def: str) -> None:
        connection.execute(text(f"ALTER TABLE notifications ADD COLUMN {name} {column_def}"))

    def _add_column_postgres(name: str, column_def: str) -> None:
        connection.execute(
            text(f"ALTER TABLE notifications ADD COLUMN IF NOT EXISTS {name} {column_def}")
        )

    def _add_column_generic(name: str, column_def: str) -> None:
        connection.execute(text(f"ALTER TABLE notifications ADD COLUMN {name} {column_def}"))

    def _add_column(
        name: str,
        sqlite_def: str,
        pg_def: str | None = None,
        generic_def: str | None = None,
    ) -> None:
        if name in columns:
            return
        if dialect == "sqlite":
            _add_column_sqlite(name, sqlite_def)
        elif dialect == "postgresql":
            _add_column_postgres(name, pg_def or sqlite_def)
        else:
            _add_column_generic(name, generic_def or sqlite_def)

    try:
        _add_column("related_call_id", "INTEGER", "INTEGER", "INTEGER")
    except Exception:
        return


def _migrate_appointments_table(connection) -> None:
    inspector = sa_inspect(connection)
    try:
        columns = {col["name"] for col in inspector.get_columns("appointments")}
    except Exception:
        return

    dialect = connection.dialect.name

    def _add_column_sqlite(name: str, column_def: str) -> None:
        connection.execute(text(f"ALTER TABLE appointments ADD COLUMN {name} {column_def}"))

    def _add_column_postgres(name: str, column_def: str) -> None:
        connection.execute(
            text(f"ALTER TABLE appointments ADD COLUMN IF NOT EXISTS {name} {column_def}")
        )

    def _add_column_generic(name: str, column_def: str) -> None:
        connection.execute(text(f"ALTER TABLE appointments ADD COLUMN {name} {column_def}"))

    def _add_column(
        name: str,
        sqlite_def: str,
        pg_def: str | None = None,
        generic_def: str | None = None,
    ) -> None:
        if name in columns:
            return
        if dialect == "sqlite":
            _add_column_sqlite(name, sqlite_def)
        elif dialect == "postgresql":
            _add_column_postgres(name, pg_def or sqlite_def)
        else:
            _add_column_generic(name, generic_def or sqlite_def)

    try:
        _add_column("contact_number", "VARCHAR(30)", "VARCHAR(30)", "VARCHAR(30)")
    except Exception:
        return


def _init_and_migrate(connection) -> None:
    Base.metadata.create_all(connection)
    _migrate_calls_table(connection)
    _migrate_notifications_table(connection)
    _migrate_appointments_table(connection)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(_init_and_migrate)


@asynccontextmanager
async def lifespan_db():
    await init_db()
    yield
    await engine.dispose()
