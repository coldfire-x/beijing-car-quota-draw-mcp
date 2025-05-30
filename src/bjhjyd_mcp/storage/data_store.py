"""
Data storage and management for Beijing car quota lottery results.

Provides in-memory storage with disk persistence for quota results.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import aiofiles
from ..models.quota_result import QuotaResult, QuotaType

logger = logging.getLogger(__name__)


class DataStore:
    """In-memory data store with disk persistence for quota results."""
    
    def __init__(self, storage_dir: Path = Path("data")):
        """
        Initialize the data store.
        
        Args:
            storage_dir: Directory to store persistent data
        """
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(exist_ok=True)
        
        # In-memory storage
        self.quota_results: Dict[str, QuotaResult] = {}
        
        # Index for fast lookups
        self.application_code_index: Dict[str, List[str]] = {}  # code -> [filenames]
        self.id_number_index: Dict[str, List[str]] = {}  # partial_id -> [filenames]
        
        # Metadata
        self.last_update: Optional[datetime] = None
        self.total_entries: int = 0
    
    async def add_quota_result(self, result: QuotaResult) -> None:
        """
        Add a quota result to the store.
        
        Args:
            result: QuotaResult to add
        """
        filename = result.metadata.filename
        logger.info(f"Adding quota result: {filename}")
        
        # Store in memory
        self.quota_results[filename] = result
        
        # Update indexes
        self._update_indexes(filename, result)
        
        # Update metadata
        self.last_update = datetime.now()
        self.total_entries += result.metadata.entry_count
        
        # Persist to disk
        await self._save_result_to_disk(result)
        await self._save_metadata()
        
        logger.info(f"Added {result.metadata.entry_count} entries from {filename}")
    
    def _update_indexes(self, filename: str, result: QuotaResult) -> None:
        """Update search indexes with new result."""
        # Index application codes
        if result.metadata.quota_type == QuotaType.WAITING_LIST:
            for entry in result.waiting_list_entries:
                if entry.application_code not in self.application_code_index:
                    self.application_code_index[entry.application_code] = []
                self.application_code_index[entry.application_code].append(filename)
        
        elif result.metadata.quota_type == QuotaType.SCORE_RANKING:
            for entry in result.score_ranking_entries:
                # Index application code
                if entry.application_code not in self.application_code_index:
                    self.application_code_index[entry.application_code] = []
                self.application_code_index[entry.application_code].append(filename)
                
                # Index partial ID number
                if entry.id_number and len(entry.id_number) >= 10:
                    id_prefix = entry.id_number[:6]
                    id_suffix = entry.id_number[-4:]
                    partial_id = f"{id_prefix}****{id_suffix}"
                    
                    if partial_id not in self.id_number_index:
                        self.id_number_index[partial_id] = []
                    self.id_number_index[partial_id].append(filename)
    
    async def find_by_application_code(self, application_code: str) -> List[Dict[str, Any]]:
        """
        Find entries by application code across all results.
        
        Args:
            application_code: Application code to search for
            
        Returns:
            List of matching entries with source information
        """
        results = []
        
        if application_code in self.application_code_index:
            for filename in self.application_code_index[application_code]:
                if filename in self.quota_results:
                    quota_result = self.quota_results[filename]
                    entry_data = quota_result.find_by_application_code(application_code)
                    
                    if entry_data:
                        entry_data["source_file"] = filename
                        entry_data["source_url"] = quota_result.metadata.source_url
                        entry_data["download_time"] = quota_result.metadata.download_time
                        results.append(entry_data)
        
        return results
    
    async def find_by_partial_id(self, id_prefix: str, id_suffix: str) -> List[Dict[str, Any]]:
        """
        Find entries by partial ID number across all results.
        
        Args:
            id_prefix: First 6 digits of ID number
            id_suffix: Last 4 digits of ID number
            
        Returns:
            List of matching entries with source information
        """
        results = []
        partial_id = f"{id_prefix}****{id_suffix}"
        
        if partial_id in self.id_number_index:
            for filename in self.id_number_index[partial_id]:
                if filename in self.quota_results:
                    quota_result = self.quota_results[filename]
                    entry_list = quota_result.find_by_partial_id(id_prefix, id_suffix)
                    
                    for entry_data in entry_list:
                        entry_data["source_file"] = filename
                        entry_data["source_url"] = quota_result.metadata.source_url
                        entry_data["download_time"] = quota_result.metadata.download_time
                        results.append(entry_data)
        
        return results
    
    async def find_by_id_prefix_or_suffix(self, id_prefix: Optional[str] = None, id_suffix: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find entries by ID prefix and/or suffix across all results.
        
        Args:
            id_prefix: First 6 digits of ID number (optional)
            id_suffix: Last 4 digits of ID number (optional)
            
        Returns:
            List of matching entries with source information
        """
        if not id_prefix and not id_suffix:
            return []
        
        results = []
        
        # If both prefix and suffix provided, use exact match
        if id_prefix and id_suffix:
            return await self.find_by_partial_id(id_prefix, id_suffix)
        
        # Search all indexed ID numbers for matches
        for partial_id, filenames in self.id_number_index.items():
            # partial_id format: "123456****7890"
            current_prefix = partial_id[:6]
            current_suffix = partial_id[-4:]
            
            # Check if current ID matches search criteria
            match = False
            if id_prefix and current_prefix == id_prefix:
                match = True
            elif id_suffix and current_suffix == id_suffix:
                match = True
            
            if match:
                # Get entries from matching files
                for filename in filenames:
                    if filename in self.quota_results:
                        quota_result = self.quota_results[filename]
                        entry_list = quota_result.find_by_partial_id(current_prefix, current_suffix)
                        
                        for entry_data in entry_list:
                            entry_data["source_file"] = filename
                            entry_data["source_url"] = quota_result.metadata.source_url
                            entry_data["download_time"] = quota_result.metadata.download_time
                            results.append(entry_data)
        
        return results
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored data."""
        stats = {
            "total_files": len(self.quota_results),
            "total_entries": self.total_entries,
            "last_update": self.last_update,
            "application_codes_indexed": len(self.application_code_index),
            "id_numbers_indexed": len(self.id_number_index),
            "files_by_type": {},
            "files": []
        }
        
        # Count by type
        for filename, result in self.quota_results.items():
            quota_type = result.metadata.quota_type.value
            if quota_type not in stats["files_by_type"]:
                stats["files_by_type"][quota_type] = 0
            stats["files_by_type"][quota_type] += 1
            
            # Add file info
            stats["files"].append({
                "filename": filename,
                "type": quota_type,
                "entries": result.metadata.entry_count,
                "source_url": result.metadata.source_url,
                "download_time": result.metadata.download_time
            })
        
        return stats
    
    async def load_from_disk(self) -> None:
        """Load stored results from disk."""
        logger.info("Loading quota results from disk")
        
        results_dir = self.storage_dir / "results"
        if not results_dir.exists():
            logger.info("No stored results found")
            return
        
        loaded_count = 0
        
        for result_file in results_dir.glob("*.json"):
            try:
                async with aiofiles.open(result_file, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                
                # Reconstruct QuotaResult object
                result = QuotaResult.parse_obj(data)
                
                # Add to store
                filename = result.metadata.filename
                self.quota_results[filename] = result
                self._update_indexes(filename, result)
                self.total_entries += result.metadata.entry_count
                
                loaded_count += 1
                
            except Exception as e:
                logger.error(f"Error loading result from {result_file}: {e}")
        
        # Load metadata
        await self._load_metadata()
        
        logger.info(f"Loaded {loaded_count} quota results from disk")
    
    async def _save_result_to_disk(self, result: QuotaResult) -> None:
        """Save a single result to disk."""
        results_dir = self.storage_dir / "results"
        results_dir.mkdir(exist_ok=True)
        
        filename = result.metadata.filename
        result_file = results_dir / f"{filename}.json"
        
        # Convert to dict for JSON serialization
        data = result.dict()
        
        async with aiofiles.open(result_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    
    async def _save_metadata(self) -> None:
        """Save store metadata to disk."""
        metadata = {
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "total_entries": self.total_entries,
            "total_files": len(self.quota_results)
        }
        
        metadata_file = self.storage_dir / "metadata.json"
        
        async with aiofiles.open(metadata_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(metadata, ensure_ascii=False, indent=2))
    
    async def _load_metadata(self) -> None:
        """Load store metadata from disk."""
        metadata_file = self.storage_dir / "metadata.json"
        
        if not metadata_file.exists():
            return
        
        try:
            async with aiofiles.open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.loads(await f.read())
            
            if metadata.get("last_update"):
                self.last_update = datetime.fromisoformat(metadata["last_update"])
            
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
    
    async def clear_all(self) -> None:
        """Clear all stored data."""
        logger.info("Clearing all stored data")
        
        self.quota_results.clear()
        self.application_code_index.clear()
        self.id_number_index.clear()
        self.last_update = None
        self.total_entries = 0
        
        # Clear disk storage
        results_dir = self.storage_dir / "results"
        if results_dir.exists():
            for result_file in results_dir.glob("*.json"):
                result_file.unlink()
        
        metadata_file = self.storage_dir / "metadata.json"
        if metadata_file.exists():
            metadata_file.unlink()
    
    def get_result_by_filename(self, filename: str) -> Optional[QuotaResult]:
        """Get a specific result by filename."""
        return self.quota_results.get(filename)
    
    def list_filenames(self) -> List[str]:
        """Get list of all stored filenames."""
        return list(self.quota_results.keys()) 