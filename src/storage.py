import logging
import sqlite3

import pandas as pd

from .database import get_connection, initialize_database

logger = logging.getLogger(__name__)
MOVIE_COLUMNS = ["title", "release_year", "rating", "genre"]


class MovieStorage:
    def __init__(self, db_path="data/movies.db"):
        self.db_path = db_path
        initialize_database(self.db_path)

    def save(self, df):
        """Replace all movie rows in one transaction."""
        # pandas uses NaN for missing values, but SQL needs None to store NULL
        # astype(object) lets the cells hold None, and where() swaps NaN -> None
        data = df[MOVIE_COLUMNS].astpye(object)
        data = data.where(data.notna(), None)

        rows = list(data.itertuples(index=False, name=None))

        connection = get_connection(self.db_path)
        try:
            connection.execute("DELETE FROM movies")
            connection.executemany(
                "INSERT INTO movies (title, release_year, rating, genre)"
                " VALUES (?, ?, ?, ?)",
                rows
            )
            connection.commit()
            logger.debug(f"Stored movies in SQLite: rows={len(rows)}")
        except sqlite3.Error:
            connection.rollback()
        finally:
            connection.close()

    def get(self):
        """Return the four movie columns as a DataFrame, ordered by id."""
        connection = get_connection(self.db_path)
        try:
            rows = connection.execute(
                "SELECT title, release_year, rating, genre FROM movies ORDER BY id"
            ).fetchall()
            # colums= keeps the column namkes even if there are zero rows
            return pd.DataFrame([tuple(r) for r in rows], columns=MOVIE_COLUMNS)
        finally:
            connection.close()


    def select_columns(self, columns, limit=5):
        """Return id plus the requested movie columns, ordered by id."""
        if not columns:
            logger.error("Select at least one column")
            raise ValueError("Select at least one column")

        for column in columns:
            if column not in MOVIE_COLUMNS:
                logger.error(f"Unsupported column: {column}")
                raise ValueError(f"Unsupported column: {column}")

        selected_columns = ", ".join(["id"] + columns)
        connection = get_connection(self.db_path)
        try:
            # column names can't use ? placeholders so I'm puting them in the string
            rows = connection.execute(
                f"SELECT {selected_columns} FROM movies ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
            result = [dict(row) for row in rows]
            logger.debug(f"Selected columns={columns}, rows={len(result)} ")
            return result 
        finally:
            connection.close()

    def count_movies(self):
        """Return the number of stored movies using SQL COUNT(*)."""
        connection = get_connection(self.db_path)
        try:
            return connection.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
        finally:
            connection.close()


    def query_movies(self, columns, min_rating, limit):
        """Return selected fields from matching movies using SQL."""
        # same validation as select_columns 
        if not columns:
            logger.error("Select at least one column")
            raise ValueError("Select at least one column")
        
        for column in columns:
            if column not in MOVIE_COLUMNS:
                logger.error(f"Unsupported column: {column}")
                raise ValueError(f"Unsupported column: {column}")
            
            selected_columns = ", ".join(["id"] + columns)
            connection = get_connection(self.db_path)

            try:
                # highest rating first; ties broken by lowest id
                rows = connection.execute(
                    f"SELECT {selected_columns} FROM movies "
                    "WHERE rating >= ? "
                    "ORDER BY rating DESC, id ASC "
                    "LIMIT ?",
                    (min_rating, limit),
                ).fetchall()
                result = [dict(row) for row in rows]
                logger.debug(f"Queried columns={columns}, rows={len(result)}")
                return result
            finally:
                connection.close()
                
