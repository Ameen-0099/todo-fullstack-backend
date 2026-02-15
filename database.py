from typing import Generator
import os
from sqlmodel import create_engine, Session, SQLModel

# Make sure to import models to register them with SQLModel.metadata
from models import User, Task

# No global engine or create_db_and_tables in this version

def get_session(engine_to_use = None) -> Generator[Session, None, None]:
    if engine_to_use:
        current_engine = engine_to_use
    else:
        # This branch is for production/development usage outside of tests
        print("Attempting to connect to the database.")
        DATABASE_URL = os.getenv("DATABASE_URL")
        if not DATABASE_URL:
            print("DATABASE_URL environment variable is NOT set.")
            raise ValueError("DATABASE_URL environment variable not set for production/development.")
        else:
            print("DATABASE_URL environment variable is set.")
            # Log a redacted version for verification, not the whole key
            print(f"DATABASE_URL format check: {DATABASE_URL[:15]}...")

        current_engine = create_engine(DATABASE_URL, echo=True)

    with Session(current_engine) as session:
        yield session