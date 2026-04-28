from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase



SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./blog.db" # SQLite driver = sync, SQLite + aiosqlite = async

# Engine = bridge between app and DB

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread" : False} # SQLite normally allows only one thread but FastAPI runs multiple requests(threads). So we disable restrictions
)

# SessionLocal → creates session → session talks to DB
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False) # sessionmaker(...) → Creates a factory for sessions

# async_sessionmaker → creates async sessions
# class_=AsyncSession → use async session class
# expire_on_commit=False → prevent auto reload after commit


class Base(DeclarativeBase): # Used to define database models
    pass

# Dependency
async def get_db():    # Creates a database session per request
    async with AsyncSessionLocal() as session:
        yield session


# *** Request → get_db() → DB session → query → response → session closed ***

