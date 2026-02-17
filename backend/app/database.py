"""Database connections for SQLite."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text, inspect as sa_inspect
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

    if "webhook_processed_at" not in columns:
        try:
            if dialect == "sqlite":
                connection.execute(
                    text("ALTER TABLE calls ADD COLUMN webhook_processed_at DATETIME")
                )
            elif dialect == "postgresql":
                connection.execute(
                    text(
                        "ALTER TABLE calls ADD COLUMN IF NOT EXISTS webhook_processed_at TIMESTAMPTZ"
                    )
                )
            else:
                connection.execute(
                    text("ALTER TABLE calls ADD COLUMN webhook_processed_at TIMESTAMP")
                )
        except Exception:
            return

    if "reception_status" not in columns:
        try:
            if dialect == "sqlite":
                connection.execute(
                    text("ALTER TABLE calls ADD COLUMN reception_status VARCHAR(20)")
                )
            elif dialect == "postgresql":
                connection.execute(
                    text(
                        "ALTER TABLE calls ADD COLUMN IF NOT EXISTS reception_status VARCHAR(20)"
                    )
                )
            else:
                connection.execute(
                    text("ALTER TABLE calls ADD COLUMN reception_status VARCHAR(20)")
                )
        except Exception:
            return

    if "reception_timestamp" not in columns:
        try:
            if dialect == "sqlite":
                connection.execute(
                    text("ALTER TABLE calls ADD COLUMN reception_timestamp DATETIME")
                )
            elif dialect == "postgresql":
                connection.execute(
                    text(
                        "ALTER TABLE calls ADD COLUMN IF NOT EXISTS reception_timestamp TIMESTAMPTZ"
                    )
                )
            else:
                connection.execute(
                    text("ALTER TABLE calls ADD COLUMN reception_timestamp TIMESTAMP")
                )
        except Exception:
            return

    if "caller_username" not in columns:
        try:
            if dialect == "sqlite":
                connection.execute(
                    text("ALTER TABLE calls ADD COLUMN caller_username VARCHAR(255)")
                )
            elif dialect == "postgresql":
                connection.execute(
                    text(
                        "ALTER TABLE calls ADD COLUMN IF NOT EXISTS caller_username VARCHAR(255)"
                    )
                )
            else:
                connection.execute(
                    text("ALTER TABLE calls ADD COLUMN caller_username VARCHAR(255)")
                )
        except Exception:
            return


def _init_and_migrate(connection) -> None:
    Base.metadata.create_all(connection)
    _migrate_calls_table(connection)


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
