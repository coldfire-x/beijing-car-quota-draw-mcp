"""
Data models for Beijing car quota lottery results.

Based on the PDF format analysis, there are two main types of data:
1. Waiting List (轮候序号列表) - Simple time-based ordering
2. Score Ranking (积分排序入围名单) - Complex score-based ranking with personal info
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class QuotaType(str, Enum):
    """Types of quota lottery results."""
    WAITING_LIST = "waiting_list"  # 轮候序号列表
    SCORE_RANKING = "score_ranking"  # 积分排序入围名单
    UNKNOWN = "unknown"


class WaitingListEntry(BaseModel):
    """Entry in a waiting list (轮候序号列表)."""
    sequence_number: int = Field(..., description="序号")
    application_code: str = Field(..., description="申请编码")
    waiting_time: datetime = Field(..., description="轮候时间")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ScoreRankingEntry(BaseModel):
    """Entry in a score ranking list (积分排序入围名单)."""
    sequence_number: int = Field(..., description="序号")
    application_code: str = Field(..., description="主申请人申请编码")
    applicant_name: str = Field(..., description="主申请人姓名")
    id_number: str = Field(..., description="主申请人证件号码 (masked)")
    family_generation_count: int = Field(..., description="家庭代际数")
    total_family_score: int = Field(..., description="家庭总积分")
    earliest_registration_time: datetime = Field(..., description="成员最早注册时间")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PDFMetadata(BaseModel):
    """Metadata for a processed PDF file."""
    filename: str = Field(..., description="PDF文件名")
    source_url: str = Field(..., description="来源网页URL")
    download_time: datetime = Field(..., description="下载时间")
    file_size: int = Field(..., description="文件大小(字节)")
    page_count: int = Field(..., description="页数")
    entry_count: int = Field(..., description="数据条目数")
    quota_type: QuotaType = Field(..., description="数据类型")
    processing_time: Optional[datetime] = Field(None, description="处理时间")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class QuotaResult(BaseModel):
    """Complete quota lottery result from a PDF file."""
    metadata: PDFMetadata = Field(..., description="PDF元数据")
    waiting_list_entries: List[WaitingListEntry] = Field(
        default_factory=list, description="轮候列表条目"
    )
    score_ranking_entries: List[ScoreRankingEntry] = Field(
        default_factory=list, description="积分排序条目"
    )
    
    # Indexes for fast lookup
    _application_code_index: Optional[Dict[str, int]] = None
    _id_number_index: Optional[Dict[str, int]] = None
    
    def build_indexes(self) -> None:
        """Build indexes for fast lookup."""
        self._application_code_index = {}
        self._id_number_index = {}
        
        # Index waiting list entries
        for i, entry in enumerate(self.waiting_list_entries):
            self._application_code_index[entry.application_code] = i
            
        # Index score ranking entries
        for i, entry in enumerate(self.score_ranking_entries):
            self._application_code_index[entry.application_code] = i
            # Only index non-masked parts of ID numbers for privacy
            if entry.id_number and len(entry.id_number) >= 10:
                # Extract first 6 and last 4 digits for partial matching
                id_prefix = entry.id_number[:6]
                id_suffix = entry.id_number[-4:]
                partial_id = f"{id_prefix}****{id_suffix}"
                self._id_number_index[partial_id] = i
    
    def find_by_application_code(self, application_code: str) -> Optional[Dict[str, Any]]:
        """Find entry by application code."""
        if not self._application_code_index:
            self.build_indexes()
            
        if application_code in self._application_code_index:
            index = self._application_code_index[application_code]
            
            if self.metadata.quota_type == QuotaType.WAITING_LIST:
                entry = self.waiting_list_entries[index]
                return {
                    "type": "waiting_list",
                    "sequence_number": entry.sequence_number,
                    "application_code": entry.application_code,
                    "waiting_time": entry.waiting_time,
                }
            elif self.metadata.quota_type == QuotaType.SCORE_RANKING:
                entry = self.score_ranking_entries[index]
                return {
                    "type": "score_ranking",
                    "sequence_number": entry.sequence_number,
                    "application_code": entry.application_code,
                    "applicant_name": entry.applicant_name,
                    "id_number": entry.id_number,
                    "family_generation_count": entry.family_generation_count,
                    "total_family_score": entry.total_family_score,
                    "earliest_registration_time": entry.earliest_registration_time,
                }
        
        return None
    
    def find_by_partial_id(self, id_prefix: str, id_suffix: str) -> List[Dict[str, Any]]:
        """Find entries by partial ID number (first 6 and last 4 digits)."""
        if not self._id_number_index:
            self.build_indexes()
            
        partial_id = f"{id_prefix}****{id_suffix}"
        results = []
        
        if partial_id in self._id_number_index:
            index = self._id_number_index[partial_id]
            entry = self.score_ranking_entries[index]
            results.append({
                "type": "score_ranking",
                "sequence_number": entry.sequence_number,
                "application_code": entry.application_code,
                "applicant_name": entry.applicant_name,
                "id_number": entry.id_number,
                "family_generation_count": entry.family_generation_count,
                "total_family_score": entry.total_family_score,
                "earliest_registration_time": entry.earliest_registration_time,
            })
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the quota result."""
        return {
            "quota_type": self.metadata.quota_type,
            "total_entries": self.metadata.entry_count,
            "waiting_list_count": len(self.waiting_list_entries),
            "score_ranking_count": len(self.score_ranking_entries),
            "file_info": {
                "filename": self.metadata.filename,
                "source_url": self.metadata.source_url,
                "download_time": self.metadata.download_time,
                "file_size": self.metadata.file_size,
                "page_count": self.metadata.page_count,
            }
        } 