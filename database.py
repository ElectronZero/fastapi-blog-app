from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# create_engine → connects to DB
# DeclarativeBase → base class for models
# sessionmaker → creates DB sessions

SQLALCHEMY_DATABASE_URL = "sqlite:///./blog.db" #using sqlite db

# Engine = bridge between app and DB

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread" : False} # SQLite normally allows only one thread but FastAPI runs multiple requests(threads). So we disable restrictions
)

# SessionLocal → creates session → session talks to DB
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) # sessionmaker(...) → Creates a factory for sessions

# Session = temporary DB connection used for queries
# Set autocommit to False so to manually commit -> db.commit()
# Set autoflush to False so that changes are not automatically pushed to DB
# bind = Engine → Connect session to database


class Base(DeclarativeBase): # Used to define database models
    pass

# Dependency
def get_db():    # Creates a database session per request
    with SessionLocal() as db:
        yield db


# *** Request → get_db() → DB session → query → response → session closed ***

