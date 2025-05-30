"""
Policy content scraper for Beijing Transportation Commission website.

Specialized scraper for extracting policy information and converting to markdown.
"""

import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin, urlparse
import aiofiles
import httpx
from crawl4ai import AsyncWebCrawler
from markdownify import markdownify as md

logger = logging.getLogger(__name__)


class PolicyScraper:
    """Specialized scraper for policy content extraction."""
    
    def __init__(self, output_dir: Path = Path("data/policies")):
        """Initialize the policy scraper."""
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Policy-related URLs
        self.policy_urls = [
            "https://xkczb.jtw.beijing.gov.cn/bszn/index.html"
        ]
        
        # HTTP client with better headers to avoid blocking
        self.http_client = httpx.AsyncClient(
            timeout=60.0,
            verify=False,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0"
            }
        )
    
    async def scrape_policy_content(self, max_depth: int = 2) -> List[Dict[str, Any]]:
        """
        Scrape policy content from the configured URLs.
        
        Args:
            max_depth: Maximum link following depth (default: 2 levels)
            
        Returns:
            List of scraped policy documents
        """
        logger.info(f"Starting policy content scraping with max depth: {max_depth}")
        
        scraped_documents = []
        visited_urls = set()  # Track visited URLs to avoid duplicates
        
        try:
            # Configure crawler with better settings for Chinese websites
            crawler_config = {
                "verbose": True,
                "headless": True,
                "browser_type": "chromium",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "wait_for": "networkidle",
                "delay": 3.0,
                "timeout": 30.0
            }
            
            async with AsyncWebCrawler(**crawler_config) as crawler:
                for policy_url in self.policy_urls:
                    logger.info(f"Starting deep scrape from: {policy_url}")
                    
                    # Scrape with depth tracking
                    docs = await self._scrape_with_depth(
                        crawler, policy_url, visited_urls, current_depth=0, max_depth=max_depth
                    )
                    scraped_documents.extend(docs)
        
        except Exception as e:
            logger.error(f"Error during policy scraping: {e}")
            raise
        
        logger.info(f"Policy scraping completed. Processed {len(scraped_documents)} documents from {len(visited_urls)} unique URLs")
        return scraped_documents
    
    async def _scrape_with_retry(self, crawler: AsyncWebCrawler, url: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """Scrape URL with retry logic and different strategies."""
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempt {attempt + 1} to scrape: {url}")
                
                # Try with crawler first
                result = await crawler.arun(
                    url=url,
                    wait_for="networkidle",
                    delay=3.0,
                    timeout=30.0
                )
                
                if result.success and result.html and len(result.html) > 1000:
                    return {
                        "html": result.html,
                        "markdown": result.markdown or "",
                        "method": "crawler"
                    }
                
                # Fallback to direct HTTP request
                logger.info(f"Crawler failed, trying direct HTTP request for: {url}")
                
                async with self.http_client as client:
                    response = await client.get(url)
                    
                    if response.status_code == 200:
                        html_content = response.text
                        
                        # Simple check if content looks valid
                        if len(html_content) > 500 and "<!DOCTYPE" in html_content or "<html" in html_content:
                            return {
                                "html": html_content,
                                "markdown": "",
                                "method": "http"
                            }
                
                logger.warning(f"Attempt {attempt + 1} failed for {url}")
                await asyncio.sleep(5 * (attempt + 1))  # Exponential backoff
                
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} error for {url}: {e}")
                await asyncio.sleep(5 * (attempt + 1))
        
        logger.error(f"All attempts failed for {url}")
        return None
    
    def _extract_policy_links(self, html_content: str, base_url: str) -> List[Dict[str, str]]:
        """Extract policy-related links from HTML content."""
        policy_links = []
        
        # Enhanced keywords that indicate policy content
        policy_keywords = [
            "政策", "指标", "摇号", "新能源", "申请", "指南", "办法", "通知", "公告",
            "规定", "流程", "条件", "要求", "说明", "程序", "配置", "分配", "实施",
            "细则", "暂行", "管理", "调控", "小客车", "家庭", "个人", "单位",
            "复核", "材料", "窗口", "变更", "转让", "登记", "资格", "交易",
            "周转", "二手", "被盗", "抢夺", "办事", "服务", "指引"
        ]
        
        # Pattern to match links with more flexibility
        link_patterns = [
            # Standard <a> tags
            r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>',
            # Links that might be split across lines
            r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>\s*([^<]+(?:<[^>]+>[^<]*)*)\s*</a>',
        ]
        
        all_matches = []
        for pattern in link_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
            all_matches.extend(matches)
        
        # Also look for links in common navigation structures
        nav_patterns = [
            r'<li[^>]*>.*?<a[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>.*?</li>',
            r'<div[^>]*class[^>]*nav[^>]*>.*?<a[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>',
            r'<ul[^>]*>.*?<a[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>.*?</ul>',
        ]
        
        for pattern in nav_patterns:
            nav_matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
            all_matches.extend(nav_matches)
        
        logger.info(f"Found {len(all_matches)} total links on page")
        
        for href, title in all_matches:
            title = re.sub(r'<[^>]+>', '', title)  # Remove any HTML tags
            title = title.strip()
            
            # Skip empty or very short titles
            if len(title) < 3:
                continue
            
            # Check if title contains policy-related keywords
            title_contains_policy = any(keyword in title for keyword in policy_keywords)
            
            # Also check if URL path suggests policy content
            url_suggests_policy = any(keyword in href.lower() for keyword in [
                'bszn', 'policy', 'guide', 'rule', 'regulation', 'notice', 'announcement'
            ])
            
            if title_contains_policy or url_suggests_policy:
                # Clean up href
                href = href.strip()
                
                # Skip certain types of links
                skip_patterns = [
                    'javascript:', 'mailto:', 'tel:', '#', 'void(0)',
                    '.jpg', '.png', '.gif', '.pdf', '.doc', '.xls',
                    'download', 'attachment'
                ]
                
                if any(skip in href.lower() for skip in skip_patterns):
                    continue
                
                # Handle relative URLs
                if href.startswith('/'):
                    # Relative to root
                    from urllib.parse import urlparse
                    parsed_base = urlparse(base_url)
                    full_url = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                elif href.startswith('../') or not href.startswith(('http://', 'https://')):
                    # Relative URL
                    full_url = urljoin(base_url, href)
                else:
                    full_url = href
                
                # Only include URLs from the same domain
                from urllib.parse import urlparse
                base_domain = urlparse(base_url).netloc
                link_domain = urlparse(full_url).netloc
                
                if link_domain != base_domain:
                    continue
                
                # Avoid duplicate URLs
                if full_url not in [link["url"] for link in policy_links]:
                    policy_links.append({
                        "url": full_url,
                        "title": title,
                        "href": href,
                        "policy_score": self._calculate_policy_relevance_score(title, href)
                    })
                    logger.info(f"Found policy link: {title} -> {full_url}")
        
        # Sort by policy relevance score (higher is better)
        policy_links.sort(key=lambda x: x.get("policy_score", 0), reverse=True)
        
        logger.info(f"Extracted {len(policy_links)} relevant policy links")
        return policy_links
    
    def _calculate_policy_relevance_score(self, title: str, href: str) -> int:
        """Calculate relevance score for policy content."""
        score = 0
        
        # High-value keywords
        high_value_keywords = [
            "申请", "指南", "说明", "办法", "规定", "细则", "流程", "实施"
        ]
        
        # Medium-value keywords
        medium_value_keywords = [
            "政策", "指标", "摇号", "新能源", "管理", "调控", "小客车"
        ]
        
        # Count keyword matches in title
        title_lower = title.lower()
        for keyword in high_value_keywords:
            if keyword in title:
                score += 10
        
        for keyword in medium_value_keywords:
            if keyword in title:
                score += 5
        
        # Bonus for URL patterns that suggest policy content
        href_lower = href.lower()
        if 'bszn' in href_lower:  # 办事指南 (service guide)
            score += 15
        if any(pattern in href_lower for pattern in ['guide', 'rule', 'regulation']):
            score += 10
        if any(pattern in href_lower for pattern in ['notice', 'announcement']):
            score += 8
        
        # Penalty for generic terms
        generic_terms = ["首页", "返回", "更多", "查看", "详情"]
        for term in generic_terms:
            if term in title:
                score -= 5
        
        return max(0, score)  # Ensure non-negative score
    
    async def _process_policy_content(self, url: str, html_content: str, title: str) -> Optional[Dict[str, Any]]:
        """Process and convert policy content to markdown."""
        try:
            # Clean and extract main content
            cleaned_content = self._extract_main_content(html_content)
            
            if not cleaned_content or len(cleaned_content.strip()) < 100:
                logger.warning(f"Insufficient content for {url}")
                return None
            
            # Convert to markdown with better settings
            markdown_content = md(
                cleaned_content,
                heading_style="ATX",
                bullets="-",
                strip=['script', 'style', 'nav', 'footer', 'header', 'meta', 'link', 'iframe']
            )
            
            # Clean up markdown
            markdown_content = self._clean_markdown(markdown_content)
            
            # Validate that we have meaningful content
            if len(markdown_content.strip()) < 200:
                logger.warning(f"Markdown content too short for {url}: {len(markdown_content)} chars")
                return None
            
            # Generate descriptive filename
            descriptive_name = self._generate_descriptive_filename(url, html_content, markdown_content, title)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{descriptive_name}_{timestamp}.md"
            
            # Save to file
            file_path = self.output_dir / filename
            
            # Create full markdown document with better structure
            full_content = f"""# {title}

**来源网址**: {url}

**抓取时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}

---

{markdown_content}

---

*本文档由系统自动抓取生成，内容以官方网站为准*
"""
            
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(full_content)
            
            logger.info(f"Successfully saved policy document: {filename} ({len(markdown_content)} chars)")
            
            return {
                "url": url,
                "title": title,
                "filename": filename,
                "file_path": str(file_path),
                "content_length": len(markdown_content),
                "total_length": len(full_content),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error processing policy content for {url}: {e}")
            return None
    
    def _generate_descriptive_filename(self, url: str, html_content: str, markdown_content: str, fallback_title: str) -> str:
        """Generate a descriptive filename based on content analysis."""
        
        # Method 1: Extract specific headings from content
        content_title = self._extract_content_specific_title(html_content, markdown_content)
        if content_title:
            safe_name = self._sanitize_filename(content_title)
            if len(safe_name) > 8:  # Ensure meaningful length
                return f"policy_{safe_name}"
        
        # Method 2: Use URL path to determine content type
        url_based_name = self._extract_name_from_url(url)
        if url_based_name:
            return f"policy_{url_based_name}"
        
        # Method 3: Analyze content keywords to generate descriptive name
        keyword_based_name = self._generate_name_from_keywords(markdown_content)
        if keyword_based_name:
            return f"policy_{keyword_based_name}"
        
        # Method 4: Fallback to sanitized title
        safe_title = self._sanitize_filename(fallback_title)
        return f"policy_{safe_title}"
    
    def _extract_content_specific_title(self, html_content: str, markdown_content: str) -> Optional[str]:
        """Extract specific, meaningful title from content."""
        
        # Look for specific content patterns that indicate the document type
        content_indicators = {
            "个人申请": ["个人", "申请", "办事说明"],
            "家庭申请": ["家庭", "申请", "指标"],
            "单位申请": ["单位", "申请", "指标"],
            "新能源指标": ["新能源", "指标", "轮候"],
            "普通指标": ["普通", "指标", "摇号"],
            "更新指标": ["更新", "指标"],
            "复核申请": ["复核", "申请"],
            "申请材料": ["申请", "材料", "窗口"],
            "办事流程": ["办事", "流程", "程序"],
            "政策解读": ["政策", "解读", "说明"],
            "管理办法": ["管理", "办法", "规定"],
            "实施细则": ["实施", "细则"],
            "操作指南": ["操作", "指南"],
            "资格条件": ["资格", "条件", "要求"],
            "转让登记": ["转让", "登记"],
            "变更手续": ["变更", "手续"],
            "二手车交易": ["二手车", "交易"],
            "被盗抢车辆": ["被盗", "抢夺", "车辆"],
            "周转指标": ["周转", "指标"],
            "各区办公": ["各区", "办公", "窗口"],
        }
        
        # Try to find the most specific match
        best_match = None
        max_score = 0
        
        content_lower = markdown_content.lower()
        html_lower = html_content.lower()
        
        for category, keywords in content_indicators.items():
            score = 0
            for keyword in keywords:
                # Count occurrences in content
                score += content_lower.count(keyword) * 2
                score += html_lower.count(keyword)
            
            if score > max_score and score >= 3:  # Require minimum relevance
                max_score = score
                best_match = category
        
        if best_match:
            logger.info(f"Content-based title match: {best_match} (score: {max_score})")
            return best_match
        
        # Try to extract specific headings that are more descriptive than the page title
        specific_heading_patterns = [
            # Look for section headings that describe the content
            r'##\s*([^#\n]{10,50})',  # Level 2 headings
            r'###\s*([^#\n]{8,40})',  # Level 3 headings
            r'####\s*([^#\n]{8,30})', # Level 4 headings
            
            # HTML heading patterns for fallback
            r'<h2[^>]*>([^<]{10,50})</h2>',
            r'<h3[^>]*>([^<]{8,40})</h3>',
            r'<h4[^>]*>([^<]{8,30})</h4>',
        ]
        
        for pattern in specific_heading_patterns:
            matches = re.findall(pattern, markdown_content + html_content, re.IGNORECASE)
            for match in matches:
                cleaned_match = match.strip()
                # Skip generic headings
                if not any(generic in cleaned_match for generic in [
                    "北京市小客车", "指标管理", "信息系统", "首页", "返回", "更多"
                ]):
                    logger.info(f"Found specific heading: {cleaned_match}")
                    return cleaned_match
        
        return None
    
    def _extract_name_from_url(self, url: str) -> Optional[str]:
        """Extract descriptive name from URL structure."""
        from urllib.parse import urlparse, unquote
        
        parsed = urlparse(url)
        path = unquote(parsed.path)
        
        # Extract meaningful parts from path
        path_parts = [part for part in path.split('/') if part and part != 'index.html']
        
        if not path_parts:
            return None
        
        # Map URL patterns to descriptive names
        url_mappings = {
            'bszn': '办事指南',
            'policy': '政策文件',
            'guide': '操作指南',
            'notice': '通知公告',
            'regulation': '管理规定',
            'application': '申请指南',
            'individual': '个人申请',
            'family': '家庭申请',
            'unit': '单位申请',
            'update': '更新指标',
            'review': '复核申请',
            'material': '申请材料',
            'process': '办事流程',
            'window': '窗口服务',
            'transfer': '转让登记',
            'change': '变更手续',
            'secondhand': '二手车交易',
        }
        
        # Build descriptive name from path
        name_parts = []
        for part in path_parts[-2:]:  # Use last 2 meaningful parts
            # Try direct mapping first
            for key, value in url_mappings.items():
                if key in part.lower():
                    name_parts.append(value)
                    break
            else:
                # Extract date or ID patterns
                if re.match(r'\d{7,}', part):  # Looks like a timestamp/ID
                    continue
                elif re.match(r'\d{4}\d{2,3}', part):  # Looks like date (YYYYMM or YYYYMMDD)
                    date_match = re.match(r'(\d{4})(\d{2})(\d{0,2})', part)
                    if date_match:
                        year, month = date_match.group(1), date_match.group(2)
                        name_parts.append(f"{year}年{month}月")
                elif len(part) > 3 and not part.endswith('.html'):
                    # Use the part as-is if it's meaningful
                    name_parts.append(part)
        
        if name_parts:
            result = '_'.join(name_parts)
            logger.info(f"URL-based name: {result}")
            return result
        
        return None
    
    def _generate_name_from_keywords(self, markdown_content: str) -> Optional[str]:
        """Generate name based on keyword analysis of content."""
        
        # Define keyword groups and their priorities
        keyword_groups = {
            "个人申请": ["个人申请", "个人办事", "个人指标"],
            "家庭申请": ["家庭申请", "家庭指标", "家庭摇号"],
            "单位申请": ["单位申请", "单位指标", "企业申请"],
            "新能源": ["新能源", "纯电动", "电动车"],
            "普通指标": ["普通指标", "燃油车", "传统能源"],
            "更新指标": ["更新指标", "换车", "车辆更新"],
            "申请条件": ["申请条件", "资格条件", "条件说明"],
            "申请流程": ["申请流程", "办事流程", "操作流程"],
            "申请材料": ["申请材料", "所需材料", "证明材料"],
            "摇号规则": ["摇号规则", "摇号说明", "阶梯中签"],
            "审核复核": ["审核复核", "复核申请", "审核结果"],
            "窗口办事": ["窗口办事", "窗口服务", "现场办理"],
            "政策解读": ["政策解读", "政策说明", "实施说明"],
            "管理规定": ["管理规定", "管理办法", "实施细则"],
        }
        
        content_lower = markdown_content.lower()
        
        # Count keyword occurrences
        keyword_scores = {}
        for category, keywords in keyword_groups.items():
            score = sum(content_lower.count(keyword) for keyword in keywords)
            if score > 0:
                keyword_scores[category] = score
        
        if keyword_scores:
            # Get the category with highest score
            best_category = max(keyword_scores.items(), key=lambda x: x[1])
            logger.info(f"Keyword-based name: {best_category[0]} (score: {best_category[1]})")
            return best_category[0]
        
        return None
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename by removing invalid characters."""
        if not name:
            return "unknown"
        
        # Remove or replace invalid filename characters
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        name = re.sub(r'[^\w\s\-\u4e00-\u9fff]', '', name)  # Keep Chinese characters
        name = re.sub(r'\s+', '_', name.strip())
        name = re.sub(r'_+', '_', name)
        name = name.strip('_')
        
        # Limit length
        if len(name) > 50:
            name = name[:50]
        
        return name if name else "policy_content"
    
    def _extract_main_content(self, html_content: str) -> str:
        """Extract main content from HTML, removing navigation and other clutter."""
        
        # Remove scripts, styles, and other non-content elements
        clean_patterns = [
            r'<script[^>]*>.*?</script>',
            r'<style[^>]*>.*?</style>',
            r'<nav[^>]*>.*?</nav>',
            r'<header[^>]*>.*?</header>',
            r'<footer[^>]*>.*?</footer>',
            r'<aside[^>]*>.*?</aside>',
            r'<!--.*?-->',
            r'<meta[^>]*>',
            r'<link[^>]*>',
            r'<iframe[^>]*>.*?</iframe>',
        ]
        
        cleaned_html = html_content
        for pattern in clean_patterns:
            cleaned_html = re.sub(pattern, '', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
        
        # Try to extract main content area with improved patterns
        main_content_patterns = [
            # Common content containers
            r'<main[^>]*>(.*?)</main>',
            r'<article[^>]*>(.*?)</article>',
            r'<div[^>]*class[^>]*content[^>]*>(.*?)</div>',
            r'<div[^>]*id[^>]*content[^>]*>(.*?)</div>',
            r'<div[^>]*class[^>]*main[^>]*>(.*?)</div>',
            r'<div[^>]*id[^>]*main[^>]*>(.*?)</div>',
            
            # Policy-specific containers
            r'<div[^>]*class[^>]*policy[^>]*>(.*?)</div>',
            r'<div[^>]*class[^>]*document[^>]*>(.*?)</div>',
            r'<div[^>]*class[^>]*text[^>]*>(.*?)</div>',
            
            # Chinese website common patterns
            r'<div[^>]*class[^>]*wenzhang[^>]*>(.*?)</div>',
            r'<div[^>]*class[^>]*neirong[^>]*>(.*?)</div>',
            r'<div[^>]*class[^>]*zhengwen[^>]*>(.*?)</div>',
        ]
        
        for pattern in main_content_patterns:
            match = re.search(pattern, cleaned_html, re.DOTALL | re.IGNORECASE)
            if match:
                content = match.group(1)
                # Check if this content is substantial
                text_content = re.sub(r'<[^>]+>', '', content)
                if len(text_content.strip()) > 500:  # Require substantial content
                    logger.info(f"Found main content using pattern: {pattern[:30]}...")
                    return content
        
        # If no specific content area found, try to extract from body but filter out navigation
        body_match = re.search(r'<body[^>]*>(.*?)</body>', cleaned_html, re.DOTALL | re.IGNORECASE)
        if body_match:
            body_content = body_match.group(1)
            
            # Remove common navigation and sidebar elements
            nav_removal_patterns = [
                r'<div[^>]*class[^>]*nav[^>]*>.*?</div>',
                r'<div[^>]*class[^>]*menu[^>]*>.*?</div>',
                r'<div[^>]*class[^>]*sidebar[^>]*>.*?</div>',
                r'<div[^>]*class[^>]*breadcrumb[^>]*>.*?</div>',
                r'<ul[^>]*class[^>]*nav[^>]*>.*?</ul>',
                r'<div[^>]*id[^>]*nav[^>]*>.*?</div>',
                r'<div[^>]*id[^>]*menu[^>]*>.*?</div>',
                r'<div[^>]*id[^>]*sidebar[^>]*>.*?</div>',
            ]
            
            for pattern in nav_removal_patterns:
                body_content = re.sub(pattern, '', body_content, flags=re.DOTALL | re.IGNORECASE)
            
            return body_content
        
        # Last resort: return cleaned HTML
        return cleaned_html
    
    def _clean_markdown(self, markdown_content: str) -> str:
        """Clean up markdown content."""
        
        # Remove excessive whitespace
        markdown_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', markdown_content)
        
        # Remove empty lines at start and end
        markdown_content = markdown_content.strip()
        
        # Fix common markdown issues
        markdown_content = re.sub(r'\*\*\s*\*\*', '', markdown_content)
        markdown_content = re.sub(r'__\s*__', '', markdown_content)
        markdown_content = re.sub(r'\[\s*\]\(\s*\)', '', markdown_content)  # Remove empty links
        
        # Clean up multiple consecutive empty links or images
        markdown_content = re.sub(r'(\!\[\]\([^)]*\)\s*){2,}', '', markdown_content)
        
        # Remove standalone "返回" or "首页" links that don't add value
        markdown_content = re.sub(r'^\s*\[?(返回|首页|更多)\]?\s*$', '', markdown_content, flags=re.MULTILINE)
        
        # Clean up excessive dashes or underscores
        markdown_content = re.sub(r'^[-_\s]*$', '', markdown_content, flags=re.MULTILINE)
        
        # Remove lines that are just whitespace or punctuation
        lines = markdown_content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Skip lines that are empty, just punctuation, or very short navigation text
            if (len(stripped) > 2 and 
                not re.match(r'^[^\w]*$', stripped) and 
                not stripped.lower() in ['more', '更多', '详情', '查看', '返回', '首页']):
                cleaned_lines.append(line)
        
        # Join lines and clean up again
        markdown_content = '\n'.join(cleaned_lines)
        markdown_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', markdown_content)
        
        return markdown_content.strip()
    
    async def cleanup(self):
        """Cleanup resources."""
        await self.http_client.aclose()
    
    async def _scrape_with_depth(
        self, 
        crawler: AsyncWebCrawler, 
        url: str, 
        visited_urls: set, 
        current_depth: int, 
        max_depth: int
    ) -> List[Dict[str, Any]]:
        """Recursively scrape URLs with depth tracking."""
        
        # Skip if already visited or max depth reached
        if url in visited_urls or current_depth > max_depth:
            return []
        
        # Add to visited set
        visited_urls.add(url)
        
        logger.info(f"Scraping depth {current_depth}/{max_depth}: {url}")
        
        scraped_documents = []
        
        try:
            # Try multiple approaches to get content
            content = await self._scrape_with_retry(crawler, url)
            
            if not content:
                logger.warning(f"Failed to get content from {url}")
                return []
            
            # Extract and process policy links for next depth
            policy_links = self._extract_policy_links(content["html"], url)
            logger.info(f"Found {len(policy_links)} policy links at depth {current_depth}")
            
            # Process current page content
            page_title = self._extract_page_title(content["html"], url)
            main_doc = await self._process_policy_content(
                url, content["html"], page_title
            )
            
            if main_doc:
                main_doc["depth"] = current_depth
                scraped_documents.append(main_doc)
                logger.info(f"Successfully processed content from depth {current_depth}: {page_title}")
            
            # If we haven't reached max depth, follow the links
            if current_depth < max_depth:
                # Limit the number of links to follow to avoid overwhelming the system
                links_to_follow = policy_links[:15] if current_depth == 0 else policy_links[:8]
                
                for i, link_info in enumerate(links_to_follow):
                    try:
                        logger.info(f"Following link {i+1}/{len(links_to_follow)} at depth {current_depth}: {link_info['title']}")
                        
                        # Add delay between requests to be respectful
                        await asyncio.sleep(2)
                        
                        # Recursively scrape the linked page
                        sub_docs = await self._scrape_with_depth(
                            crawler, 
                            link_info["url"], 
                            visited_urls, 
                            current_depth + 1, 
                            max_depth
                        )
                        scraped_documents.extend(sub_docs)
                        
                    except Exception as e:
                        logger.error(f"Error processing policy link {link_info['url']} at depth {current_depth}: {e}")
                        continue
            
        except Exception as e:
            logger.error(f"Error scraping URL {url} at depth {current_depth}: {e}")
        
        return scraped_documents
    
    def _extract_page_title(self, html_content: str, url: str) -> str:
        """Extract page title from HTML content."""
        
        # Try to get title from <title> tag first
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            # Clean up common title patterns
            title = re.sub(r'\s*[-–—]\s*.*$', '', title)  # Remove everything after dash
            title = re.sub(r'\s*\|\s*.*$', '', title)     # Remove everything after pipe
            if len(title) > 10:  # Only use if meaningful
                return title
        
        # Try to get from main heading
        heading_patterns = [
            r'<h1[^>]*>([^<]+)</h1>',
            r'<h2[^>]*>([^<]+)</h2>',
            r'<h3[^>]*>([^<]+)</h3>'
        ]
        
        for pattern in heading_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                heading = match.group(1).strip()
                if len(heading) > 5:
                    return heading
        
        # Fallback: use URL path
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        path_parts = [part for part in parsed_url.path.split('/') if part]
        if path_parts:
            return path_parts[-1].replace('.html', '').replace('_', ' ')
        
        return f"policy_page_{datetime.now().strftime('%H%M%S')}" 