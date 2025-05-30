"""
PDF parser for Beijing car quota lottery results.

Handles two main formats:
1. Waiting List (轮候序号列表) - Format: 序号 申请编码 轮候时间
2. Score Ranking (积分排序入围名单) - Format: 序号 申请编码 姓名 身份证号 家庭代际数 积分 注册时间
"""

import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import pdfplumber
from ..models.quota_result import (
    QuotaResult, QuotaType, WaitingListEntry, ScoreRankingEntry, PDFMetadata
)

logger = logging.getLogger(__name__)


class PDFFormatDetector:
    """Detects the format of Beijing car quota lottery PDF files."""
    
    @staticmethod
    def detect_format(text_sample: str) -> QuotaType:
        """
        Detect PDF format based on text content.
        
        Args:
            text_sample: Sample text from the PDF (first few pages)
            
        Returns:
            QuotaType indicating the detected format
        """
        # Check for score ranking indicators
        score_indicators = [
            "主申请人姓名", "主申请人证件号码", "家庭总积分", "家庭代际数"
        ]
        
        # Check for waiting list indicators  
        waiting_indicators = [
            "轮候时间", "申请编码"
        ]
        
        # Count indicators
        score_count = sum(1 for indicator in score_indicators if indicator in text_sample)
        waiting_count = sum(1 for indicator in waiting_indicators if indicator in text_sample)
        
        if score_count >= 2:
            return QuotaType.SCORE_RANKING
        elif waiting_count >= 1 and "积分" not in text_sample:
            return QuotaType.WAITING_LIST
        else:
            return QuotaType.UNKNOWN


