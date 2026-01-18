"""
Integration tests for SEC 10-K Fetcher

These tests require network access and may take longer to run.
They test the actual integration with SEC API.

Note: These tests are marked with @pytest.mark.integration and
can be skipped with: pytest -m "not integration"
"""

import pytest
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.sec10k_fetcher import SEC10KFetcher, TICKER_TO_CIK


@pytest.mark.integration
class TestSECAPIIntegration:
    """Integration tests that require actual SEC API access."""
    
    @pytest.fixture
    def fetcher(self):
        """Create a SEC10KFetcher instance for integration testing."""
        return SEC10KFetcher()
    
    @pytest.fixture
    def temp_output_dir(self, tmp_path):
        """Create temporary output directory."""
        return tmp_path / "output"
    
    def test_fetch_apple_submissions(self, fetcher):
        """Test fetching real submissions for Apple."""
        cik = TICKER_TO_CIK["AAPL"]
        submissions = fetcher.get_company_submissions(cik)
        
        assert submissions is not None
        assert "cik" in submissions
        # SEC API may return CIK with or without leading zeros
        assert submissions["cik"] in ["320193", "0000320193"]
        assert "filings" in submissions
    
    def test_find_apple_latest_10k(self, fetcher):
        """Test finding latest 10-K for Apple."""
        cik = TICKER_TO_CIK["AAPL"]
        submissions = fetcher.get_company_submissions(cik)
        latest_10k = fetcher.find_latest_10k(submissions)
        
        assert latest_10k is not None
        assert latest_10k["formType"] == "10-K"
        assert "filingDate" in latest_10k
        assert "accessionNumber" in latest_10k
        assert "primaryDocument" in latest_10k
    
    @pytest.mark.slow
    def test_download_filing(self, fetcher, temp_output_dir):
        """Test downloading an actual filing."""
        cik = TICKER_TO_CIK["AAPL"]
        submissions = fetcher.get_company_submissions(cik)
        latest_10k = fetcher.find_latest_10k(submissions)
        
        if latest_10k:
            downloaded_file = fetcher.download_filing(
                cik=cik,
                accession_number=latest_10k["accessionNumber"],
                document_name=latest_10k["primaryDocument"],
                output_dir=temp_output_dir
            )
            
            assert downloaded_file.exists()
            assert downloaded_file.stat().st_size > 0
    
    @pytest.mark.slow
    @pytest.mark.skip(reason="Requires WeasyPrint and may be slow")
    def test_full_pipeline_single_company(self, fetcher, temp_output_dir):
        """Test the complete pipeline for a single company."""
        result = fetcher.process_company(
            ticker="AAPL",
            cik=TICKER_TO_CIK["AAPL"],
            output_dir=temp_output_dir
        )
        
        if result:
            assert result["ticker"] == "AAPL"
            assert result["cik"] == TICKER_TO_CIK["AAPL"]
            assert Path(result["pdf_path"]).exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
