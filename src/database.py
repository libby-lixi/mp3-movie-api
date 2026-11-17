import sqlite3
from pathlib import Path


def get_connection(db_path):
    """Return a fresh connection with rows accessible by column name."""
    # create the parent directory, connect, and set sqlite3.Row.
    path = Path(db_path)
    # make the data/folder if it doesn't exist yet
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    # lets us use row["title"] and dict(now) instead of row[0]
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(db_path):
    """Create the movie table if it does not exist."""
    connection = get_connection(db_path)
    try: 
        # no NOT NULL on the datga columns, so NULL is allowed
        connection.execute(
            """CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY,
                title TEXT,
                release_year INTEGER,
                rating REAL,
                genre TEXT
            )
            """
        )
        connection.commit()
    finally:
        connection.close()
