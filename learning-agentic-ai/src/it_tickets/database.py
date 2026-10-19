"""Engine and session factory setup."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from it_tickets.models import Base


def create_session_factory(database_path: str) -> sessionmaker[Session]:
    """Create the SQLite engine, ensure tables exist, and return a session factory."""
    db_file = Path(database_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
