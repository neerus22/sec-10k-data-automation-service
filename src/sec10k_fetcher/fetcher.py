"""
SEC 10-K Report Fetcher and PDF Converter

This module provides functionality to fetch the latest 10-K reports from the SEC EDGAR
database for specified companies and convert them to PDF format.

The implementation follows SEC API guidelines:
- Uses proper User-Agent headers
- Respects rate limiting
- Handles errors gracefully
- Supports both HTML and TXT filing formats

"""

import os
import json
import time
import logging
import re
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from weasyprint import HTML

from .config import (
    SEC_SUBMISSIONS_TEMPLATE,
    SEC_ARCHIVE_BASE,
    SEC_USER_AGENT,
    SEC_REQUEST_DELAY,
    TICKER_TO_CIK,
)


# Configure logging
logger = logging.getLogger(__name__)


class SECAPIError(Exception):
    """Custom exception for SEC API-related errors."""
    pass


class PDFConversionError(Exception):
    """Custom exception for PDF conversion errors."""
    pass


class SEC10KFetcher:
    """
    Fetches 10-K reports from SEC EDGAR database and converts them to PDF.
    
    This class handles:
    - Retrieving company submission metadata
    - Finding the latest 10-K filing
    - Downloading the filing document
    - Converting HTML/TXT to PDF format
    """
    
    def __init__(self, user_agent: str = SEC_USER_AGENT, request_delay: float = SEC_REQUEST_DELAY):
        """
        Initialize the SEC 10-K fetcher.
        
        Args:
            user_agent: User-Agent string for SEC API requests (required by SEC)
            request_delay: Delay in seconds between API requests to respect rate limits
        """
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov"
        })
        self.request_delay = request_delay
        logger.info("SEC10KFetcher initialized")
    
    def _make_request(self, url: str, headers: Optional[Dict] = None) -> requests.Response:
        """
        Make an HTTP request with proper headers and rate limiting.
        
        Args:
            url: URL to request
            headers: Optional additional headers
            
        Returns:
            Response object
            
        Raises:
            SECAPIError: If the request fails
        """
        request_headers = self.session.headers.copy()
        if headers:
            request_headers.update(headers)
        
        try:
            time.sleep(self.request_delay)  # Rate limiting
            response = self.session.get(url, headers=request_headers, timeout=30)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for URL {url}: {e}")
            raise SECAPIError(f"Failed to fetch data from SEC API: {e}") from e
    
    def get_company_submissions(self, cik: str) -> Dict:
        """
        Fetch company submission metadata from SEC API.
        
        Args:
            cik: Company Central Index Key (10-digit zero-padded string)
            
        Returns:
            Dictionary containing company submission metadata
            
        Raises:
            SECAPIError: If the API request fails
        """
        url = SEC_SUBMISSIONS_TEMPLATE.format(cik=cik)
        logger.debug(f"Fetching submissions for CIK {cik}")
        
        try:
            response = self._make_request(url)
            data = response.json()
            logger.info(f"Successfully fetched submissions for CIK {cik}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response for CIK {cik}: {e}")
            raise SECAPIError(f"Invalid JSON response from SEC API: {e}") from e
    
    def find_latest_10k(self, submissions: Dict) -> Optional[Dict]:
        """
        Find the latest 10-K filing from company submissions.
        
        Filters out amendments (10-K/A) to get the most recent original 10-K.
        
        Args:
            submissions: Company submission metadata dictionary
            
        Returns:
            Dictionary with filing metadata (formType, accessionNumber, filingDate, 
            primaryDocument) or None if no 10-K is found
        """
        filings = submissions.get("filings", {}).get("recent", {})
        form_types = filings.get("form", [])
        accession_numbers = filings.get("accessionNumber", [])
        filing_dates = filings.get("filingDate", [])
        primary_documents = filings.get("primaryDocument", [])
        
        if not all([form_types, accession_numbers, filing_dates, primary_documents]):
            logger.warning("Incomplete filing data in submissions")
            return None
        
        latest_10k = None
        latest_date = None
        
        # Iterate through filings to find the latest 10-K (excluding amendments)
        for i, form_type in enumerate(form_types):
            if form_type == "10-K":  # Exclude 10-K/A amendments
                filing_date = filing_dates[i]
                accession_number = accession_numbers[i]
                primary_document = primary_documents[i]
                
                # Parse date for comparison
                try:
                    date_obj = datetime.strptime(filing_date, "%Y-%m-%d")
                    if latest_date is None or date_obj > latest_date:
                        latest_date = date_obj
                        latest_10k = {
                            "formType": form_type,
                            "accessionNumber": accession_number,
                            "filingDate": filing_date,
                            "primaryDocument": primary_document
                        }
                except ValueError as e:
                    logger.warning(f"Invalid date format {filing_date}: {e}")
                    continue
        
        if latest_10k:
            logger.info(
                f"Found latest 10-K: {latest_10k['filingDate']}, "
                f"accession {latest_10k['accessionNumber']}"
            )
        else:
            logger.warning("No 10-K filing found")
        
        return latest_10k
    
    def _download_image(self, image_url: str, output_dir: Path, base_url: str) -> Optional[str]:
        """
        Download a single image referenced in an HTML filing.
        
        Args:
            image_url: URL or relative path to the image
            output_dir: Directory to save the image
            base_url: Base URL for resolving relative paths
            
        Returns:
            Local filename if successful, None otherwise
        """
        try:
            # Resolve relative URLs
            if not image_url.startswith("http"):
                image_url = urljoin(base_url, image_url)
            
            # Extract filename
            image_filename = os.path.basename(urlparse(image_url).path)
            if not image_filename:
                return None
            
            local_image_path = output_dir / image_filename
            
            # Skip if already downloaded
            if local_image_path.exists():
                return image_filename
            
            archive_headers = {
                "Host": "www.sec.gov",
                "Referer": "https://www.sec.gov/"
            }
            response = self._make_request(image_url, headers=archive_headers)
            
            with open(local_image_path, "wb") as f:
                f.write(response.content)
            
            logger.debug(f"Downloaded image: {image_filename}")
            return image_filename
            
        except Exception as e:
            logger.warning(f"Failed to download image {image_url}: {e}")
            return None
    
    def _download_html_images(self, html_file: Path, cik: str, accession_number: str) -> Set[str]:
        """
        Download all images referenced in an HTML filing.
        
        Args:
            html_file: Path to the HTML file
            cik: Company Central Index Key
            accession_number: Filing accession number
            
        Returns:
            Set of downloaded image filenames
        """
        if html_file.suffix.lower() != ".html" and html_file.suffix.lower() != ".htm":
            return set()
        
        try:
            with open(html_file, "r", encoding="utf-8", errors="ignore") as f:
                html_content = f.read()
            
            # Extract image references (img src and CSS background-image)
            # Match common patterns: src="filename.jpg", src='filename.jpg', src=filename.jpg
            image_patterns = [
                r'src=["\']([^"\']*\.(jpg|jpeg|png|gif|svg))["\']',
                r'background-image:\s*url\(["\']?([^"\']*\.(jpg|jpeg|png|gif|svg))["\']?\)',
            ]
            
            accession_no_hyphens = accession_number.replace("-", "")
            base_url = f"{SEC_ARCHIVE_BASE}/{int(cik)}/{accession_no_hyphens}/"
            output_dir = html_file.parent
            
            downloaded_images = set()
            
            for pattern in image_patterns:
                matches = re.finditer(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    image_path = match.group(1)
                    # Only download images in the same directory (not external URLs)
                    if not image_path.startswith("http") and not image_path.startswith("//"):
                        local_filename = self._download_image(image_path, output_dir, base_url)
                        if local_filename:
                            downloaded_images.add(local_filename)
            
            if downloaded_images:
                logger.info(f"Downloaded {len(downloaded_images)} images for HTML filing")
            else:
                logger.debug("No images found to download")
            
            return downloaded_images
            
        except Exception as e:
            logger.warning(f"Failed to extract/download images from HTML: {e}")
            return set()
    
    def download_filing(self, cik: str, accession_number: str, document_name: str, 
                       output_dir: Path) -> Path:
        """
        Download a filing document from SEC archives.
        Also downloads referenced images if the filing is HTML.
        
        Args:
            cik: Company Central Index Key (10-digit zero-padded)
            accession_number: Filing accession number (format: 0000000000-00-000000)
            document_name: Name of the primary document file
            output_dir: Directory to save the downloaded file
            
        Returns:
            Path to the downloaded file
            
        Raises:
            SECAPIError: If the download fails
        """
        # Normalize accession number (remove hyphens)
        accession_no_hyphens = accession_number.replace("-", "")
        
        # Construct URL
        url = f"{SEC_ARCHIVE_BASE}/{int(cik)}/{accession_no_hyphens}/{document_name}"
        logger.debug(f"Downloading filing from {url}")
        
        try:
            # Update headers for archive request
            archive_headers = {
                "Host": "www.sec.gov",
                "Referer": "https://www.sec.gov/"
            }
            response = self._make_request(url, headers=archive_headers)
            
            # Save file
            output_dir.mkdir(parents=True, exist_ok=True)
            local_file = output_dir / document_name
            
            with open(local_file, "wb") as f:
                f.write(response.content)
            
            logger.info(f"Downloaded filing to {local_file}")
            
            # Download referenced images if HTML file
            if local_file.suffix.lower() in [".html", ".htm"]:
                self._download_html_images(local_file, cik, accession_number)
            
            return local_file
            
        except Exception as e:
            logger.error(f"Failed to download filing: {e}")
            raise SECAPIError(f"Failed to download filing document: {e}") from e
    
    def convert_to_pdf(self, input_file: Path, output_file: Path) -> Path:
        """
        Convert HTML or TXT filing to PDF format.
        
        Args:
            input_file: Path to input HTML/TXT file
            output_file: Path for output PDF file
            
        Returns:
            Path to the created PDF file
            
        Raises:
            PDFConversionError: If the conversion fails
        """
        logger.debug(f"Converting {input_file} to PDF: {output_file}")
        
        try:
            # WeasyPrint can handle HTML files
            # For TXT files, we'll wrap them in basic HTML
            if input_file.suffix.lower() == ".txt":
                # Convert TXT to HTML by wrapping in pre tags
                with open(input_file, "r", encoding="utf-8", errors="ignore") as f:
                    txt_content = f.read()
                
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <style>
                        pre {{ 
                            font-family: 'Courier New', monospace; 
                            font-size: 10pt;
                            white-space: pre-wrap;
                            word-wrap: break-word;
                        }}
                        body {{ margin: 20px; }}
                    </style>
                </head>
                <body>
                    <pre>{txt_content}</pre>
                </body>
                </html>
                """
                
                # Write temporary HTML file
                temp_html = input_file.with_suffix(".html")
                with open(temp_html, "w", encoding="utf-8") as f:
                    f.write(html_content)
                
                HTML(filename=str(temp_html)).write_pdf(str(output_file))
                temp_html.unlink()  # Clean up temporary HTML file
            else:
                # Direct HTML to PDF conversion
                HTML(filename=str(input_file)).write_pdf(str(output_file))
            
            logger.info(f"Successfully converted to PDF: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
            raise PDFConversionError(f"Failed to convert file to PDF: {e}") from e
    
    def process_company(self, ticker: str, cik: str, output_dir: Path) -> Optional[Dict]:
        """
        Complete workflow: fetch latest 10-K for a company and convert to PDF.
        
        Args:
            ticker: Company stock ticker symbol
            cik: Company Central Index Key
            output_dir: Directory to save PDF files
            
        Returns:
            Dictionary with processing results (ticker, cik, filing_date, pdf_path)
            or None if processing fails
        """
        logger.info(f"Processing {ticker} (CIK: {cik})")
        
        try:
            # Step 1: Get company submissions
            submissions = self.get_company_submissions(cik)
            
            # Step 2: Find latest 10-K
            latest_10k = self.find_latest_10k(submissions)
            if not latest_10k:
                logger.warning(f"No 10-K found for {ticker}")
                return None
            
            # Step 3: Download filing
            temp_dir = output_dir / "temp"
            downloaded_file = self.download_filing(
                cik=cik,
                accession_number=latest_10k["accessionNumber"],
                document_name=latest_10k["primaryDocument"],
                output_dir=temp_dir
            )
            
            # Step 4: Convert to PDF
            pdf_filename = f"{ticker}_{latest_10k['accessionNumber']}_{latest_10k['filingDate']}.pdf"
            pdf_path = output_dir / pdf_filename
            
            self.convert_to_pdf(downloaded_file, pdf_path)
            
            # Clean up downloaded file (if it exists)
            if downloaded_file.exists():
                downloaded_file.unlink()
            
            result = {
                "ticker": ticker,
                "cik": cik,
                "filing_date": latest_10k["filingDate"],
                "accession_number": latest_10k["accessionNumber"],
                "pdf_path": str(pdf_path)
            }
            
            logger.info(f"Successfully processed {ticker}: {result['pdf_path']}")
            return result
            
        except (SECAPIError, PDFConversionError) as e:
            logger.error(f"Failed to process {ticker}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error processing {ticker}: {e}")
            return None


def fetch_10k_reports(
    tickers: List[str],
    output_dir: str = "./output_pdfs",
    cik_map: Optional[Dict[str, str]] = None
) -> List[Dict]:
    """
    Fetch latest 10-K reports for a list of company tickers.
    
    Args:
        tickers: List of company stock ticker symbols
        output_dir: Directory to save PDF files
        cik_map: Optional dictionary mapping tickers to CIKs (defaults to built-in map)
        
    Returns:
        List of dictionaries containing processing results for each company
    """
    if cik_map is None:
        cik_map = TICKER_TO_CIK
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    fetcher = SEC10KFetcher()
    results = []
    
    for ticker in tickers:
        ticker_upper = ticker.upper()
        cik = cik_map.get(ticker_upper)
        
        if not cik:
            logger.warning(f"No CIK mapping found for ticker {ticker_upper}, skipping")
            continue
        
        result = fetcher.process_company(ticker_upper, cik, output_path)
        if result:
            results.append(result)
    
    logger.info(f"Processing complete. {len(results)}/{len(tickers)} companies processed successfully")
    return results
