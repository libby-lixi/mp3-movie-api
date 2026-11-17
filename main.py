import io
import json
import logging
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from src import HealthResponse, MovieStorage, MovieUploadInfo, MovieDataResponse, MovieProcessingReport, ProcessConfig
from src.storage import MO
from data_pipeline import create_cleaning_report, process_data, validate_dataframe


setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Processing API", version="1.0.0")
app.middleware("http")(log_requests) # puts the "security guard" at the front door
storage = MovieStorage()

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
    total = storage.count_movies()
    if total == 0:
        return {"data": [], "total_rows": 0}
    
    # select_columns already returns id + the columns we ask for
    data = storage.select_columns(MOVIE_COLUMNS, limit)
    logger.info(f"Retrieved movies: retuened_rows={len(data)}, total_rows={total}")
    return {"data": data, "total_rows": total}

