import pandas as pd
import pytest

from src import MovieStorage
import main


def test_movies_persist(client, test_storage, uploaded_movies):
    # a brand new storage object reading the same database file
    other_storage = MovieStorage(test_storage.db_path)

    df = other_storage.get()
    assert len(df) == 20
    assert other_storage.count_movies() == 20
    assert list(df.columns) == ["title", "release_year", "rating", "genre"]

    # titles should be in the same order as the original CSV
    original = pd.read_csv("fixtures/sample_movies.csv")
    assert list(df["title"]) == list(original["title"])

    # IDs from storage and from the API should both be 1 through 20
    storage_ids = [row["id"] for row in other_storage.select_columns(["title"], 100)]
    response = client.get("/movies", params={"limit": 100})
    api_ids = [movie["id"] for movie in response.json()["data"]]

    assert storage_ids == list(range(1, 21))
    assert api_ids == storage_ids


def test_cache_and_processing(client, uploaded_movies, processing_body):
    # 1. first requests are misses, and their responses get cached
    response_100 = client.get("/movies", params={"limit": 100})
    response_1 = client.get("/movies", params={"limit": 1})
    assert response_100.status_code == 200
    assert response_1.status_code == 200
    assert main.cache.get(100) == response_100.json()
    assert main.cache.get(1) == response_1.json()

    # 2. repeating limit=100 gives the same response
    repeat = client.get("/movies", params={"limit": 100})
    assert repeat.json() == response_100.json()

    # 3. processing removes 4 rows and clears the cache
    process = client.post("/movies/process", json=processing_body)
    assert process.status_code == 200
    report = process.json()
    assert report["validation_rows_removed"] == 0
    assert report["cleaning_report"]["rows_before"] == 20
    assert report["cleaning_report"]["rows_after"] == 16
    assert report["cleaning_report"]["rows_removed"] == 4
    assert main.cache.get(100) is None
    assert main.cache.get(1) is None

    # 4. new retrieval shows the 16 processed movies
    after = client.get("/movies", params={"limit": 100})
    body = after.json()
    assert body["total_rows"] == 16

    titles = [movie["title"] for movie in body["data"]]
    expected_titles = [
        "Movie A", "Movie B", "Movie C", "Movie D",
        "Movie E", "Movie F", "Movie G", "Movie H",
        "Movie I", "Movie J", "Movie K", "Movie L",
        "Movie M", "Movie N", "Movie O", "Movie P",
    ]
    assert titles == expected_titles

    ids = [movie["id"] for movie in body["data"]]
    assert ids == list(range(1, 17))

    # the new response is cached
    assert main.cache.get(100) == body


def test_cache_hit_skips_database(client, uploaded_movies, monkeypatch):
    # 1. fill the cache
    first = client.get("/movies", params={"limit": 100})
    assert first.status_code == 200

    # 2. if the database gets called now, the test fails
    def fail(*args, **kwargs):
        pytest.fail("Database should not be used on a cache hit")

    monkeypatch.setattr(main.storage, "select_columns", fail)
    monkeypatch.setattr(main.storage, "count_movies", fail)

    # 3. same request should come from the cache
    second = client.get("/movies", params={"limit": 100})
    assert second.status_code == 200
    assert second.json() == first.json()
