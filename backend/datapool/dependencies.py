from collections.abc import Generator

from datapool.connection import SessionLocal
from sqlalchemy.orm import Session


def get_datapool_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
