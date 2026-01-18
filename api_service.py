"""
FastAPI REST API Service for SEC 10-K Report Fetcher

This service exposes the SEC 10-K fetching functionality as a REST API,
making it accessible to other teams in Quartr.

Endpoints:
- GET /health - Health check
- POST /api/v1/reports/fetch - Fetch 10-K reports for given tickers
- GET /api/v1/reports/status/{job_id} - Get status of a fetch job (future)
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from pathlib import Path
import logging
import uuid
from datetime import datetime

from sec_10k_fetcher import SEC10KFetcher, fetch_10k_reports, TICKER_TO_CIK

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SEC 10-K Report Fetcher API",
    description="REST API for fetching and converting SEC 10-K reports to PDF",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# In-memory job store (in production, use Redis or database)
job_store: Dict[str, Dict] = {}


# Request/Response Models
class FetchReportsRequest(BaseModel):
    """Request model for fetching reports."""
    tickers: List[str] = Field(
        ...,
        description="List of company ticker symbols",
        example=["AAPL", "META", "GOOGL"]
    )
    output_dir: Optional[str] = Field(
        default="./output_pdfs",
        description="Directory to save PDF files (optional, defaults to ./output_pdfs)"
    )


class FetchReportsResponse(BaseModel):
    """Response model for fetch reports endpoint."""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status: 'started', 'completed', 'failed'")
    message: str = Field(..., description="Status message")
    total_companies: int = Field(..., description="Number of companies to process")


class ReportResult(BaseModel):
    """Model for individual report result."""
    ticker: str
    cik: str
    filing_date: str
    accession_number: str
    pdf_path: str
    status: str = "success"


class JobStatusResponse(BaseModel):
    """Response model for job status."""
    job_id: str
    status: str
    created_at: str
    completed_at: Optional[str]
    total_companies: int
    processed: int
    successful: int
    failed: int
    results: List[ReportResult]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    service: str = "SEC 10-K Fetcher API"


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat()
    )


@app.post("/api/v1/reports/fetch", response_model=FetchReportsResponse, tags=["Reports"])
async def fetch_reports(
    request: FetchReportsRequest,
    background_tasks: BackgroundTasks
):
    """
    Fetch latest 10-K reports for specified companies.
    
    This endpoint accepts a list of company tickers and fetches their latest
    10-K reports, converting them to PDF format.
    
    The processing happens in the background. Use the job_id to check status.
    """
    job_id = str(uuid.uuid4())
    
    # Validate tickers
    valid_tickers = []
    invalid_tickers = []
    
    for ticker in request.tickers:
        ticker_upper = ticker.upper()
        if ticker_upper in TICKER_TO_CIK:
            valid_tickers.append(ticker_upper)
        else:
            invalid_tickers.append(ticker_upper)
    
    if not valid_tickers:
        raise HTTPException(
            status_code=400,
            detail=f"No valid tickers provided. Invalid: {invalid_tickers}"
        )
    
    # Initialize job in store
    job_store[job_id] = {
        "job_id": job_id,
        "status": "started",
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "total_companies": len(valid_tickers),
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "results": []
    }
    
    # Log invalid tickers
    if invalid_tickers:
        logger.warning(f"Invalid tickers ignored: {invalid_tickers}")
    
    # Schedule background task
    background_tasks.add_task(
        process_reports_job,
        job_id=job_id,
        tickers=valid_tickers,
        output_dir=request.output_dir or "./output_pdfs"
    )
    
    return FetchReportsResponse(
        job_id=job_id,
        status="started",
        message=f"Started processing {len(valid_tickers)} companies",
        total_companies=len(valid_tickers)
    )


async def process_reports_job(job_id: str, tickers: List[str], output_dir: str):
    """
    Background task to process reports.
    
    Args:
        job_id: Unique job identifier
        tickers: List of company tickers
        output_dir: Output directory for PDFs
    """
    try:
        logger.info(f"Starting job {job_id} for tickers: {tickers}")
        
        # Process reports
        results = fetch_10k_reports(tickers=tickers, output_dir=output_dir)
        
        # Update job status
        job_store[job_id].update({
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "processed": len(tickers),
            "successful": len(results),
            "failed": len(tickers) - len(results),
            "results": [
                ReportResult(
                    ticker=r["ticker"],
                    cik=r["cik"],
                    filing_date=r["filing_date"],
                    accession_number=r["accession_number"],
                    pdf_path=r["pdf_path"],
                    status="success"
                )
                for r in results
            ]
        })
        
        logger.info(f"Completed job {job_id}: {len(results)}/{len(tickers)} successful")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        job_store[job_id].update({
            "status": "failed",
            "completed_at": datetime.utcnow().isoformat(),
            "error": str(e)
        })


@app.get("/api/v1/reports/status/{job_id}", response_model=JobStatusResponse, tags=["Reports"])
async def get_job_status(job_id: str):
    """
    Get the status of a report fetching job.
    
    Args:
        job_id: Unique job identifier returned from /fetch endpoint
    """
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    job = job_store[job_id]
    
    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
        total_companies=job["total_companies"],
        processed=job["processed"],
        successful=job["successful"],
        failed=job["failed"],
        results=job["results"]
    )


@app.get("/api/v1/reports/download/{job_id}/{ticker}", tags=["Reports"])
async def download_report(job_id: str, ticker: str):
    """
    Download a specific PDF report by job ID and ticker.
    
    Args:
        job_id: Job identifier
        ticker: Company ticker symbol
    """
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    job = job_store[job_id]
    
    # Find the report for this ticker
    ticker_upper = ticker.upper()
    report = next(
        (r for r in job["results"] if r["ticker"] == ticker_upper),
        None
    )
    
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"Report for ticker {ticker} not found in job {job_id}"
        )
    
    pdf_path = Path(report["pdf_path"])
    
    if not pdf_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"PDF file not found: {report['pdf_path']}"
        )
    
    return FileResponse(
        path=pdf_path,
        filename=pdf_path.name,
        media_type="application/pdf"
    )


@app.get("/api/v1/companies", tags=["Companies"])
async def list_supported_companies():
    """List all supported companies with their tickers and CIKs."""
    return {
        "companies": [
            {"ticker": ticker, "cik": cik}
            for ticker, cik in TICKER_TO_CIK.items()
        ],
        "total": len(TICKER_TO_CIK)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
