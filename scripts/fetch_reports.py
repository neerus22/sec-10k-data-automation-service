"""
Command-line script for fetching SEC 10-K reports

Provides a CLI interface for the SEC 10-K fetcher.
Can be run directly or as a module entry point.
"""

import sys
import argparse
import logging
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sec10k_fetcher import fetch_10k_reports, SECAPIError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("sec_10k_fetcher.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch latest 10-K reports from SEC EDGAR and convert to PDF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch reports for specific companies
  python scripts/fetch_reports.py --tickers AAPL,META,GOOGL --output_dir ./pdfs
  
  # Use default companies from assignment
  python scripts/fetch_reports.py
        """
    )
    
    parser.add_argument(
        "--tickers",
        type=str,
        default="AAPL,META,GOOGL,AMZN,NFLX,GS",
        help="Comma-separated list of stock ticker symbols (default: AAPL,META,GOOGL,AMZN,NFLX,GS)"
    )
    
    parser.add_argument(
        "--output_dir",
        type=str,
        default="./output_pdfs",
        help="Directory to save PDF files (default: ./output_pdfs)"
    )
    
    args = parser.parse_args()
    
    # Parse tickers
    ticker_list = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    
    if not ticker_list:
        logger.error("No valid tickers provided")
        sys.exit(1)
    
    success_count = 0
    failure_count = 0
    results = []

    # Fetch reports for each ticker individually to log errors per company
    for ticker in ticker_list:
        try:
            report = fetch_10k_reports([ticker], args.output_dir)
            if report:
                results.extend(report)
                logger.info(f"Successfully processed {ticker}: {report[0]['pdf_path']}")
                success_count += 1
            else:
                logger.warning(f"No report found for {ticker}")
                failure_count += 1
        except SECAPIError as e:
            logger.error(f"SEC API error for {ticker}: {e}")
            failure_count += 1
        except Exception as e:
            logger.error(f"Unexpected error for {ticker}: {e}")
            failure_count += 1

    # Print summary
    print("\n" + "="*60)
    print("Processing Summary")
    print("="*60)

    for result in results:
        print(f"✓ {result['ticker']}: {result['pdf_path']}")

    if failure_count > 0:
        print(f"\n⚠ {failure_count} ticker(s) failed to process")
    
    print(f"\n✅ {success_count} ticker(s) successfully processed")

    # Exit code: 0 if at least one success, 1 if all failed
    sys.exit(0 if success_count > 0 else 1)


if __name__ == "__main__":
    main()
