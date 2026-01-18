"""
Configuration constants for SEC 10-K Fetcher

Contains SEC API endpoints, rate limiting settings, and company mappings.
"""

# SEC API Configuration
SEC_SUBMISSIONS_TEMPLATE = "https://data.sec.gov/submissions/CIK{cik:0>10s}.json"
SEC_ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data"
SEC_USER_AGENT = "Quartr Data Automation Team contact@quartr.com"

# Rate limiting: SEC recommends no more than 10 requests per second
SEC_REQUEST_DELAY = 0.1  # 100ms between requests

# Company ticker to CIK mapping
# CIKs (Central Index Keys) are required to fetch SEC filings
TICKER_TO_CIK = {
    "AAPL": "0000320193",  # Apple Inc.
    "META": "0001326801",  # Meta Platforms Inc.
    "GOOGL": "0001652044",  # Alphabet Inc. (Class A)
    "AMZN": "0001018724",  # Amazon.com Inc.
    "NFLX": "0001065280",  # Netflix Inc.
    "GS": "0000886982",  # Goldman Sachs Group Inc.
}
