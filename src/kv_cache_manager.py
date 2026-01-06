"""
K-V Cache Manager for storing query-response pairs
"""
from typing import Dict, Optional, List
from datetime import datetime
import os
import json
import hashlib


class KVCacheManager:
    """
    Manages Key-Value cache for query-response pairs
    """
    
    def __init__(self, cache_dir: str = "database/kv_cache"):
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "cache_index.json")
        self.cache = {}
        self.access_count = {}
        self.load_cache()
    
    def load_cache(self):
        """Load cache from disk"""
        os.makedirs(self.cache_dir, exist_ok=True)
        
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache = data.get('cache', {})
                    self.access_count = data.get('access_count', {})
                print(f"✅ Loaded {len(self.cache)} cached items")
            except Exception as e:
                print(f"⚠️ Error loading cache: {e}")
                self.cache = {}
                self.access_count = {}
    
    def save_cache(self):
        """Save cache to disk"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'cache': self.cache,
                    'access_count': self.access_count
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving cache: {e}")
    
    def _hash_query(self, query: str) -> str:
        """Generate hash for query"""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()
    
    def get(self, query: str) -> Optional[Dict]:
        """
        Get cached response for query
        Returns: {response, context, access_count} or None
        """
        query_hash = self._hash_query(query)
        
        if query_hash in self.cache:
            # Increment access count
            self.access_count[query_hash] = self.access_count.get(query_hash, 0) + 1
            
            cached_item = self.cache[query_hash]
            cached_item['access_count'] = self.access_count[query_hash]
            
            # Update timestamp
            cached_item['last_accessed'] = datetime.now().isoformat()
            
            self.save_cache()
            return cached_item
        
        return None
    
    def put(self, query: str, response: str, context: str = ""):
        """
        Store query-response pair in cache
        """
        query_hash = self._hash_query(query)
        
        self.cache[query_hash] = {
            'query': query,
            'response': response,
            'context': context,
            'created_at': datetime.now().isoformat(),
            'last_accessed': datetime.now().isoformat()
        }
        
        self.access_count[query_hash] = 1
        self.save_cache()
    
    def clear(self):
        """Clear all cache"""
        self.cache = {}
        self.access_count = {}
        self.save_cache()
        print("🗑️ Cache cleared")
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total_size_bytes = len(json.dumps(self.cache).encode('utf-8'))
        
        return {
            'size': len(self.cache),
            'total_items': len(self.cache),  # ✅ Add this
            'size_mb': total_size_bytes / (1024 * 1024),
            'total_accesses': sum(self.access_count.values()),
            'most_accessed': self._get_most_accessed(5),
            'top_queries': self._get_most_accessed(5)  # ✅ Add alias
        }
    
    def _get_most_accessed(self, limit: int = 5) -> List[Dict]:
        """Get most accessed queries"""
        sorted_items = sorted(
            self.access_count.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        result = []
        for query_hash, count in sorted_items:
            if query_hash in self.cache:
                result.append({
                    'query': self.cache[query_hash].get('query', 'Unknown')[:50],
                    'access_count': count
                })
        
        return result
    
    def optimize(self, max_size_mb: float = 100.0) -> Dict:
        """
        Optimize cache by removing least accessed items
        """
        current_size_mb = self.get_stats()['size_mb']
        
        if current_size_mb <= max_size_mb:
            return {
                'freed_mb': 0,
                'removed_items': 0
            }
        
        # Sort by access count (ascending)
        sorted_items = sorted(
            self.access_count.items(),
            key=lambda x: x[1]
        )
        
        removed = 0
        for query_hash, _ in sorted_items:
            if query_hash in self.cache:
                del self.cache[query_hash]
                del self.access_count[query_hash]
                removed += 1
                
                # Check if we've freed enough space
                if self.get_stats()['size_mb'] <= max_size_mb:
                    break
        
        self.save_cache()
        
        new_size_mb = self.get_stats()['size_mb']
        freed_mb = current_size_mb - new_size_mb
        
        return {
            'freed_mb': freed_mb,
            'removed_items': removed
        }
