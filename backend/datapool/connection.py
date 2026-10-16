import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATAPOOL_DATABASE_URL = os.getenv("DATAPOOL_DATABASE_URL")

if not DATAPOOL_DATABASE_URL:
    raise RuntimeError(
        "DATAPOOL_DATABASE_URL is not configured in .env"
    )

engine = create_engine(
    DATAPOOL_DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()
