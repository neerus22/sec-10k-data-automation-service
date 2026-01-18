"""
SEC 10-K Fetcher Module

Core functionality for fetching SEC 10-K reports and converting to PDF.
"""

from .fetcher import SEC10KFetcher, SECAPIError, PDFConversionError, fetch_10k_reports
from .config import TICKER_TO_CIK, SEC_USER_AGENT, SEC_REQUEST_DELAY

__all__ = [
    "SEC10KFetcher",
    "SECAPIError",
    "PDFConversionError",
    "fetch_10k_reports",
    "TICKER_TO_CIK",
    "SEC_USER_AGENT",
    "SEC_REQUEST_DELAY",
]
