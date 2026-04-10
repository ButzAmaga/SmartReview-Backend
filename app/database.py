from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from sqlalchemy.orm import DeclarativeBase

# SQLite for local dev — swap URL for PostgreSQL in production
DATABASE_URL = "sqlite:///./myapp.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Base = declarative_base()


# Replace Base = declarative_base() with this: 2.0 version
class Base(DeclarativeBase):
    pass

# Dependency — gives each request its own DB session, then closes it
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()