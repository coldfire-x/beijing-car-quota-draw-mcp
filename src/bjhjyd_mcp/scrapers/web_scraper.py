"""
Web scraper for Beijing Transportation Commission car quota lottery results.

Uses crawl4ai to scrape https://xkczb.jtw.beijing.gov.cn/jggb/index.html
and download relevant PDF files.
"""

import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
import aiofiles
import httpx
from crawl4ai import AsyncWebCrawler

logger = logging.getLogger(__name__)


class WebScraper:
    """Scraper for Beijing Transportation Commission website."""
    
    def __init__(self, download_dir: Path = Path("downloads")):
        """
        Initialize the web scraper.
        
        Args:
            download_dir: Directory to save downloaded PDF files
        """
        self.base_url = "https://xkczb.jtw.beijing.gov.cn/jggb/index.html"
        self.download_dir = download_dir
        self.download_dir.mkdir(exist_ok=True)
        
        # Keywords to match for relevant links
        self.target_keywords = [
            "北京市家庭新能源小客车指标",
            "北京市单位新能源小客车指标", 
            "北京市个人新能源"
        ]
        
        # HTTP client for downloading files
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            verify=False,  # Disable SSL verification to avoid certificate issues
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
    
    async def scrape_and_download(self, max_pages: int = 5) -> List[Dict[str, str]]:
        """
        Scrape the website and download relevant PDF files.
        
        Args:
            max_pages: Maximum number of pages to scrape
            
        Returns:
            List of dictionaries containing PDF info: {filename, url, title}
        """
        logger.info(f"Starting scrape of {self.base_url}, max pages: {max_pages}")
        
        downloaded_files = []
        
        try:
            async with AsyncWebCrawler(verbose=True) as crawler:
                # Scrape each page
                for page_num in range(1, max_pages + 1):
                    page_url = self._get_page_url(page_num)
                    logger.info(f"Scraping page {page_num}: {page_url}")
                    
                    # Crawl the page
                    result = await crawler.arun(url=page_url)
                    
                    if result.success:
                        # Extract relevant links
                        relevant_links = self._extract_relevant_links(
                            result.html, page_url
                        )
                        
                        logger.info(f"Found {len(relevant_links)} relevant links on page {page_num}")
                        
                        # Process each relevant link
                        for link_info in relevant_links:
                            try:
                                pdf_files = await self._process_link(crawler, link_info)
                                downloaded_files.extend(pdf_files)
                            except Exception as e:
                                logger.error(f"Error processing link {link_info['url']}: {e}")
                    else:
                        logger.warning(f"Failed to scrape page {page_num}: {result.error_message}")
                    
                    # Add delay between pages
                    await asyncio.sleep(2)
        
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            raise
        
        logger.info(f"Scraping completed. Downloaded {len(downloaded_files)} PDF files")
        return downloaded_files
    
    def _get_page_url(self, page_num: int) -> str:
        """Get URL for a specific page number."""
        if page_num == 1:
            return self.base_url
        else:
            # Assuming pagination pattern - may need adjustment based on actual site
            return f"https://xkczb.jtw.beijing.gov.cn/jggb/index_{page_num}.html"
    
    def _extract_relevant_links(self, html_content: str, base_url: str) -> List[Dict[str, str]]:
        """
        Extract links that match target keywords.
        
        Args:
            html_content: HTML content of the page
            base_url: Base URL for resolving relative links
            
        Returns:
            List of relevant link information
        """
        relevant_links = []
        
        # Pattern to match links with titles
        link_pattern = re.compile(
            r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>',
            re.IGNORECASE | re.DOTALL
        )
        
        matches = link_pattern.findall(html_content)
        
        for href, title in matches:
            title = title.strip()
            
            # Check if title matches any target keywords
            if any(keyword in title for keyword in self.target_keywords):
                full_url = urljoin(base_url, href)
                relevant_links.append({
                    "url": full_url,
                    "title": title,
                    "href": href
                })
                logger.info(f"Found relevant link: {title} -> {full_url}")
        
        return relevant_links
    
    async def _process_link(self, crawler: AsyncWebCrawler, link_info: Dict[str, str]) -> List[Dict[str, str]]:
        """
        Process a relevant link and download any PDF files found.
        
        Args:
            crawler: AsyncWebCrawler instance
            link_info: Information about the link to process
            
        Returns:
            List of downloaded PDF file information
        """
        logger.info(f"Processing link: {link_info['title']}")
        
        # Crawl the target page
        result = await crawler.arun(url=link_info["url"])
        
        if not result.success:
            logger.warning(f"Failed to crawl {link_info['url']}: {result.error_message}")
            return []
        
        # Extract PDF links from the page
        pdf_links = self._extract_pdf_links(result.html, link_info["url"])
        
        downloaded_files = []
        
        # Download each PDF
        for pdf_url in pdf_links:
            try:
                filename = await self._download_pdf(pdf_url, link_info["url"])
                if filename:
                    downloaded_files.append({
                        "filename": filename,
                        "url": pdf_url,
                        "source_page": link_info["url"],
                        "title": link_info["title"]
                    })
            except Exception as e:
                logger.error(f"Error downloading PDF {pdf_url}: {e}")
        
        return downloaded_files
    
    def _extract_pdf_links(self, html_content: str, base_url: str) -> List[str]:
        """Extract PDF download links from HTML content."""
        pdf_links = []
        
        # Pattern to match PDF links
        pdf_pattern = re.compile(
            r'<a[^>]*href=["\']([^"\']*\.pdf[^"\']*)["\']',
            re.IGNORECASE
        )
        
        matches = pdf_pattern.findall(html_content)
        
        for href in matches:
            full_url = urljoin(base_url, href)
            pdf_links.append(full_url)
            logger.info(f"Found PDF link: {full_url}")
        
        return pdf_links
    
    async def _download_pdf(self, pdf_url: str, source_url: str) -> Optional[str]:
        """
        Download a PDF file.
        
        Args:
            pdf_url: URL of the PDF to download
            source_url: URL of the page containing the PDF link
            
        Returns:
            Filename of the downloaded file, or None if failed
        """
        try:
            logger.info(f"Downloading PDF: {pdf_url}")
            
            # Generate filename
            timestamp = int(datetime.now().timestamp() * 1000)
            filename = f"{timestamp}.pdf"
            filepath = self.download_dir / filename
            
            # Download the file
            response = await self.http_client.get(pdf_url)
            response.raise_for_status()
            
            # Save to file
            async with aiofiles.open(filepath, 'wb') as f:
                await f.write(response.content)
            
            # Log download info
            file_size = len(response.content)
            logger.info(f"Downloaded {filename} ({file_size} bytes) from {pdf_url}")
            
            # Save mapping info
            await self._save_url_mapping(filename, pdf_url, source_url)
            
            return filename
            
        except Exception as e:
            logger.error(f"Failed to download PDF {pdf_url}: {e}")
            return None
    
    async def _save_url_mapping(self, filename: str, pdf_url: str, source_url: str):
        """Save mapping between filename and URLs."""
        mapping_file = self.download_dir / "url_mapping.txt"
        
        mapping_line = f"{filename} {pdf_url} {source_url}\n"
        
        async with aiofiles.open(mapping_file, 'a', encoding='utf-8') as f:
            await f.write(mapping_line)
    
    async def get_existing_downloads(self) -> List[Dict[str, str]]:
        """Get list of already downloaded files."""
        mapping_file = self.download_dir / "url_mapping.txt"
        
        if not mapping_file.exists():
            return []
        
        downloads = []
        
        async with aiofiles.open(mapping_file, 'r', encoding='utf-8') as f:
            async for line in f:
                parts = line.strip().split(' ', 2)
                if len(parts) >= 2:
                    downloads.append({
                        "filename": parts[0],
                        "url": parts[1],
                        "source_page": parts[2] if len(parts) > 2 else ""
                    })
        
        return downloads
    
    def cleanup_old_files(self, keep_days: int = 30):
        """Clean up old downloaded files."""
        cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 3600)
        
        for pdf_file in self.download_dir.glob("*.pdf"):
            if pdf_file.stat().st_mtime < cutoff_time:
                logger.info(f"Removing old file: {pdf_file}")
                pdf_file.unlink()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.http_client.aclose() 