"""
MCP server implementation for Beijing car quota lottery results.

Uses fastapi_mcp to expose FastAPI endpoints as MCP tools for AI agents.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel, Field
import uvicorn
import aiofiles
import re
import json

from ..models.quota_result import QuotaResult, QuotaType
from ..parsers.pdf_parser import PDFParser
from ..scrapers.web_scraper import WebScraper
from ..scrapers.policy_scraper import PolicyScraper
from ..storage.data_store import DataStore
from ..analysis.analyzer import LotteryAnalyzer
from ..utils.celebration_generator import CelebrationGenerator

logger = logging.getLogger(__name__)


class QuotaSearchRequest(BaseModel):
    """Request model for quota searches."""
    application_code: str = Field(..., description="申请编码")


class IDSearchRequest(BaseModel):
    """Request model for ID number searches."""
    id_prefix: Optional[str] = Field(None, description="身份证号前6位 (可选)")
    id_suffix: Optional[str] = Field(None, description="身份证号后4位 (可选)")


class CelebrationRequest(BaseModel):
    """Request model for celebration page generation."""
    application_code: str = Field(..., description="申请编码")
    name: Optional[str] = Field("恭喜您", description="获奖者姓名 (可选)")
    save_to_file: Optional[bool] = Field(False, description="是否保存为文件 (可选)")


class PolicyExplanationRequest(BaseModel):
    """Request model for policy explanations."""
    question: str = Field(..., description="关于小客车指标政策的问题")
    detail_level: Optional[str] = Field("medium", description="详细程度: basic, medium, detailed")
    category: Optional[str] = Field(None, description="政策类别: 个人申请, 家庭申请, 单位申请, 新能源, 更新指标, 申请材料, 等等")


class MCPServer:
    """MCP server for Beijing car quota lottery results."""
    
    def __init__(
        self,
        data_dir: Path = Path("data"),
        downloads_dir: Path = Path("downloads"),
        host: str = "127.0.0.1",
        port: int = 8000
    ):
        """
        Initialize the MCP server.
        
        Args:
            data_dir: Directory for storing processed data
            downloads_dir: Directory for downloaded PDF files
            host: Server host
            port: Server port
        """
        self.data_dir = data_dir
        self.downloads_dir = downloads_dir
        self.host = host
        self.port = port
        
        # Initialize components
        self.data_store = DataStore(data_dir)
        self.pdf_parser = PDFParser()
        self.web_scraper = WebScraper(downloads_dir)
        self.policy_scraper = PolicyScraper()
        self.analyzer = LotteryAnalyzer(self.data_store)
        self.celebration_generator = CelebrationGenerator()
        
        # Create FastAPI app
        self.app = FastAPI(
            title="Beijing Car Quota Lottery MCP Server",
            description="MCP server for querying Beijing car quota lottery results",
            version="0.1.0"
        )
        
        # Setup routes
        self._setup_routes()
        
        # Create MCP server
        self.mcp = FastApiMCP(
            self.app,
            name="Beijing Car Quota Lottery API",
            description="API for querying Beijing car quota lottery results"
        )
        
        # Mount MCP server
        self.mcp.mount()
    
    def _setup_routes(self):
        """Setup FastAPI routes that will be exposed as MCP tools."""
        
        @self.app.get("/health", operation_id="health_check")
        async def health_check():
            """Check server health and data status."""
            stats = await self.data_store.get_statistics()
            return {
                "status": "healthy",
                "server": "Beijing Car Quota Lottery MCP Server",
                "version": "0.1.0",
                "data_stats": stats
            }
        
        @self.app.post("/search/application-code", operation_id="search_by_application_code")
        async def search_by_application_code(request: QuotaSearchRequest):
            """
            Search for quota lottery results by application code (申请编码).
            
            This tool searches across all loaded PDF files to find entries
            matching the provided application code.
            """
            try:
                results = await self.data_store.find_by_application_code(request.application_code)
                
                if not results:
                    return {
                        "found": False,
                        "message": f"No results found for application code: {request.application_code}",
                        "application_code": request.application_code
                    }
                
                # Check if this might be a winner (not just waiting list)
                winner_results = [r for r in results if r.get("type") != "waiting_list"]
                is_potential_winner = len(winner_results) > 0
                
                # Also check for high-priority waiting list (early sequence numbers)
                if not is_potential_winner:
                    high_priority_results = [r for r in results if r.get("sequence_number") and r.get("sequence_number") <= 50000]
                    is_potential_winner = len(high_priority_results) > 0
                
                response = {
                    "found": True,
                    "application_code": request.application_code,
                    "results": results,
                    "count": len(results)
                }
                
                # Add celebration suggestion for potential winners
                if is_potential_winner:
                    response["winner_detected"] = True
                    response["celebration_suggestion"] = {
                        "message": "🎉 Congratulations! You appear to have won the lottery!",
                        "action": "Generate a celebration page to share the good news!",
                        "endpoint": "/celebration/generate",
                        "parameters": {
                            "application_code": request.application_code,
                            "name": "您的姓名",  # User can customize
                            "save_to_file": True
                        }
                    }
                else:
                    response["winner_detected"] = False
                    response["status_info"] = "Currently on waiting list - keep checking for updates!"
                
                return response
                
            except Exception as e:
                logger.error(f"Error searching by application code {request.application_code}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/search/id-number", operation_id="search_by_id_number")
        async def search_by_id_number(request: IDSearchRequest):
            """
            Search for quota lottery results by partial ID number.
            
            This tool searches for entries using the first 6 and/or last 4 digits
            of an ID number (身份证号). You can provide either:
            - Only id_prefix (first 6 digits)
            - Only id_suffix (last 4 digits) 
            - Both id_prefix and id_suffix for exact match
            """
            try:
                # Validation: at least one field must be provided
                if not request.id_prefix and not request.id_suffix:
                    raise HTTPException(
                        status_code=400, 
                        detail="At least one of id_prefix or id_suffix must be provided"
                    )
                
                # Validate field formats if provided
                if request.id_prefix and len(request.id_prefix) != 6:
                    raise HTTPException(
                        status_code=400,
                        detail="id_prefix must be exactly 6 digits"
                    )
                
                if request.id_suffix and len(request.id_suffix) != 4:
                    raise HTTPException(
                        status_code=400,
                        detail="id_suffix must be exactly 4 digits"
                    )
                
                # Search using the new flexible method
                results = await self.data_store.find_by_id_prefix_or_suffix(
                    request.id_prefix, request.id_suffix
                )
                
                # Create search pattern description
                if request.id_prefix and request.id_suffix:
                    search_pattern = f"{request.id_prefix}****{request.id_suffix}"
                elif request.id_prefix:
                    search_pattern = f"{request.id_prefix}****XXXX"
                else:
                    search_pattern = f"XXXXXX****{request.id_suffix}"
                
                if not results:
                    return {
                        "found": False,
                        "message": f"No results found for ID pattern: {search_pattern}",
                        "search_pattern": search_pattern,
                        "search_type": "prefix_and_suffix" if (request.id_prefix and request.id_suffix) 
                                      else "prefix_only" if request.id_prefix 
                                      else "suffix_only"
                    }
                
                # Check if any results indicate winners
                winner_results = [r for r in results if r.get("type") != "waiting_list"]
                high_priority_results = [r for r in results if r.get("sequence_number") and r.get("sequence_number") <= 50000]
                is_potential_winner = len(winner_results) > 0 or len(high_priority_results) > 0
                
                response = {
                    "found": True,
                    "search_pattern": search_pattern,
                    "search_type": "prefix_and_suffix" if (request.id_prefix and request.id_suffix) 
                                  else "prefix_only" if request.id_prefix 
                                  else "suffix_only",
                    "results": results,
                    "count": len(results)
                }
                
                # Add celebration suggestion for potential winners
                if is_potential_winner and len(results) == 1:  # Only suggest for single match
                    result = results[0]
                    response["winner_detected"] = True
                    response["celebration_suggestion"] = {
                        "message": "🎉 Congratulations! You appear to have won the lottery!",
                        "action": "Generate a celebration page to share the good news!",
                        "endpoint": "/celebration/generate",
                        "parameters": {
                            "application_code": result.get("application_code", ""),
                            "name": result.get("name", "您的姓名"),
                            "save_to_file": True
                        }
                    }
                elif is_potential_winner:
                    response["winner_detected"] = True
                    response["multiple_winners"] = True
                    response["celebration_note"] = "Multiple winning entries found! You can generate celebration pages for each application code."
                else:
                    response["winner_detected"] = False
                    response["status_info"] = "Currently on waiting list - keep checking for updates!"
                
                return response
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error searching by ID {request.id_prefix}/{request.id_suffix}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/celebration/generate", operation_id="generate_celebration_page")
        async def generate_celebration_page(request: CelebrationRequest):
            """
            Generate a celebration HTML page for lottery winners.
            
            This tool creates a beautiful, animated HTML page with splash effects
            to celebrate users who have won the car quota lottery. The page includes
            fireworks, confetti, sparkles, and sharing functionality.
            """
            try:
                # First, verify that the application code actually won
                results = await self.data_store.find_by_application_code(request.application_code)
                
                if not results:
                    return {
                        "success": False,
                        "message": f"No lottery results found for application code: {request.application_code}",
                        "celebration_generated": False
                    }
                
                # Check if the person actually won (not just in waiting list)
                winner_results = [r for r in results if r.get("type") != "waiting_list"]
                
                if not winner_results:
                    # Check if they're in a prioritized waiting list (which might indicate winning)
                    prioritized_results = [r for r in results if r.get("sequence_number") and r.get("sequence_number") <= 50000]
                    
                    if not prioritized_results:
                        return {
                            "success": False,
                            "message": "Application code found but appears to be on waiting list only. Celebration pages are for confirmed winners.",
                            "celebration_generated": False,
                            "waiting_list_info": results[:3]  # Show first 3 waiting list entries
                        }
                    else:
                        # Use prioritized waiting list results as potential winners
                        winner_results = prioritized_results
                
                # Prepare winner information
                winner_info = {
                    "application_code": request.application_code,
                    "name": request.name or "恭喜您",
                    "id_info": ""  # We don't have ID info from application code search
                }
                
                # Generate celebration page
                save_path = None
                if request.save_to_file:
                    celebrations_dir = self.data_dir / "celebrations"
                    celebrations_dir.mkdir(exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    save_path = celebrations_dir / f"celebration_{request.application_code}_{timestamp}.html"
                
                html_content = self.celebration_generator.generate_celebration_page(
                    winner_info=winner_info,
                    lottery_results=winner_results,
                    save_path=save_path
                )
                
                # Create sharing links
                sharing_links = self.celebration_generator.create_sharing_links(winner_info)
                
                response = {
                    "success": True,
                    "message": "🎉 Celebration page generated successfully!",
                    "celebration_generated": True,
                    "application_code": request.application_code,
                    "winner_name": winner_info["name"],
                    "lottery_results_count": len(winner_results),
                    "sharing_links": sharing_links
                }
                
                if request.save_to_file and save_path:
                    response["saved_file"] = str(save_path)
                else:
                    # Return HTML content directly if not saving to file
                    response["html_content"] = html_content
                
                return response
                
            except Exception as e:
                logger.error(f"Error generating celebration page for {request.application_code}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/data/statistics", operation_id="get_data_statistics")
        async def get_data_statistics():
            """
            Get statistics about the loaded quota lottery data.
            
            Returns information about the number of files loaded, total entries,
            last update time, and breakdown by data type.
            """
            try:
                stats = await self.data_store.get_statistics()
                return stats
            except Exception as e:
                logger.error(f"Error getting statistics: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/data/refresh", operation_id="refresh_data")
        async def refresh_data(max_pages: int = Query(5, description="Maximum pages to scrape")):
            """
            Refresh quota lottery data by scraping the latest PDFs.
            
            This tool scrapes the Beijing Transportation Commission website
            for new PDF files and processes them to update the searchable data.
            """
            try:
                logger.info("Starting data refresh...")
                
                # Use WebScraper as context manager to ensure proper resource cleanup
                async with WebScraper(self.downloads_dir) as scraper:
                    # Scrape and download new PDFs
                    downloaded_files = await scraper.scrape_and_download(max_pages)
                
                if not downloaded_files:
                    return {
                        "success": True,
                        "message": "No new PDF files found",
                        "files_processed": 0
                    }
                
                # Process downloaded PDFs
                processed_count = 0
                errors = []
                
                for file_info in downloaded_files:
                    try:
                        pdf_path = self.downloads_dir / file_info["filename"]
                        source_url = file_info.get("source_page", "")
                        
                        # Parse PDF
                        result = self.pdf_parser.parse_pdf(pdf_path, source_url)
                        
                        # Validate parsed data
                        validation_report = self.pdf_parser.validate_parsed_data(result)
                        
                        if validation_report["is_valid"]:
                            # Add to data store
                            await self.data_store.add_quota_result(result)
                            processed_count += 1
                            logger.info(f"Successfully processed {file_info['filename']}")
                        else:
                            errors.append(f"Validation failed for {file_info['filename']}: {validation_report['errors']}")
                            
                    except Exception as e:
                        error_msg = f"Error processing {file_info['filename']}: {str(e)}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                
                return {
                    "success": True,
                    "message": f"Data refresh completed",
                    "files_downloaded": len(downloaded_files),
                    "files_processed": processed_count,
                    "errors": errors
                }
                
            except Exception as e:
                logger.error(f"Error during data refresh: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/data/scrape-policy", operation_id="scrape_policy_documents")
        async def scrape_policy_documents():
            """
            Scrape policy documents from the Beijing Transportation Commission website.
            
            This tool scrapes policy documents from the Beijing Transportation Commission website
            and processes them to update the searchable data.
            """
            try:
                logger.info("Starting policy document scraping...")
                
                # Scrape policy documents
                scraped_documents = await self.policy_scraper.scrape_policy_content()
                
                return {
                    "success": True,
                    "message": f"Policy document scraping completed",
                    "total_documents": len(scraped_documents),
                    "documents": scraped_documents
                }
                
            except Exception as e:
                logger.error(f"Error during policy scraping: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/policy/explain", operation_id="explain_car_quota_policy")
        async def explain_car_quota_policy(request: PolicyExplanationRequest):
            """
            Explain Beijing car quota policy based on the knowledge base.
            
            This tool analyzes the user's question about car quota policy and provides
            detailed explanations based on the scraped policy documents. It can answer
            questions about application procedures, requirements, materials needed, 
            timeframes, and specific policy details.
            """
            try:
                logger.info(f"Processing policy question: {request.question}")
                
                # Search relevant policy documents
                relevant_docs = await self._find_relevant_policy_documents(request.question, request.category)
                
                if not relevant_docs:
                    return {
                        "question": request.question,
                        "answer": "很抱歉，在现有的政策知识库中没有找到相关信息。建议您访问北京市交通委员会官方网站或致电12328咨询热线获取最新政策信息。",
                        "confidence": "low",
                        "sources": [],
                        "suggestions": [
                            "请检查问题的关键词是否正确",
                            "尝试使用更具体的政策术语",
                            "访问官方网站: https://xkczb.jtw.beijing.gov.cn",
                            "致电咨询热线: 12328"
                        ]
                    }
                
                # Generate explanation based on relevant documents
                explanation = await self._generate_policy_explanation(
                    request.question, 
                    relevant_docs, 
                    request.detail_level
                )
                
                return {
                    "question": request.question,
                    "answer": explanation["answer"],
                    "confidence": explanation["confidence"],
                    "sources": explanation["sources"],
                    "related_topics": explanation["related_topics"],
                    "actionable_steps": explanation.get("actionable_steps", []),
                    "important_notes": explanation.get("important_notes", [])
                }
                
            except Exception as e:
                logger.error(f"Error explaining policy: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/data/files", operation_id="list_data_files")
        async def list_data_files():
            """
            List all loaded quota lottery data files.
            
            Returns information about each PDF file that has been processed
            and is available for searching.
            """
            try:
                stats = await self.data_store.get_statistics()
                return {
                    "total_files": stats["total_files"],
                    "files": stats["files"]
                }
            except Exception as e:
                logger.error(f"Error listing files: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        # Analysis endpoints
        @self.app.get("/analysis/comprehensive", operation_id="get_comprehensive_analysis")
        async def get_comprehensive_analysis():
            """
            Get comprehensive lottery analysis including success rates, waiting times, and trends.
            
            This tool provides a complete analysis of Beijing car quota lottery data,
            including success rates by year, estimated waiting times, trend analysis,
            and personalized recommendations.
            """
            try:
                analysis = await self.analyzer.get_comprehensive_analysis()
                return analysis
            except Exception as e:
                logger.error(f"Error getting comprehensive analysis: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/analysis/success-rates", operation_id="get_success_rates_analysis")
        async def get_success_rates_analysis():
            """
            Get lottery success rate analysis by year.
            
            This tool calculates and returns the success rates for each year,
            including estimated number of applicants, winners, and rejection rates.
            """
            try:
                analysis = await self.analyzer.get_success_rates()
                return analysis
            except Exception as e:
                logger.error(f"Error getting success rates analysis: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/analysis/waiting-time", operation_id="get_waiting_time_analysis")
        async def get_waiting_time_analysis():
            """
            Get waiting time analysis for queue participants.
            
            This tool estimates average waiting times for people in the queue
            based on historical data and annual quotas.
            """
            try:
                analysis = await self.analyzer.get_waiting_time_analysis()
                return analysis
            except Exception as e:
                logger.error(f"Error getting waiting time analysis: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/analysis/trends", operation_id="get_trend_analysis")
        async def get_trend_analysis():
            """
            Get trend analysis comparing different years.
            
            This tool analyzes trends in success rates, competition levels,
            and changes in the lottery system over time.
            """
            try:
                analysis = await self.analyzer.get_trend_analysis()
                return analysis
            except Exception as e:
                logger.error(f"Error getting trend analysis: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    async def _find_relevant_policy_documents(self, question: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Find policy documents relevant to the user's question."""
        try:
            policies_dir = self.data_dir / "policies"
            if not policies_dir.exists():
                logger.warning("No policies directory found")
                return []
            
            # Get all policy files
            policy_files = list(policies_dir.glob("*.md"))
            if not policy_files:
                logger.warning("No policy documents found")
                return []
            
            # Keywords from the question
            question_lower = question.lower()
            question_keywords = self._extract_keywords_from_question(question_lower)
            
            relevant_docs = []
            
            for policy_file in policy_files:
                try:
                    async with aiofiles.open(policy_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                    
                    # Calculate relevance score
                    relevance_score = self._calculate_document_relevance(
                        content, question_keywords, question_lower, category
                    )
                    
                    if relevance_score > 0:
                        # Extract key sections related to the question
                        relevant_sections = self._extract_relevant_sections(content, question_keywords)
                        
                        relevant_docs.append({
                            "filename": policy_file.name,
                            "path": str(policy_file),
                            "relevance_score": relevance_score,
                            "content": content,
                            "relevant_sections": relevant_sections
                        })
                        
                except Exception as e:
                    logger.error(f"Error reading policy file {policy_file}: {e}")
                    continue
            
            # Sort by relevance score and return top results
            relevant_docs.sort(key=lambda x: x["relevance_score"], reverse=True)
            return relevant_docs[:5]  # Return top 5 most relevant documents
            
        except Exception as e:
            logger.error(f"Error finding relevant policy documents: {e}")
            return []
    
    def _extract_keywords_from_question(self, question: str) -> List[str]:
        """Extract keywords from the user's question."""
        # Common policy-related keywords
        policy_keywords = [
            # Application types
            "个人申请", "家庭申请", "单位申请", "个人", "家庭", "单位", "企业",
            
            # Vehicle types
            "新能源", "普通", "燃油车", "电动车", "纯电动",
            
            # Process terms
            "申请", "摇号", "轮候", "更新", "复核", "审核", "材料", "条件", "流程", "程序",
            
            # Requirements
            "资格", "条件", "要求", "证件", "证明", "驾驶证", "身份证", "居住证", "工作居住证",
            
            # Time-related
            "时间", "期限", "有效期", "申报期", "截止", "多久", "什么时候", "几月",
            
            # Results and status
            "结果", "中签", "获得", "成功", "失败", "等待", "排队",
            
            # Documents and procedures
            "材料", "文件", "手续", "窗口", "办理", "提交", "打印", "下载",
            
            # Specific processes
            "转让", "变更", "过户", "注销", "登记", "被盗", "抢夺"
        ]
        
        # Find keywords present in the question
        found_keywords = []
        for keyword in policy_keywords:
            if keyword in question:
                found_keywords.append(keyword)
        
        # Also extract potential question words
        question_words = ["如何", "怎么", "什么", "哪些", "多少", "几", "是否", "能否", "可以", "需要"]
        for word in question_words:
            if word in question:
                found_keywords.append(word)
        
        return found_keywords
    
    def _calculate_document_relevance(self, content: str, keywords: List[str], question: str, category: Optional[str]) -> float:
        """Calculate how relevant a document is to the user's question."""
        score = 0.0
        content_lower = content.lower()
        
        # Check for direct keyword matches
        for keyword in keywords:
            count = content_lower.count(keyword)
            score += count * 2  # Each keyword occurrence adds 2 points
        
        # Bonus for category match in filename or content
        if category:
            category_lower = category.lower()
            if category_lower in content_lower:
                score += 10
        
        # Check for related terms in content
        related_terms = {
            "申请": ["提交", "填报", "办理", "登记"],
            "材料": ["证件", "文件", "证明", "资料"],
            "条件": ["要求", "资格", "规定"],
            "流程": ["程序", "步骤", "操作", "办理"],
            "时间": ["期限", "截止", "有效期", "申报期"]
        }
        
        for main_term, related in related_terms.items():
            if main_term in question:
                for related_term in related:
                    score += content_lower.count(related_term) * 1
        
        # Penalty for very short documents (likely not comprehensive)
        if len(content) < 1000:
            score *= 0.5
        
        return score
    
    def _extract_relevant_sections(self, content: str, keywords: List[str]) -> List[str]:
        """Extract sections of the document that are most relevant to the question."""
        relevant_sections = []
        
        # Split content into paragraphs
        paragraphs = content.split('\n\n')
        
        for paragraph in paragraphs:
            paragraph_lower = paragraph.lower()
            
            # Count keyword matches in this paragraph
            keyword_count = sum(1 for keyword in keywords if keyword in paragraph_lower)
            
            # If paragraph has relevant keywords and is substantial, include it
            if keyword_count >= 1 and len(paragraph.strip()) > 100:
                # Clean up the paragraph
                cleaned = paragraph.strip()
                if cleaned and not cleaned.startswith('*') and not cleaned.startswith('---'):
                    relevant_sections.append(cleaned)
        
        # Return top 5 most relevant sections
        return relevant_sections[:5]
    
    async def _generate_policy_explanation(self, question: str, relevant_docs: List[Dict], detail_level: str) -> Dict[str, Any]:
        """Generate a comprehensive explanation based on relevant documents."""
        try:
            # Combine relevant sections from all documents
            all_relevant_content = []
            sources = []
            
            for doc in relevant_docs:
                sources.append({
                    "filename": doc["filename"],
                    "relevance_score": doc["relevance_score"]
                })
                
                # Add the most relevant sections
                for section in doc["relevant_sections"]:
                    all_relevant_content.append(section)
            
            if not all_relevant_content:
                return {
                    "answer": "在现有政策文档中未找到相关信息。",
                    "confidence": "low",
                    "sources": sources,
                    "related_topics": []
                }
            
            # Generate answer based on detail level
            answer = self._construct_answer(question, all_relevant_content, detail_level)
            
            # Extract actionable steps and important notes
            actionable_steps = self._extract_actionable_steps(all_relevant_content)
            important_notes = self._extract_important_notes(all_relevant_content)
            related_topics = self._suggest_related_topics(question, relevant_docs)
            
            # Determine confidence level
            confidence = "high" if len(relevant_docs) >= 2 else "medium" if len(relevant_docs) == 1 else "low"
            
            return {
                "answer": answer,
                "confidence": confidence,
                "sources": sources,
                "related_topics": related_topics,
                "actionable_steps": actionable_steps,
                "important_notes": important_notes
            }
            
        except Exception as e:
            logger.error(f"Error generating policy explanation: {e}")
            return {
                "answer": "生成解释时发生错误，请稍后重试。",
                "confidence": "low",
                "sources": [],
                "related_topics": []
            }
    
    def _construct_answer(self, question: str, content_sections: List[str], detail_level: str) -> str:
        """Construct a comprehensive answer from relevant content sections."""
        
        # Basic structure for the answer
        answer_parts = []
        
        # Identify the type of question
        question_lower = question.lower()
        
        if any(word in question_lower for word in ["如何", "怎么", "怎样"]):
            answer_parts.append("根据政策规定，具体步骤如下：\n")
        elif any(word in question_lower for word in ["什么", "哪些"]):
            answer_parts.append("根据政策文件，相关信息如下：\n")
        elif any(word in question_lower for word in ["需要", "要", "应该"]):
            answer_parts.append("根据政策要求：\n")
        else:
            answer_parts.append("根据相关政策规定：\n")
        
        # Process content based on detail level
        if detail_level == "basic":
            # Provide a concise summary
            key_points = []
            for section in content_sections[:2]:  # Use top 2 sections
                # Extract key sentences
                sentences = section.split('。')
                for sentence in sentences[:2]:  # First 2 sentences per section
                    if len(sentence.strip()) > 20:
                        key_points.append(sentence.strip() + '。')
            
            answer_parts.extend(key_points[:3])  # Max 3 key points for basic
            
        elif detail_level == "detailed":
            # Provide comprehensive information
            for i, section in enumerate(content_sections[:4]):  # Use top 4 sections
                if i > 0:
                    answer_parts.append(f"\n{i+1}. ")
                
                # Clean and format the section
                cleaned_section = self._clean_content_section(section)
                answer_parts.append(cleaned_section)
        
        else:  # medium (default)
            # Balanced approach
            for i, section in enumerate(content_sections[:3]):  # Use top 3 sections
                if i > 0:
                    answer_parts.append(f"\n\n{i+1}. ")
                
                # Extract important parts
                cleaned_section = self._clean_content_section(section)
                # Limit length for medium detail
                if len(cleaned_section) > 300:
                    cleaned_section = cleaned_section[:300] + "..."
                answer_parts.append(cleaned_section)
        
        # Add closing note
        answer_parts.append("\n\n*以上信息基于现有政策文档，具体要求请以官方最新政策为准。如有疑问，请咨询12328热线或访问官方网站。*")
        
        return "".join(answer_parts)
    
    def _clean_content_section(self, section: str) -> str:
        """Clean up a content section for presentation."""
        # Remove markdown formatting
        cleaned = re.sub(r'[#*_]', '', section)
        
        # Remove URLs and links
        cleaned = re.sub(r'http[s]?://\S+', '', cleaned)
        cleaned = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', cleaned)
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # Remove system notes
        cleaned = re.sub(r'\*[^*]*系统.*?\*', '', cleaned)
        
        return cleaned.strip()
    
    def _extract_actionable_steps(self, content_sections: List[str]) -> List[str]:
        """Extract actionable steps from the content."""
        steps = []
        
        # Look for numbered lists, step indicators, etc.
        step_patterns = [
            r'(\d+)\.?\s*([^。]*申请[^。]*)',
            r'(\d+)\.?\s*([^。]*提交[^。]*)', 
            r'(\d+)\.?\s*([^。]*办理[^。]*)',
            r'(\d+)\.?\s*([^。]*填报[^。]*)',
            r'第\s*([一二三四五六七八九十]+)\s*[步条]?\s*[：:]?\s*([^。]*)',
        ]
        
        for section in content_sections:
            for pattern in step_patterns:
                matches = re.findall(pattern, section)
                for match in matches:
                    if len(match) >= 2:
                        step_text = match[1].strip()
                        if len(step_text) > 10:  # Ensure meaningful content
                            steps.append(step_text)
        
        return steps[:5]  # Return top 5 steps
    
    def _extract_important_notes(self, content_sections: List[str]) -> List[str]:
        """Extract important notes and warnings from the content."""
        notes = []
        
        # Look for important indicators
        note_patterns = [
            r'注意[：:]?\s*([^。]*)',
            r'重要[：:]?\s*([^。]*)',
            r'注[：:]?\s*([^。]*)',
            r'备注[：:]?\s*([^。]*)',
            r'特别提醒[：:]?\s*([^。]*)',
        ]
        
        for section in content_sections:
            for pattern in note_patterns:
                matches = re.findall(pattern, section)
                for match in matches:
                    note_text = match.strip()
                    if len(note_text) > 15:  # Ensure meaningful content
                        notes.append(note_text)
        
        return notes[:3]  # Return top 3 notes
    
    def _suggest_related_topics(self, question: str, relevant_docs: List[Dict]) -> List[str]:
        """Suggest related topics based on the question and available documents."""
        topics = []
        
        # Analyze question to suggest related topics
        question_lower = question.lower()
        
        # Topic mapping
        topic_suggestions = {
            "个人申请": ["家庭申请政策", "申请材料清单", "申请条件说明", "审核流程"],
            "家庭申请": ["个人申请区别", "家庭积分规则", "申请材料要求", "轮候时间"],
            "新能源": ["普通指标对比", "轮候排队规则", "车辆类型要求", "更新指标"],
            "申请材料": ["窗口办理流程", "在线申请步骤", "证件要求", "代办规定"],
            "摇号": ["中签率分析", "阶梯中签规则", "申请次数统计", "结果查询"],
            "更新": ["车辆过户手续", "指标有效期", "更新条件", "申请流程"]
        }
        
        # Find matching topics based on question content
        for key, suggestions in topic_suggestions.items():
            if key in question_lower:
                topics.extend(suggestions)
        
        # Also suggest based on available document types
        doc_types = set()
        for doc in relevant_docs:
            filename = doc["filename"]
            if "个人申请" in filename:
                doc_types.add("个人申请相关政策")
            if "家庭申请" in filename:
                doc_types.add("家庭申请相关政策")
            if "材料" in filename:
                doc_types.add("申请材料清单")
            if "更新" in filename:
                doc_types.add("更新指标政策")
        
        topics.extend(list(doc_types))
        
        # Remove duplicates and limit
        return list(set(topics))[:5]
    
    async def initialize(self):
        """Initialize the server by loading existing data."""
        logger.info("Initializing MCP server...")
        
        # Create directories
        self.data_dir.mkdir(exist_ok=True)
        self.downloads_dir.mkdir(exist_ok=True)
        
        # Load existing data from disk
        await self.data_store.load_from_disk()
        
        # If no data exists, try to load example PDFs
        if self.data_store.total_entries == 0:
            await self._load_example_pdfs()
        
        logger.info(f"MCP server initialized with {self.data_store.total_entries} total entries")
    
    async def _load_example_pdfs(self):
        """Load example PDF files if they exist."""
        examples_dir = Path("examples")
        
        if not examples_dir.exists():
            logger.info("No examples directory found, skipping example PDF loading")
            return
        
        # Load example PDFs
        for pdf_file in examples_dir.glob("*.pdf"):
            try:
                logger.info(f"Loading example PDF: {pdf_file}")
                
                # Parse PDF
                result = self.pdf_parser.parse_pdf(pdf_file, f"example://{pdf_file.name}")
                
                # Validate and add to store
                validation_report = self.pdf_parser.validate_parsed_data(result)
                
                if validation_report["is_valid"]:
                    await self.data_store.add_quota_result(result)
                    logger.info(f"Successfully loaded example PDF: {pdf_file.name}")
                else:
                    logger.warning(f"Validation failed for {pdf_file.name}: {validation_report['errors']}")
                    
            except Exception as e:
                logger.error(f"Error loading example PDF {pdf_file}: {e}")
    
    def run(self, **kwargs):
        """Run the MCP server."""
        # Set default uvicorn parameters
        run_kwargs = {
            "host": self.host,
            "port": self.port,
            "log_level": "info"
        }
        run_kwargs.update(kwargs)
        
        # Initialize server before running
        asyncio.run(self.initialize())
        
        logger.info(f"Starting MCP server at http://{self.host}:{self.port}")
        logger.info(f"MCP endpoint available at http://{self.host}:{self.port}/mcp")
        logger.info(f"API documentation at http://{self.host}:{self.port}/docs")
        
        uvicorn.run(self.app, **run_kwargs)


# Convenience function for creating and running the server
def create_server(**kwargs) -> MCPServer:
    """Create an MCP server instance."""
    return MCPServer(**kwargs)


def run_server(**kwargs):
    """Create and run an MCP server."""
    server = create_server(**kwargs)
    server.run() 