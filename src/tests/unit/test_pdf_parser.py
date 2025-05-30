"""Unit tests for PDF parser functionality."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from bjhjyd_mcp.parsers.pdf_parser import PDFParser, PDFFormatDetector
from bjhjyd_mcp.models.quota_result import QuotaType


class TestPDFFormatDetector:
    """Test PDF format detection."""
    
    def test_detect_score_ranking_format(self):
        """Test detection of score ranking format."""
        sample_text = """
        序号 主申请人申请编码 主申请人姓名 主申请人证件号码 家庭代际数 家庭总积分 成员最早注册时间
        1 1437100439239 孟红伟 110228********1240 3 300 2011-02-24 20:35:11.000
        """
        
        detector = PDFFormatDetector()
        result = detector.detect_format(sample_text)
        
        assert result == QuotaType.SCORE_RANKING
    
    def test_detect_waiting_list_format(self):
        """Test detection of waiting list format."""
        sample_text = """
        序号 申请编码 轮候时间
        1 87861015821462018-01-07 14:56:11.401
        2 9520106831497 2018-01-14 03:54:54.765
        """
        
        detector = PDFFormatDetector()
        result = detector.detect_format(sample_text)
        
        assert result == QuotaType.WAITING_LIST
    
    def test_detect_unknown_format(self):
        """Test detection of unknown format."""
        sample_text = "This is some random text without quota indicators"
        
        detector = PDFFormatDetector()
        result = detector.detect_format(sample_text)
        
        assert result == QuotaType.UNKNOWN


class TestPDFParser:
    """Test PDF parser functionality."""
    
    @pytest.fixture
    def parser(self):
        """Create a PDF parser instance."""
        return PDFParser()
    
    def test_waiting_list_pattern_matching(self, parser):
        """Test waiting list regex pattern."""
        test_line = "1 87861015821462018-01-07 14:56:11.401"
        
        match = parser.waiting_list_pattern.match(test_line)
        
        assert match is not None
        assert match.group(1) == "1"  # sequence number
        assert match.group(2) == "8786101582146"  # application code
        assert match.group(3) == "2018-01-07 14:56:11.401"  # waiting time
    
    def test_score_ranking_pattern_matching(self, parser):
        """Test score ranking regex pattern."""
        test_line = "1 1437100439239 孟红伟 110228********1240 3 300 2011-02-24 20:35:11.000"
        
        match = parser.score_ranking_pattern.match(test_line)
        
        assert match is not None
        assert match.group(1) == "1"  # sequence number
        assert match.group(2) == "1437100439239"  # application code
        assert match.group(3) == "孟红伟"  # name
        assert match.group(4) == "110228********1240"  # ID number
        assert match.group(5) == "3"  # family generation count
        assert match.group(6) == "300"  # total family score
        assert match.group(7) == "2011-02-24 20:35:11.000"  # registration time
    
    def test_parse_waiting_list_entries(self, parser):
        """Test parsing waiting list entries."""
        raw_entries = [
            "1 8786101582146 2018-01-07 14:56:11.401",
            "2 9520106831497 2018-01-14 03:54:54.765"
        ]
        
        entries = parser._parse_waiting_list_entries(raw_entries)
        
        assert len(entries) == 2
        
        # Check first entry
        assert entries[0].sequence_number == 1
        assert entries[0].application_code == "8786101582146"
        assert entries[0].waiting_time == datetime(2018, 1, 7, 14, 56, 11, 401000)
        
        # Check second entry
        assert entries[1].sequence_number == 2
        assert entries[1].application_code == "9520106831497"
        assert entries[1].waiting_time == datetime(2018, 1, 14, 3, 54, 54, 765000)
    
    def test_parse_score_ranking_entries(self, parser):
        """Test parsing score ranking entries."""
        raw_entries = [
            "1 1437100439239 孟红伟 110228********1240 3 300 2011-02-24 20:35:11.000",
            "2 6213100377766 王宏伟 110221********0017 3 297 2011-02-10 20:50:31.000"
        ]
        
        entries = parser._parse_score_ranking_entries(raw_entries)
        
        assert len(entries) == 2
        
        # Check first entry
        assert entries[0].sequence_number == 1
        assert entries[0].application_code == "1437100439239"
        assert entries[0].applicant_name == "孟红伟"
        assert entries[0].id_number == "110228********1240"
        assert entries[0].family_generation_count == 3
        assert entries[0].total_family_score == 300
        assert entries[0].earliest_registration_time == datetime(2011, 2, 24, 20, 35, 11)
        
        # Check second entry
        assert entries[1].sequence_number == 2
        assert entries[1].application_code == "6213100377766"
        assert entries[1].applicant_name == "王宏伟"
    
    def test_extract_entries_from_page(self, parser):
        """Test extracting entries from page text."""
        page_text = """
        序号 申请编码 轮候时间
        1 8786101582146 2018-01-07 14:56:11.401
        2 9520106831497 2018-01-14 03:54:54.765
        页码: 1/100
        """
        
        entries = parser._extract_entries_from_page(page_text, QuotaType.WAITING_LIST)
        
        assert len(entries) == 2
        assert "1 8786101582146 2018-01-07 14:56:11.401" in entries
        assert "2 9520106831497 2018-01-14 03:54:54.765" in entries
    
    @patch('bjhjyd_mcp.parsers.pdf_parser.pdfplumber')
    def test_parse_pdf_file_not_found(self, mock_pdfplumber, parser):
        """Test parsing non-existent PDF file."""
        mock_pdfplumber.open.side_effect = FileNotFoundError("File not found")
        
        with pytest.raises(FileNotFoundError):
            parser.parse_pdf(Path("nonexistent.pdf"))
    
    def test_validation_report_no_entries(self, parser):
        """Test validation report for result with no entries."""
        from bjhjyd_mcp.models.quota_result import QuotaResult, PDFMetadata
        
        metadata = PDFMetadata(
            filename="test.pdf",
            source_url="http://example.com",
            download_time=datetime.now(),
            file_size=1000,
            page_count=1,
            entry_count=0,
            quota_type=QuotaType.WAITING_LIST
        )
        
        result = QuotaResult(metadata=metadata)
        
        report = parser.validate_parsed_data(result)
        
        assert report["is_valid"] is False
        assert "No valid entries found in PDF" in report["errors"] 