"""
Beijing Car Quota Lottery Results MCP Server

This package provides an MCP server for querying Beijing car quota lottery results.
It scrapes data from the Beijing Transportation Commission website and provides
tools to search for quota codes and ID numbers in the lottery results.
"""

__version__ = "0.1.0"
__author__ = "Developer"
__email__ = "dev@example.com"

from .server.mcp_server import MCPServer
from .models.quota_result import QuotaResult, QuotaType
from .parsers.pdf_parser import PDFParser
from .scrapers.web_scraper import WebScraper

__all__ = [
    "MCPServer",
    "QuotaResult", 
    "QuotaType",
    "PDFParser",
    "WebScraper",
] 