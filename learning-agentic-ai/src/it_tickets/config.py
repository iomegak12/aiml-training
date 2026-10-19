"""Configuration loaded from the environment / .env file."""

import os

from dotenv import find_dotenv, load_dotenv

from it_tickets.exceptions import ConfigurationError

DATABASE_PATH_ENV_VAR = "TICKETS_DB_PATH"


def get_database_path() -> str:
    """Return the SQLite database path configured in .env (or the environment).

    Raises:
        ConfigurationError: if TICKETS_DB_PATH is not set or is empty.
    """
    load_dotenv(find_dotenv(usecwd=True))  # look for .env from the caller's working directory
    path = os.getenv(DATABASE_PATH_ENV_VAR, "").strip()
    if not path:
        raise ConfigurationError(
            f"{DATABASE_PATH_ENV_VAR} is not set. Add it to your .env file, "
            f"e.g. {DATABASE_PATH_ENV_VAR}=./data/tickets.db"
        )
    return path
