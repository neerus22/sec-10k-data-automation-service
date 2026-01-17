# SEC 10-K Report Fetcher and PDF Converter

This project retrieves the latest 10-K annual reports from the SEC EDGAR database and converts them into PDF format. The implementation is structured as a reusable data ingestion service suitable for integration into broader data automation workflows. 
NOTE: This project is submitted as part of the Quartr Data Automation assignment.



## Overview

This tool automates the process of:
1. Retrieving company submission metadata from the SEC EDGAR API
2. Identifying the latest 10-K filing for each company
3. Downloading the filing documents (HTML/TXT format)
4. Converting the documents to PDF format

## Supported Companies

The tool is configured to fetch 10-K reports for the following companies:

- **AAPL** - Apple Inc.
- **META** - Meta Platforms Inc.
- **GOOGL** - Alphabet Inc. (Class A)
- **AMZN** - Amazon.com Inc.
- **NFLX** - Netflix Inc.
- **GS** - The Goldman Sachs Group Inc.

## Features

- ✅ **SEC API Compliance**: Proper User-Agent headers and rate limiting
- ✅ **Robust Error Handling**: Graceful handling of API errors and missing filings
- ✅ **PDF Conversion**: Supports both HTML and TXT filing formats
- ✅ **Image Downloading**: Automatically downloads referenced images for complete PDFs
- ✅ **REST API Service**: FastAPI service for team integration with background job processing
- ✅ **Comprehensive Testing**: Unit tests and integration tests covering critical functionality
- ✅ **Comprehensive Logging**: Detailed logs for debugging and monitoring
- ✅ **Type Hints**: Full type annotations for better code maintainability
- ✅ **Clean Architecture**: Modular, extensible design for production use

## Prerequisites

### System Requirements

- **Python 3.8+**
- **Internet connection** for SEC API access

### System Dependencies (for PDF conversion)

The PDF conversion uses WeasyPrint, which requires system libraries:

#### macOS
```bash
brew install pango gdk-pixbuf libffi
```

#### Ubuntu/Debian
```bash
sudo apt-get install python3-cffi python3-brotli libpango-1.0-0 libpangoft2-1.0-0
```

#### Windows
WeasyPrint should work with pre-built wheels. If you encounter issues, install GTK+ runtime from [gtk.org](https://gtk.org/).

## Installation

1. **Clone or download this repository**

2. **Create a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Command Line Interface

#### Fetch reports for default companies (all 6 companies from assignment):
```bash
python scripts/fetch_reports.py
```

#### Fetch reports for specific companies:
```bash
python scripts/fetch_reports.py --tickers AAPL,META,GOOGL --output_dir ./pdfs
```

#### Command-line Options:
- `--tickers`: Comma-separated list of stock ticker symbols (default: AAPL,META,GOOGL,AMZN,NFLX,GS)
- `--output_dir`: Directory to save PDF files (default: ./output_pdfs)

### REST API Service

#### Start the API server:
```bash
python src/api/main.py
# Or with uvicorn directly:
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Documentation (Swagger UI)**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **Health Check**: http://localhost:8000/health

**Note**: Use `http://localhost:8000/health` (not `http://0.0.0.0:8000/health`) in your browser.  
For detailed API testing instructions, see `docs/API_TESTING.md`.

#### API Endpoints:

**1. Fetch Reports** (POST `/api/v1/reports/fetch`):
```bash
curl -X POST "http://localhost:8000/api/v1/reports/fetch" \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["AAPL", "META", "GOOGL"], "output_dir": "./pdfs"}'
```

Returns:
```json
{
  "job_id": "uuid-here",
  "status": "started",
  "message": "Started processing 3 companies",
  "total_companies": 3
}
```

**2. Check Job Status** (GET `/api/v1/reports/status/{job_id}`):
```bash
curl "http://localhost:8000/api/v1/reports/status/{job_id}"
```

**3. Download PDF** (GET `/api/v1/reports/download/{job_id}/{ticker}`):
```bash
curl "http://localhost:8000/api/v1/reports/download/{job_id}/AAPL" --output aapl_10k.pdf
```

**4. List Supported Companies** (GET `/api/v1/companies`):
```bash
curl "http://localhost:8000/api/v1/companies"
```

### Python API

You can also use the module programmatically:

```python
from src.sec10k_fetcher import fetch_10k_reports

# Fetch reports for specific companies
results = fetch_10k_reports(
    tickers=["AAPL", "META", "GOOGL"],
    output_dir="./pdfs"
)

# Process results
for result in results:
    print(f"{result['ticker']}: {result['pdf_path']}")
    print(f"  Filing Date: {result['filing_date']}")
    print(f"  Accession: {result['accession_number']}")
```

## Output

The tool creates PDF files in the specified output directory with the following naming convention:

```
{ticker}_{accession_number}_{filing_date}.pdf
```

Example: `AAPL_0000320193-23-000077_2023-11-03.pdf`

- PDFs are saved in the `output_dir` directory
- Temporary files are automatically cleaned up
- A log file (`sec_10k_fetcher.log`) is created in the current directory

## Testing

### Run Unit Tests:
```bash
pytest tests/ -v
```

### Run Integration Tests (requires network access):
```bash
pytest tests/ -v -m integration
```

### Run All Tests:
```bash
pytest tests/ -v
```

Note: Integration tests are marked with `@pytest.mark.integration` and may take longer as they hit the actual SEC API.

## Project Structure

```
assignment/
├── src/                 # Core implementation and API service
├── scripts/             # CLI scripts to fetch reports
├── tests/               # Unit and integration tests
├── requirements.txt     # Python dependencies
├── README.md            # This file
├── output_pdfs/         # Generated PDFs
└── sec_10k_fetcher.log  # Application logs

```

## SEC API Integration & Compliance

This service uses official SEC EDGAR API endpoints, includes a descriptive User-Agent header, and applies conservative rate limiting (100ms between requests).  
See `docs/SEC_COMPLIANCE_VERIFICATION.md` for detailed verification.


## SEC API Documentation

For more information about the SEC EDGAR API:

- [EDGAR Application Programming Interfaces](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
