import io
import logging
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from src import (
    HealthResponse,
    MovieCache,
    MovieStorage,
    MovieUploadInfo,
    MovieDataResponse,
    MovieProcessingReport,
    ProcessConfig,
)
from src.storage import MOVIE_COLUMNS
from src.utils import setup_logging
from src.middleware import log_requests
from data_pipeline import create_cleaning_report, process_data, validate_dataframe


setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Processing API", version="1.0.0")
app.middleware("http")(log_requests) # puts the "security guard" at the front door
storage = MovieStorage()
cache = MovieCache()


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return HealthResponse(status="ok", version="1.0.0")


@app.post("/upload", response_model=MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    """Read and store a CSV upload."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Could not parse CSV file.")
    
    if sorted(df.columns) != sorted(MOVIE_COLUMNS):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must have exactly these columns: {MOVIE_COLUMNS}",
        )
    if df.empty:
        raise HTTPException(status_code=400, detail="CSV file is empty.")
    
    df = df[MOVIE_COLUMNS] # put columns in the right order

    # replace whatever was sorted before
    storage.save(df)
    logger.info(f"Uploaded dataset: filename={file.filename}, rows={len(df)}")

    return {
        "filename": file.filename,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
    }

@app.get("/movies", response_model=MovieDataResponse)
def get_movies(limit: int = Query(default=100, ge=1)):
    """Return up to limit movies plus the total count."""
    # check the cache first
    cached = cache.get(limit)
    if cached is not None:
        logger.info(f"Cache hit for movies: limit={limit}")
        return cached

    # cache miss, so read from the database like in Part 1
    total = storage.count_movies()
    if total == 0:
        response = {"data": [], "total_rows": 0}
    else:
        data = storage.select_columns(MOVIE_COLUMNS, limit)
        response = {"data": data, "total_rows": total}

    # save the response so the next identical request is a hit
    cache.set(limit, response)
    logger.info(f"Retrieved movies: returned_rows={len(response['data'])}")
    return response



@app.get("/movies/search", response_model=list[dict])
def query_movies(
    columns: list[str] = Query(default=["title"]),
    min_rating: float = Query(default=0, ge=0, le=10),
    limit: int = Query(default=100, ge=1)
):
    try:
        result = storage.query_movies(columns, min_rating, limit)
    except ValueError as e:
        # bad column name -> 400 instead of a crash
        raise HTTPException(status_code=400, detail=str(e))
    
    logger.info(
        f"Queried movies: columns={columns}, min_rating={min_rating}, "
        f"returned_rows={len(result)}"
    )
    return result

@app.post("/movies/process", response_model=MovieProcessingReport)
def process_movies(config: ProcessConfig):
    df = storage.get()
    if df.empty:
        raise HTTPException(status_code=400, detail="No movies to process.")
    
    # turn the config model into a normal dict for the MP1 functions
    config_dict = config.model_dump()
    required_columns = config_dict["validation"]["required_columns"]
    numeric_columns = config_dict["validation"]["numeric_columns"]

    # make sure every numeric column actually exists
    for column in numeric_columns:
        if column not in df.columns:
            logger.warning(f"Numeric column not found: {column}")
            raise HTTPException(status_code=400, detail=f"Numeric column not found: {column}")

    try:
        validated_df = validate_dataframe(df, required_columns, numeric_columns)
        validation_rows_removed = len(df) - len(validated_df)
        logger.info(f"Validated movies: rows_removed={validation_rows_removed}")

        before_processing = validated_df.copy()
        processed_df = process_data(validated_df, config_dict)
        cleaning_report = create_cleaning_report(before_processing, processed_df)
    except ValueError as error:
        logger.warning(f"Processing failed: error={error}")
        raise HTTPException(status_code=400, detail=str(error))

    # replace the stored movies with the cleaned ones
    storage.save(processed_df)
    cache.invalidate() # cleared the cache

    logger.info(
        f"Processed movies: validation_removed={validation_rows_removed}, "
        f"cleaning_report={cleaning_report}"
    )

    return {
        "validation_rows_removed": validation_rows_removed,
        "cleaning_report": cleaning_report,
    }