class PDFParser:
    """Parser for Beijing car quota lottery PDF files."""
    
    def __init__(self):
        self.format_detector = PDFFormatDetector()
        
        # Regex patterns for different formats
        self.waiting_list_pattern = re.compile(
            r'^(\d+)\s+(\d+)\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})$'
        )
        
        # More flexible pattern for score ranking due to variable name lengths
        self.score_ranking_pattern = re.compile(
            r'^(\d+)\s+(\d+)\s+([^\d\s]+?)\s+(\d{6}\*+\d{4})\s+(\d+)\s+(\d+)\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})$'
        )
    
    def parse_pdf(self, pdf_path: Path, source_url: str = "") -> QuotaResult:
        """
        Parse a PDF file and extract quota lottery results.
        
        Args:
            pdf_path: Path to the PDF file
            source_url: URL where the PDF was downloaded from
            
        Returns:
            QuotaResult containing parsed data
        """
        logger.info(f"Parsing PDF: {pdf_path}")
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Extract metadata
                file_size = pdf_path.stat().st_size
                page_count = len(pdf.pages)
                
                # Get sample text for format detection
                sample_text = ""
                for i, page in enumerate(pdf.pages[:3]):  # First 3 pages
                    sample_text += page.extract_text() or ""
                    if len(sample_text) > 2000:  # Enough for detection
                        break
                
                # Detect format
                quota_type = self.format_detector.detect_format(sample_text)
                logger.info(f"Detected format: {quota_type}")
                
                # Extract all text
                all_entries = []
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        entries = self._extract_entries_from_page(page_text, quota_type)
                        all_entries.extend(entries)
                        
                        if page_num % 50 == 0:  # Log progress every 50 pages
                            logger.info(f"Processed {page_num + 1}/{page_count} pages")
                
                # Create metadata
                metadata = PDFMetadata(
                    filename=pdf_path.name,
                    source_url=source_url,
                    download_time=datetime.fromtimestamp(pdf_path.stat().st_mtime),
                    file_size=file_size,
                    page_count=page_count,
                    entry_count=len(all_entries),
                    quota_type=quota_type,
                    processing_time=datetime.now()
                )
                
                # Create result object
                result = QuotaResult(metadata=metadata)
                
                # Parse entries based on format
                if quota_type == QuotaType.WAITING_LIST:
                    result.waiting_list_entries = self._parse_waiting_list_entries(all_entries)
                elif quota_type == QuotaType.SCORE_RANKING:
                    result.score_ranking_entries = self._parse_score_ranking_entries(all_entries)
                
                # Build indexes for fast lookup
                result.build_indexes()
                
                logger.info(f"Successfully parsed {len(all_entries)} entries from {pdf_path}")
                return result
                
        except Exception as e:
            logger.error(f"Error parsing PDF {pdf_path}: {e}")
            raise
    
    def _extract_entries_from_page(self, page_text: str, quota_type: QuotaType) -> List[str]:
        """Extract data entries from a page of text."""
        lines = page_text.split('\n')
        entries = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip headers and non-data lines
            if any(header in line for header in [
                "序号", "申请编码", "轮候时间", "主申请人", "积分", "页码", "共", "页"
            ]):
                continue
            
            # Check if line matches expected data pattern
            if quota_type == QuotaType.WAITING_LIST:
                if self.waiting_list_pattern.match(line):
                    entries.append(line)
            elif quota_type == QuotaType.SCORE_RANKING:
                if self.score_ranking_pattern.match(line):
                    entries.append(line)
            else:
                # For unknown format, try both patterns
                if self.waiting_list_pattern.match(line) or self.score_ranking_pattern.match(line):
                    entries.append(line)
        
        return entries
    
    def _parse_waiting_list_entries(self, raw_entries: List[str]) -> List[WaitingListEntry]:
        """Parse waiting list entries."""
        entries = []
        
        for raw_entry in raw_entries:
            match = self.waiting_list_pattern.match(raw_entry)
            if match:
                try:
                    sequence_number = int(match.group(1))
                    application_code = match.group(2)
                    waiting_time = datetime.strptime(match.group(3), "%Y-%m-%d %H:%M:%S.%f")
                    
                    entry = WaitingListEntry(
                        sequence_number=sequence_number,
                        application_code=application_code,
                        waiting_time=waiting_time
                    )
                    entries.append(entry)
                    
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse waiting list entry: {raw_entry}, error: {e}")
        
        return entries
    
    def _parse_score_ranking_entries(self, raw_entries: List[str]) -> List[ScoreRankingEntry]:
        """Parse score ranking entries."""
        entries = []
        
        for raw_entry in raw_entries:
            match = self.score_ranking_pattern.match(raw_entry)
            if match:
                try:
                    sequence_number = int(match.group(1))
                    application_code = match.group(2)
                    applicant_name = match.group(3).strip()
                    id_number = match.group(4)
                    family_generation_count = int(match.group(5))
                    total_family_score = int(match.group(6))
                    earliest_registration_time = datetime.strptime(match.group(7), "%Y-%m-%d %H:%M:%S.%f")
                    
                    entry = ScoreRankingEntry(
                        sequence_number=sequence_number,
                        application_code=application_code,
                        applicant_name=applicant_name,
                        id_number=id_number,
                        family_generation_count=family_generation_count,
                        total_family_score=total_family_score,
                        earliest_registration_time=earliest_registration_time
                    )
                    entries.append(entry)
                    
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse score ranking entry: {raw_entry}, error: {e}")
        
        return entries
    
    def validate_parsed_data(self, result: QuotaResult) -> Dict[str, Any]:
        """Validate parsed data and return validation report."""
        report = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "statistics": result.get_statistics()
        }
        
        # Check if we have any entries
        total_entries = len(result.waiting_list_entries) + len(result.score_ranking_entries)
        if total_entries == 0:
            report["is_valid"] = False
            report["errors"].append("No valid entries found in PDF")
        
        # Check sequence number continuity
        if result.metadata.quota_type == QuotaType.WAITING_LIST:
            sequence_numbers = [entry.sequence_number for entry in result.waiting_list_entries]
        elif result.metadata.quota_type == QuotaType.SCORE_RANKING:
            sequence_numbers = [entry.sequence_number for entry in result.score_ranking_entries]
        else:
            sequence_numbers = []
        
        if sequence_numbers:
            expected_sequence = list(range(1, len(sequence_numbers) + 1))
            if sequence_numbers != expected_sequence:
                report["warnings"].append("Sequence numbers are not continuous")
        
        # Check for duplicate application codes
        if result.metadata.quota_type == QuotaType.WAITING_LIST:
            app_codes = [entry.application_code for entry in result.waiting_list_entries]
        elif result.metadata.quota_type == QuotaType.SCORE_RANKING:
            app_codes = [entry.application_code for entry in result.score_ranking_entries]
        else:
            app_codes = []
        
        if len(app_codes) != len(set(app_codes)):
            report["warnings"].append("Duplicate application codes found")
        
        return report 