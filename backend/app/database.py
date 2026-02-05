"""Database connections for SQLite and MongoDB."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# SQLAlchemy Base
class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass


# SQLite AsyncEngine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# MongoDB Client
class MongoDB:
    """MongoDB connection manager."""

    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

    @classmethod
    async def connect(cls) -> None:
        """Connect to MongoDB."""
        cls.client = AsyncIOMotorClient(settings.mongodb_url)
        cls.db = cls.client[settings.mongodb_db]

    @classmethod
    async def disconnect(cls) -> None:
        """Disconnect from MongoDB."""
        if cls.client:
            cls.client.close()

    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        """Get MongoDB database instance."""
        if cls.db is None:
            raise RuntimeError("MongoDB not connected. Call MongoDB.connect() first.")
        return cls.db


def get_mongodb() -> AsyncIOMotorDatabase:
    """Dependency to get MongoDB database."""
    return MongoDB.get_db()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def lifespan_db():
    """Database lifespan context manager."""
    # Startup
    await init_db()
    await MongoDB.connect()
    yield
    # Shutdown
    await MongoDB.disconnect()
    await engine.dispose()
