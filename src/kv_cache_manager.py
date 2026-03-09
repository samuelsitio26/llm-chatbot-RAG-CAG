"""
K-V Cache Manager for storing query-response pairs
Includes lifecycle policy support:
  - age > 21 days AND access_count < 5  → candidate for deletion
  - access_count >= 5 AND net_likes >= 1 → candidate for FAQ promotion
  - staging entries: regen_count tracked, max 3 regenerations before needs_review
"""
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
import os
import json
import hashlib


class KVCacheManager:
    """
    Manages Key-Value cache for query-response pairs
    """

    MAX_REGEN = 3  # maximum regeneration attempts before marking needs_review
    
    def __init__(self, cache_dir: str = "database/kv_cache"):
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "cache_index.json")
        self.cache = {}          # confirmed entries – served directly to users
        self.staging = {}        # provisional entries – waiting for quality signal
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
                    self.staging = data.get('staging', {})
                staging_count = len(self.staging)
                print(f"✅ Loaded {len(self.cache)} confirmed + {staging_count} staging items")
            except Exception as e:
                print(f"⚠️ Error loading cache: {e}")
                self.cache = {}
                self.access_count = {}
                self.staging = {}
    
    def save_cache(self):
        """Save cache to disk"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'cache': self.cache,
                    'access_count': self.access_count,
                    'staging': self.staging,
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving cache: {e}")
    
    def _hash_query(self, query: str) -> str:
        """Generate hash for query — strips emojis/symbols so variants hash equally."""
        import re
        # Remove emoji and non-alphanumeric, non-space characters, then normalise whitespace
        cleaned = re.sub(r'[^\w\s]', ' ', query, flags=re.UNICODE)
        cleaned = re.sub(r'\s+', ' ', cleaned).lower().strip()
        return hashlib.md5(cleaned.encode()).hexdigest()
    
    def get(self, query: str) -> Optional[Dict]:
        """
        Get cached response for query.
        1. Check confirmed cache first.
        2. Fall back to staging cache (increment staging_access, try auto-promote).
        Returns: {response, context, access_count, from_staging?} or None
        """
        query_hash = self._hash_query(query)

        # ── 1) Confirmed cache ──────────────────────────────────────────────
        if query_hash in self.cache:
            self.access_count[query_hash] = self.access_count.get(query_hash, 0) + 1
            cached_item = self.cache[query_hash]
            cached_item['access_count'] = self.access_count[query_hash]
            cached_item['last_accessed'] = datetime.now().isoformat()
            self.save_cache()
            return cached_item

        # ── 2) Staging cache ─────────────────────────────────────────────
        if query_hash in self.staging:
            entry = self.staging[query_hash]

            # Never serve entries flagged for review
            if entry.get('status') == 'needs_review':
                return None

            net_likes = entry.get('total_likes', 0) - entry.get('total_dislikes', 0)

            # Disliked too many times → don’t serve, will be garbage-collected
            if net_likes <= -3:
                return None

            # Increment staging access counter
            entry['staging_access'] = entry.get('staging_access', 0) + 1
            entry['last_accessed'] = datetime.now().isoformat()

            # Auto-promote: seen ≥5 times by different users AND net positive
            if entry['staging_access'] >= 5 and net_likes >= 1:
                self._promote_staging_to_confirmed(query_hash)
                if query_hash in self.cache:
                    promoted = self.cache[query_hash]
                    promoted['access_count'] = self.access_count.get(query_hash, 1)
                    return promoted

            self.save_cache()
            # Serve staging entry (provisional) – marked so caller knows it’s not confirmed
            return {
                **entry,
                'from_staging': True,
                'access_count': entry['staging_access'],
            }

        return None
    
    def put(self, query: str, response: str, context: str = ""):
        """
        Store query-response pair in STAGING cache.
        It will be promoted to confirmed cache only after quality validation.
        """
        query_hash = self._hash_query(query)

        # Don’t overwrite existing confirmed entry
        if query_hash in self.cache:
            return

        # Update or create staging entry
        existing = self.staging.get(query_hash, {})
        self.staging[query_hash] = {
            'query': query,
            'response': response,
            'context': context,
            'created_at': existing.get('created_at', datetime.now().isoformat()),
            'last_accessed': datetime.now().isoformat(),
            'source': 'rag_staging',
            # Quality tracking
            'staging_access':  existing.get('staging_access', 0),
            'total_likes':     existing.get('total_likes', 0),
            'total_dislikes':  existing.get('total_dislikes', 0),
            # Regeneration control
            'regen_count':     existing.get('regen_count', 0),
            'status':          existing.get('status', 'unverified'),  # unverified | trusted | low_confidence | needs_review
        }
        self.save_cache()

    # ------------------------------------------------------------------
    # Staging helpers
    # ------------------------------------------------------------------

    def _promote_staging_to_confirmed(self, query_hash: str) -> bool:
        """Move a staging entry to the confirmed cache."""
        if query_hash not in self.staging:
            return False

        entry = self.staging.pop(query_hash)
        self.cache[query_hash] = {
            'query':        entry['query'],
            'response':     entry['response'],
            'context':      entry.get('context', ''),
            'created_at':   entry.get('created_at', datetime.now().isoformat()),
            'last_accessed': datetime.now().isoformat(),
            'source':       'confirmed_cache',
            'total_likes':  entry.get('total_likes', 0),
            'total_dislikes': entry.get('total_dislikes', 0),
        }
        self.access_count[query_hash] = entry.get('staging_access', 1)
        self.save_cache()
        print(f"⭐ Promoted to confirmed cache: {entry.get('query', '')[:60]}")
        return True

    def record_feedback(self, query_hash: str, rating: int) -> Dict:
        """
        Record user feedback (like = +1, dislike = -1) for a cache entry.

        Returns a Dict describing the outcome:
          {
            "found":        bool,
            "action":       "none" | "trusted" | "promoted" | "regen" | "needs_review",
            "query":        str,   # original query — needed to re-run RAG on dislike
            "old_response": str,   # current cached response — used for quality comparison
            "regen_count":  int,   # how many times this entry has been regenerated
          }
        """
        NOT_FOUND = {"found": False, "action": "none", "query": "", "old_response": "", "regen_count": 0}

        # ── Staging entry ────────────────────────────────────────────────
        if query_hash in self.staging:
            entry = self.staging[query_hash]

            if rating > 0:
                entry['total_likes'] = entry.get('total_likes', 0) + 1
                net_likes = entry.get('total_likes', 0) - entry.get('total_dislikes', 0)
                # Enough positive signal → promote
                promoted = False
                if entry.get('staging_access', 0) >= 3 and net_likes >= 1:
                    promoted = self._promote_staging_to_confirmed(query_hash)
                if not promoted:
                    entry['status'] = 'trusted'
                    self.save_cache()
                action = 'promoted' if promoted else 'trusted'
                print(f"👍 Feedback (staging LIKE): net={net_likes:+d}, action={action}")
                return {"found": True, "action": action, "query": entry.get('query', ''),
                        "old_response": entry.get('response', ''), "regen_count": entry.get('regen_count', 0)}

            else:  # dislike
                entry['total_dislikes'] = entry.get('total_dislikes', 0) + 1
                regen_count = entry.get('regen_count', 0)

                if regen_count >= self.MAX_REGEN:
                    # Reached regen limit → lock entry
                    entry['status'] = 'needs_review'
                    self.save_cache()
                    print(f"🔒 Max regen reached ({self.MAX_REGEN}x) — marked needs_review: {entry.get('query', '')[:50]}")
                    return {"found": True, "action": "needs_review", "query": entry.get('query', ''),
                            "old_response": entry.get('response', ''), "regen_count": regen_count}

                # Under limit → signal caller to regenerate
                self.save_cache()
                print(f"🔄 Dislike on staging — requesting regen #{regen_count + 1}: {entry.get('query', '')[:50]}")
                return {"found": True, "action": "regen", "query": entry.get('query', ''),
                        "old_response": entry.get('response', ''), "regen_count": regen_count}

        # ── Confirmed entry ──────────────────────────────────────────────
        if query_hash in self.cache:
            entry = self.cache[query_hash]
            if rating > 0:
                entry['total_likes'] = entry.get('total_likes', 0) + 1
            else:
                entry['total_dislikes'] = entry.get('total_dislikes', 0) + 1
            self.save_cache()
            print(f"👍 Feedback (confirmed): rating={rating:+d}")
            return {"found": True, "action": "none", "query": entry.get('query', ''),
                    "old_response": entry.get('response', ''), "regen_count": 0}

        print(f"⚠️ record_feedback: hash {query_hash[:8]}... not found")
        return NOT_FOUND

    def update_after_regen(
        self, query_hash: str, new_response: str, context: str, old_response: str
    ) -> Dict:
        """
        Called after a regeneration attempt.
        Compares new_response vs old_response and decides whether to replace.

        Quality heuristic:
          - New response must be ≥10% longer in character count to be considered 'better'

        Returns:
          {"replaced": bool, "status": str, "regen_count": int}
        """
        if query_hash not in self.staging:
            return {"replaced": False, "status": "not_found", "regen_count": 0}

        entry      = self.staging[query_hash]
        new_len    = len(new_response.strip())
        old_len    = len(old_response.strip())
        regen_count = entry.get('regen_count', 0) + 1  # count this attempt

        if new_len > old_len * 1.1:  # new response is meaningfully longer
            # Replace with better response; reset dislike counter
            entry['response']          = new_response
            entry['context']           = context
            entry['regen_count']       = regen_count
            entry['last_regenerated']  = datetime.now().isoformat()
            entry['status']            = 'unverified'  # needs fresh validation
            entry['total_dislikes']    = 0             # fresh start for new response
            new_status = 'unverified'
            replaced   = True
            print(f"✅ Regen #{regen_count}: replaced (new={new_len} chars > old={old_len} chars)")
        else:
            # Not better enough → keep old, mark low confidence
            entry['regen_count']      = regen_count
            entry['last_regenerated'] = datetime.now().isoformat()
            if regen_count >= self.MAX_REGEN:
                entry['status'] = 'needs_review'
                print(f"🔒 Regen #{regen_count}: max reached — needs_review (new={new_len}, old={old_len})")
            else:
                entry['status'] = 'low_confidence'
                print(f"⚠️ Regen #{regen_count}: not better — low_confidence (new={new_len}, old={old_len})")
            new_status = entry['status']
            replaced   = False

        self.save_cache()
        return {"replaced": replaced, "status": new_status, "regen_count": regen_count}
    
    def update_entry(self, query_hash: str, new_response: str) -> bool:
        """Replace the cached response for a given hash (used after user chooses regenerated variant)."""
        if query_hash in self.staging:
            self.staging[query_hash]['response'] = new_response
            self.staging[query_hash]['last_regenerated'] = datetime.now().isoformat()
            self.staging[query_hash]['status'] = 'unverified'
            self.save_cache()
            print(f"🔄 Staging entry updated with chosen answer: {query_hash[:8]}...")
            return True
        if query_hash in self.cache:
            self.cache[query_hash]['response'] = new_response
            self.cache[query_hash]['last_accessed'] = datetime.now().isoformat()
            self.save_cache()
            print(f"🔄 Confirmed entry updated with chosen answer: {query_hash[:8]}...")
            return True
        return False

    def clear(self):
        """Clear all cache (confirmed + staging)"""
        self.cache = {}
        self.staging = {}
        self.access_count = {}
        self.save_cache()
        print("🗑️ Cache cleared (confirmed + staging)")
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total_size_bytes = len(json.dumps(self.cache).encode('utf-8'))
        
        return {
            'size': len(self.cache),
            'total_items': len(self.cache),
            'staging_items': len(self.staging),
            'size_mb': total_size_bytes / (1024 * 1024),
            'total_accesses': sum(self.access_count.values()),
            'most_accessed': self._get_most_accessed(5),
            'top_queries': self._get_most_accessed(5)
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

    # ============================================================
    # LIFECYCLE POLICY
    # ============================================================

    def get_lifecycle_candidates(
        self,
        max_age_days: int = 21,
        min_access_for_promote: int = 5,
    ) -> Dict:
        """
        Categorize all cache entries into:
          - to_delete  : last_accessed > max_age_days AND access_count < min_access_for_promote
          - to_promote : access_count >= min_access_for_promote  (→ add to FAQ)
          - to_keep    : everything else

        Returns:
            {
              "to_delete":  [ {hash, query, access_count, age_days}, ... ],
              "to_promote": [ {hash, query, response, access_count, age_days}, ... ],
              "to_keep":    [ {hash, query, access_count, age_days}, ... ],
            }
        """
        now = datetime.now()
        cutoff = timedelta(days=max_age_days)

        to_delete:  List[Dict] = []
        to_promote: List[Dict] = []
        to_keep:    List[Dict] = []

        for query_hash, item in self.cache.items():
            count = self.access_count.get(query_hash, item.get('access_count', 0))

            # Parse last-accessed timestamp (fall back to created_at)
            try:
                ts_str = item.get('last_accessed') or item.get('created_at')
                last_accessed = datetime.fromisoformat(ts_str)
            except Exception:
                last_accessed = now - timedelta(days=999)  # treat as very old

            age_days = (now - last_accessed).days
            query_text = item.get('query', '')

            entry_base = {
                'hash':         query_hash,
                'query':        query_text,
                'access_count': count,
                'age_days':     age_days,
            }

            if count >= min_access_for_promote:
                # Require net positive feedback to promote to FAQ
                net_likes = item.get('total_likes', 0) - item.get('total_dislikes', 0)
                if net_likes >= 1:
                    to_promote.append({**entry_base, 'response': item.get('response', '')})
                elif net_likes < 0:
                    to_delete.append({**entry_base, 'reason': 'popular but disliked'})
                else:
                    to_keep.append({**entry_base, 'reason': f'popular but no quality signal (net_likes={net_likes})'})
            elif age_days > max_age_days and count < min_access_for_promote:
                to_delete.append(entry_base)
            else:
                to_keep.append(entry_base)

        return {
            'to_delete':  to_delete,
            'to_promote': to_promote,
            'to_keep':    to_keep,
        }

    def delete_entries(self, hashes: List[str]) -> int:
        """Delete specific cache entries by hash. Returns count deleted."""
        removed = 0
        for h in hashes:
            if h in self.cache:
                del self.cache[h]
                self.access_count.pop(h, None)
                removed += 1
        if removed:
            self.save_cache()
        return removed

    def pre_populate_from_faq(self, faq_list: List[Dict]) -> Dict:
        """
        Pre-populate cache directly from FAQ Q+A pairs (no LLM call needed).
        Only processes entries that have both 'question' and 'answer' fields.

        Args:
            faq_list: list of FAQ dicts with at least 'question' and 'answer' keys

        Returns:
            {'added': int, 'skipped': int}
        """
        added = skipped = 0

        for faq in faq_list:
            question = faq.get('question', '').strip()
            answer   = faq.get('answer',   '').strip()

            if not question or not answer:
                skipped += 1
                continue

            query_hash = self._hash_query(question)

            if query_hash in self.cache:
                skipped += 1
                continue

            self.cache[query_hash] = {
                'query':        question,
                'response':     answer,
                'context':      faq.get('context', ''),
                'created_at':   datetime.now().isoformat(),
                'last_accessed': datetime.now().isoformat(),
                'source':       'faq_prepopulate',
            }
            self.access_count[query_hash] = 0
            added += 1

        if added:
            self.save_cache()

        print(f"📥 FAQ pre-populate: {added} added, {skipped} skipped (already cached / no answer)")
        return {'added': added, 'skipped': skipped}
