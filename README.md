MP 3 Movie API

This is a FastAPI backend that lest users manage, search, and clean a movie collection. It uses SQLite for persistence so datra surviuves server restarts, and Fake Redis to keep things snappy with a caching layer.

- Ingesting Data (POST /upload): You can uplaod a CSV file of movies. The app stricly checks that it contains the exact columns (title, release_year, rating, and genre) befor ecompletely replacing the existing collection.
- Storage & SQL(src/database.py & src/storage.py): Handles setting up the SQLite connection and table. The MovieStorage class takes care of saving, counting, and querying movies directly via SQL
- Searching (GET /movie/search): This allows users to filter movies by a minimum rating and sort the results using SQL queries.
- Data Cleaning (POST /movies/process): Runs the MP1 data pipeline functions to validate and clean up the stored movies, then writes the polished rows right back to the database. 
- Smart Caching (src/cache.py): The MovieCache uses FakeRedis to cache GET /movies responses for 90 seconds (keyed limit). Whenever you upload new data or run the processing pipeline, the cache resets automatically so users alaways get fresh data.
- Models & Lodging (src/models.py, src/utils.py, src/middleware.py): Pydantic handles request and response validation, while custom utils and middleware keep track of logging.

