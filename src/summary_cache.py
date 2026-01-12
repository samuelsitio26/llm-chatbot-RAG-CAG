"""
Summary Cache for document chunks
Pre-generate summaries for faster context retrieval
"""

import os
import hashlib
import json
from datetime import datetime
from typing import Optional, Dict


class SummaryCache:
    """
    Cache for document summaries
    Speeds up context retrieval by using pre-generated summaries
    """
    
    def __init__(self, cache_dir: str = "../database/summary_cache"):
        self.cache_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), cache_dir)
        )
        os.makedirs(self.cache_dir, exist_ok=True)
        self.summaries = {}
        self.index_file = os.path.join(self.cache_dir, "summary_index.json")
        self._load_index()
    
    def _load_index(self):
        """Load summary index"""
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    self.summaries = json.load(f)
            except:
                self.summaries = {}
    
    def _save_index(self):
        """Save summary index"""
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self.summaries, f, indent=2, ensure_ascii=False)
    
    def _generate_chunk_id(self, text: str) -> str:
        """Generate unique ID for chunk"""
        return hashlib.md5(text.encode()).hexdigest()
    
    def get_summary(self, text: str) -> Optional[str]:
        """Get cached summary for a chunk"""
        chunk_id = self._generate_chunk_id(text)
        
        if chunk_id in self.summaries:
            return self.summaries[chunk_id]['summary']
        
        return None
    
    def save_summary(self, text: str, summary: str):
        """Save summary to cache"""
        chunk_id = self._generate_chunk_id(text)
        
        self.summaries[chunk_id] = {
            'summary': summary,
            'text_preview': text[:100] + "..." if len(text) > 100 else text,
            'text_length': len(text)
        }
        
        self._save_index()
    
    def get_stats(self) -> Dict:
        """Get summary cache statistics"""
        return {
            'total_summaries': len(self.summaries),
            'cache_size_kb': os.path.getsize(self.index_file) / 1024 if os.path.exists(self.index_file) else 0
        }
    
    def add_summary(self, chunk_id: str, content: str, summary: str):
        """Add a summary to cache"""
        self.summaries[chunk_id] = {
            'content': content[:200],
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        }
        self._save_index()
    
    def clear(self):
        """Clear all summaries"""
        self.summaries = {}
        self._save_index()
