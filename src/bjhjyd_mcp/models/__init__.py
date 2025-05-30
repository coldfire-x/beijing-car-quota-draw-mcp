"""Data models for the Beijing Car Quota Lottery MCP Server."""

from .quota_result import QuotaResult, QuotaType, WaitingListEntry, ScoreRankingEntry

__all__ = [
    "QuotaResult",
    "QuotaType", 
    "WaitingListEntry",
    "ScoreRankingEntry",
] 