"""
KV Cache Manager - Dual-Layer Query Response Cache
Part of Modified Hybrid CAG-RAG System (May 2026)

Architecture Role:
  - KV Cache = Transformer cache layer (contextual reuse of computed attention states)
  - Dual-layer lifecycle: candidate → staging → confirmed
  - Used alongside FAQ Cache (semantic response reuse) and RAG (retrieval)
  
Lifecycle Policy:
  - Candidate stage: First query, no evidence yet
  - Staging stage: Awaiting validation from RAG re-retrieval
  - Confirmed stage: Validated after 3+ regenerations with 2+ consistency hits
  - TTL-based expiry: 30 days (staging), 90 days (confirmed)
"""

import hashlib
import json
import os
from difflib import SequenceMatcher
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


class KVCacheManager:
    """
    Manages dual-layer cache for query-response pairs with quality gating.
    
    Used by CAG system to:
      1. Cache responses from RAG pipeline
      2. Track validation/confidence signals
      3. Promote high-confidence entries to confirmed status
      4. Prevent serving unvalidated provisional entries
    
    NOT a replacement for FAQ cache - that's a separate semantic response layer.
    """

    MAX_REGEN = 3  # maximum regeneration attempts before marking needs_review

    # Research mode: do not directly serve first-time staging entries.
    # Toggle with env var CAG_TRUST_GATING=0 for baseline comparison.
    CANDIDATE_MIN_EVIDENCE = 2
    CONSISTENCY_THRESHOLD = 0.72
    PROBATION_MIN_TRUST = 0.60

    # TTL (Time To Live) untuk cache entries — informasi wisata bisa berubah
    # (harga tiket, jam buka, fasilitas baru) sehingga cache perlu direfresh.
    # Staging entries lebih pendek karena belum divalidasi kualitasnya.
    STAGING_TTL_DAYS = 30  # Entry staging expire setelah 30 hari
    CONFIRMED_TTL_DAYS = 90  # Entry confirmed expire setelah 90 hari

    def __init__(self, cache_dir: str = "database/kv_cache"):
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "cache_index.json")
        self.cache = {}  # confirmed entries – served directly to users
        self.staging = {}  # provisional entries – waiting for quality signal
        self.access_count = {}
        self.enable_trust_gating = os.getenv("CAG_TRUST_GATING", "1") != "0"
        self.research_metrics = {
            "candidate_blocked_requests": 0,
            "candidate_to_probation": 0,
            "probation_served": 0,
            "probation_to_confirmed": 0,
        }
        self.load_cache()

    def load_cache(self):
        """Load cache from disk"""
        os.makedirs(self.cache_dir, exist_ok=True)

        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                    self.cache = data.get("cache", {})
                    self.access_count = data.get("access_count", {})
                    self.staging = data.get("staging", {})
                    self.research_metrics.update(data.get("research_metrics", {}))
                staging_count = len(self.staging)
                print(
                    f"✅ Loaded {len(self.cache)} confirmed + {staging_count} staging items"
                )
            except Exception as e:
                print(f"⚠️ Error loading cache: {e}")
                self.cache = {}
                self.access_count = {}
                self.staging = {}

    def save_cache(self):
        """Save cache to disk"""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "cache": self.cache,
                        "access_count": self.access_count,
                        "staging": self.staging,
                        "research_metrics": self.research_metrics,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as e:
            print(f"⚠️ Error saving cache: {e}")

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _compute_trust_score(self, retrieval_quality: Optional[Dict]) -> float:
        """Compute trust score used by research gating.

        trust = 0.50 * hybrid + 0.30 * margin + 0.20 * grounding
        Missing fields fall back to conservative defaults.
        """
        if not retrieval_quality:
            return 0.50

        hybrid = self._clamp01(retrieval_quality.get("hybrid_score", 0.0))
        margin = self._clamp01(retrieval_quality.get("margin_score", 0.0))
        grounding = self._clamp01(retrieval_quality.get("grounding_score", 0.0))
        return self._clamp01(0.50 * hybrid + 0.30 * margin + 0.20 * grounding)

    def _response_similarity(self, left: str, right: str) -> float:
        """Approximate textual consistency between two generated answers."""
        l_norm = " ".join((left or "").lower().split())
        r_norm = " ".join((right or "").lower().split())
        if not l_norm or not r_norm:
            return 0.0
        return SequenceMatcher(None, l_norm, r_norm).ratio()

    def _hash_query(self, query: str, context_key: str = "") -> str:
        """Generate hash for query with optional context_key (Dual-Layer Cache Key).

        Dual-layer strategy:
          Layer 1 — Context-Free  (context_key = ""):
            hash = MD5( normalize(query) )
            → Digunakan untuk query eksplisit yang menyebut entitas secara langsung.
            → Ex: "harga tiket Pantai Parbaba?" — jawaban stabil lintas percakapan.

          Layer 2 — Context-Aware (context_key ≠ ""):
            hash = MD5( normalize(query) + "#CTX#" + normalize(context_key) )
            → Digunakan untuk follow-up query agar tidak terjadi collision lintas konteks.
            → Ex: "bagaimana fasilitasnya?" + ctx "Pantai Parbaba"
                ≠ "bagaimana fasilitasnya?" + ctx "Hotel Labersa"
            → Mencegah respons satu konteks disajikan ke konteks percakapan berbeda.

        Referensi: Park et al. (2023) Generative Agents — konteks percakapan sebagai
        dimensi state yang terpisah dari query literal.
        """
        import re

        cleaned = re.sub(r"[^\w\s]", " ", query, flags=re.UNICODE)
        cleaned = re.sub(r"\s+", " ", cleaned).lower().strip()

        if context_key:
            ctx = re.sub(r"[^\w\s]", " ", context_key, flags=re.UNICODE)
            ctx = re.sub(r"\s+", " ", ctx).lower().strip()
            combined = f"{cleaned}#CTX#{ctx}"
        else:
            combined = cleaned

        return hashlib.md5(combined.encode()).hexdigest()

    def get(self, query: str, context_key: str = "") -> Optional[Dict]:
        """
        Get cached response for query.

        Args:
            query:       Teks query pengguna.
            context_key: Entitas aktif percakapan (last_place) untuk Dual-Layer lookup.
                         Kosong ("") → context-free lookup (Layer 1).
                         Berisi nama entitas → context-aware lookup (Layer 2).

        Lookup order:
          1. Confirmed cache (Layer 2 jika context_key, lalu Layer 1 sebagai fallback)
          2. Staging cache  (urutan yang sama)

        Returns: {response, context, access_count, from_staging?} or None
        """
        # Context-aware hash (Layer 2) — coba dulu jika ada context_key
        query_hash = self._hash_query(query, context_key=context_key)

        # Jika context-aware miss DAN context_key ada → fallback ke context-free (Layer 1)
        # Ini mencegah cache miss palsu ketika entri di-store sebelum fitur context_key ditambahkan.
        _fallback_hash = self._hash_query(query) if context_key else None

        # ── 1) Confirmed cache ──────────────────────────────────────────────
        # Coba context-aware hash dulu; jika miss dan ada fallback, coba context-free.
        _effective_hash = query_hash
        if (
            query_hash not in self.cache
            and _fallback_hash
            and _fallback_hash in self.cache
        ):
            _effective_hash = _fallback_hash
        if _effective_hash in self.cache:
            query_hash = _effective_hash  # gunakan hash yang hit
            # ── TTL check for confirmed cache ─────────────────────────────────
            cached_item = self.cache[query_hash]
            created_str = cached_item.get("created_at", "")
            if created_str:
                try:
                    age = datetime.now() - datetime.fromisoformat(created_str)
                    if age.days > self.CONFIRMED_TTL_DAYS:
                        # Entry expired → remove from confirmed, let system re-generate
                        del self.cache[query_hash]
                        if query_hash in self.access_count:
                            del self.access_count[query_hash]
                        self.save_cache()
                        print(
                            f"🕐 Confirmed cache expired (age={age.days}d): "
                            f"{cached_item.get('query', '')[:50]}"
                        )
                        # Fall through to staging check below
                    else:
                        self.access_count[query_hash] = (
                            self.access_count.get(query_hash, 0) + 1
                        )
                        cached_item["access_count"] = self.access_count[query_hash]
                        cached_item["last_accessed"] = datetime.now().isoformat()
                        self.save_cache()
                        print(f"✅ [KV Cache - Confirmed] Reusing validated response for: '{query[:50]}...'")
                        return cached_item
                except (ValueError, TypeError):
                    pass
            # If TTL parse failed, still serve the entry normally
            if query_hash in self.cache:
                self.access_count[query_hash] = self.access_count.get(query_hash, 0) + 1
                cached_item = self.cache[query_hash]
                cached_item["access_count"] = self.access_count[query_hash]
                cached_item["last_accessed"] = datetime.now().isoformat()
                self.save_cache()
                print(f"✅ [KV Cache - Confirmed] Reusing validated response for: '{query[:50]}...'")
                return cached_item

        # ── 2) Staging cache ─────────────────────────────────────────────
        # Sama: coba context-aware dulu, fallback ke context-free.
        _eff_staging = query_hash
        if (
            query_hash not in self.staging
            and _fallback_hash
            and _fallback_hash in self.staging
        ):
            _eff_staging = _fallback_hash
        query_hash = _eff_staging  # gunakan hash yang hit di staging

        if query_hash in self.staging:
            entry = self.staging[query_hash]

            # ── TTL check for staging cache ────────────────────────────────
            staging_created = entry.get("created_at", "")
            if staging_created:
                try:
                    staging_age = datetime.now() - datetime.fromisoformat(
                        staging_created
                    )
                    if staging_age.days > self.STAGING_TTL_DAYS:
                        del self.staging[query_hash]
                        self.save_cache()
                        print(
                            f"🕐 Staging cache expired (age={staging_age.days}d): "
                            f"{entry.get('query', '')[:50]}"
                        )
                        return None
                except (ValueError, TypeError):
                    pass

            # Never serve entries flagged for review
            if entry.get("status") == "needs_review":
                return None

            cache_stage = entry.get("stage", "candidate")
            
            # Design: Do NOT serve staging entries directly.
            # Staging entries must be re-validated via RAG to ensure quality before confirmation.
            # This is intentional quality gating, not a bug.
            print(f"🚦 [Quality Gate] Staging entry for '{query[:50]}...' requires RAG re-validation. Requesting fresh retrieval.")
            entry["candidate_block_count"] = entry.get("candidate_block_count", 0) + 1
            entry["last_accessed"] = datetime.now().isoformat()
            self.research_metrics["candidate_blocked_requests"] = (
                self.research_metrics.get("candidate_blocked_requests", 0) + 1
            )
            self.save_cache()
            return None

    def put(
        self,
        query: str,
        response: str,
        context: str = "",
        context_key: str = "",
        retrieval_quality: Optional[Dict] = None,
        source: str = "rag_staging",
    ):
        """
        Store query-response pair in STAGING cache.

        Args:
            query:       Teks query pengguna.
            response:    Respons yang akan di-cache.
            context:     Snippet konteks dokumen (opsional, untuk metadata).
            context_key: Entitas aktif percakapan untuk Dual-Layer storage.
                         Jika diisi → entry disimpan dengan context-aware hash.
                         Ini memastikan follow-up queries di konteks berbeda
                         tidak saling menimpa cache entry satu sama lain.

        Quality gate:
          Entry hanya masuk STAGING, bukan langsung ke confirmed cache.
          Promosi ke confirmed memerlukan: staging_access ≥ 5 AND net_likes ≥ 1.
        """
        query_hash = self._hash_query(query, context_key=context_key)
        trust_score = self._compute_trust_score(retrieval_quality)
        effective_source = source
        if context == "from_faq" and source == "rag_staging":
            effective_source = "faq_seed"

        # Don’t overwrite existing confirmed entry
        if query_hash in self.cache:
            return

        # Update or create staging entry
        existing = self.staging.get(query_hash, {})
        existing_stage = existing.get("stage", "candidate")
        evidence_count = int(existing.get("evidence_count", 0))
        consistency_hits = int(existing.get("consistency_hits", 0))

        if existing:
            evidence_count += 1
            prev_response = existing.get("response", "")
            sim = self._response_similarity(prev_response, response)
            if sim >= self.CONSISTENCY_THRESHOLD:
                consistency_hits += 1

            # Keep a more informative response when two retrieval attempts disagree.
            if sim < self.CONSISTENCY_THRESHOLD and len(response.strip()) <= len(prev_response.strip()):
                response = prev_response

        else:
            evidence_count = 1

        stage = existing_stage
        if not self.enable_trust_gating:
            stage = "probation"
        elif effective_source == "faq_seed":
            # Curated FAQ knowledge can start from probation.
            stage = "probation"
        elif evidence_count >= 3 and consistency_hits >= 2:
            # 3rd Exact Match and consistent -> Promote to confirmed
            print(f"⭐ Auto-promoting {query_hash[:8]} to confirmed (consistency_hits={consistency_hits})")
            self.cache[query_hash] = {
                "query": query,
                "response": response,
                "context": context,
                "created_at": existing.get("created_at", datetime.now().isoformat()),
                "last_accessed": datetime.now().isoformat(),
                "source": "confirmed_cache",
                "total_likes": existing.get("total_likes", 0),
                "total_dislikes": existing.get("total_dislikes", 0),
            }
            self.access_count[query_hash] = existing.get("staging_access", 1) + 1
            if query_hash in self.staging:
                del self.staging[query_hash]
            self.research_metrics["probation_to_confirmed"] = (
                self.research_metrics.get("probation_to_confirmed", 0) + 1
            )
            self.save_cache()
            return
        elif (
            existing_stage == "candidate"
            and evidence_count >= self.CANDIDATE_MIN_EVIDENCE
            and (
                consistency_hits >= 1
                or max(float(existing.get("trust_score", 0.0)), trust_score)
                >= self.PROBATION_MIN_TRUST
            )
        ):
            stage = "probation"
            self.research_metrics["candidate_to_probation"] = (
                self.research_metrics.get("candidate_to_probation", 0) + 1
            )

        self.staging[query_hash] = {
            "query": query,
            "response": response,
            "context": context,
            "created_at": existing.get("created_at", datetime.now().isoformat()),
            "last_accessed": datetime.now().isoformat(),
            "source": effective_source,
            # Quality tracking
            "staging_access": existing.get("staging_access", 0),
            "total_likes": existing.get("total_likes", 0),
            "total_dislikes": existing.get("total_dislikes", 0),
            "stage": stage,
            "trust_score": max(float(existing.get("trust_score", 0.0)), trust_score),
            "evidence_count": evidence_count,
            "consistency_hits": consistency_hits,
            # Regeneration control
            "regen_count": existing.get("regen_count", 0),
            "status": existing.get(
                "status", "unverified"
            ),  # unverified | trusted | low_confidence | needs_review
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
            "query": entry["query"],
            "response": entry["response"],
            "context": entry.get("context", ""),
            "created_at": entry.get("created_at", datetime.now().isoformat()),
            "last_accessed": datetime.now().isoformat(),
            "source": "confirmed_cache",
            "total_likes": entry.get("total_likes", 0),
            "total_dislikes": entry.get("total_dislikes", 0),
        }
        self.access_count[query_hash] = entry.get("staging_access", 1)
        self.research_metrics["probation_to_confirmed"] = (
            self.research_metrics.get("probation_to_confirmed", 0) + 1
        )
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
        NOT_FOUND = {
            "found": False,
            "action": "none",
            "query": "",
            "old_response": "",
            "regen_count": 0,
        }

        # ── Staging entry ────────────────────────────────────────────────
        if query_hash in self.staging:
            entry = self.staging[query_hash]

            if rating > 0:
                entry["total_likes"] = entry.get("total_likes", 0) + 1
                net_likes = entry.get("total_likes", 0) - entry.get("total_dislikes", 0)
                # Enough positive signal → promote
                promoted = False
                if entry.get("staging_access", 0) >= 3 and net_likes >= 1:
                    promoted = self._promote_staging_to_confirmed(query_hash)
                if not promoted:
                    entry["status"] = "trusted"
                    self.save_cache()
                action = "promoted" if promoted else "trusted"
                print(
                    f"👍 Feedback (staging LIKE): net={net_likes:+d}, action={action}"
                )
                return {
                    "found": True,
                    "action": action,
                    "query": entry.get("query", ""),
                    "old_response": entry.get("response", ""),
                    "regen_count": entry.get("regen_count", 0),
                }

            else:  # dislike
                entry["total_dislikes"] = entry.get("total_dislikes", 0) + 1
                regen_count = entry.get("regen_count", 0)

                if regen_count >= self.MAX_REGEN:
                    # Reached regen limit → lock entry
                    entry["status"] = "needs_review"
                    self.save_cache()
                    print(
                        f"🔒 Max regen reached ({self.MAX_REGEN}x) — marked needs_review: {entry.get('query', '')[:50]}"
                    )
                    return {
                        "found": True,
                        "action": "needs_review",
                        "query": entry.get("query", ""),
                        "old_response": entry.get("response", ""),
                        "regen_count": regen_count,
                    }

                # Under limit → signal caller to regenerate
                self.save_cache()
                print(
                    f"🔄 Dislike on staging — requesting regen #{regen_count + 1}: {entry.get('query', '')[:50]}"
                )
                return {
                    "found": True,
                    "action": "regen",
                    "query": entry.get("query", ""),
                    "old_response": entry.get("response", ""),
                    "regen_count": regen_count,
                }

        # ── Confirmed entry ──────────────────────────────────────────────
        if query_hash in self.cache:
            entry = self.cache[query_hash]
            if rating > 0:
                entry["total_likes"] = entry.get("total_likes", 0) + 1
            else:
                entry["total_dislikes"] = entry.get("total_dislikes", 0) + 1
            self.save_cache()
            print(f"👍 Feedback (confirmed): rating={rating:+d}")
            return {
                "found": True,
                "action": "none",
                "query": entry.get("query", ""),
                "old_response": entry.get("response", ""),
                "regen_count": 0,
            }

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

        entry = self.staging[query_hash]
        new_len = len(new_response.strip())
        old_len = len(old_response.strip())
        regen_count = entry.get("regen_count", 0) + 1  # count this attempt

        if new_len > old_len * 1.1:  # new response is meaningfully longer
            # Replace with better response; reset dislike counter
            entry["response"] = new_response
            entry["context"] = context
            entry["regen_count"] = regen_count
            entry["last_regenerated"] = datetime.now().isoformat()
            entry["status"] = "unverified"  # needs fresh validation
            entry["total_dislikes"] = 0  # fresh start for new response
            new_status = "unverified"
            replaced = True
            print(
                f"✅ Regen #{regen_count}: replaced (new={new_len} chars > old={old_len} chars)"
            )
        else:
            # Not better enough → keep old, mark low confidence
            entry["regen_count"] = regen_count
            entry["last_regenerated"] = datetime.now().isoformat()
            if regen_count >= self.MAX_REGEN:
                entry["status"] = "needs_review"
                print(
                    f"🔒 Regen #{regen_count}: max reached — needs_review (new={new_len}, old={old_len})"
                )
            else:
                entry["status"] = "low_confidence"
                print(
                    f"⚠️ Regen #{regen_count}: not better — low_confidence (new={new_len}, old={old_len})"
                )
            new_status = entry["status"]
            replaced = False

        self.save_cache()
        return {"replaced": replaced, "status": new_status, "regen_count": regen_count}

    def update_entry(self, query_hash: str, new_response: str) -> bool:
        """Replace the cached response for a given hash (used after user chooses regenerated variant)."""
        if query_hash in self.staging:
            self.staging[query_hash]["response"] = new_response
            self.staging[query_hash]["last_regenerated"] = datetime.now().isoformat()
            self.staging[query_hash]["status"] = "unverified"
            self.save_cache()
            print(f"🔄 Staging entry updated with chosen answer: {query_hash[:8]}...")
            return True
        if query_hash in self.cache:
            self.cache[query_hash]["response"] = new_response
            self.cache[query_hash]["last_accessed"] = datetime.now().isoformat()
            self.save_cache()
            print(f"🔄 Confirmed entry updated with chosen answer: {query_hash[:8]}...")
            return True
        return False

    def delete_entry(self, query_hash: str) -> bool:
        """Delete a cache entry from confirmed or staging storage."""
        removed = False

        if query_hash in self.staging:
            del self.staging[query_hash]
            removed = True

        if query_hash in self.cache:
            del self.cache[query_hash]
            removed = True

        if query_hash in self.access_count:
            del self.access_count[query_hash]

        if removed:
            self.save_cache()
            print(f"🗑️ Removed invalid cache entry: {query_hash[:8]}...")

        return removed

    def clear(self):
        """Clear all cache (confirmed + staging)"""
        self.cache = {}
        self.staging = {}
        self.access_count = {}
        self.save_cache()
        print("🗑️ Cache cleared (confirmed + staging)")

    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total_size_bytes = len(json.dumps(self.cache).encode("utf-8"))
        stage_distribution = {"candidate": 0, "probation": 0, "unknown": 0}
        for item in self.staging.values():
            stage = item.get("stage", "candidate")
            if stage not in stage_distribution:
                stage_distribution["unknown"] += 1
            else:
                stage_distribution[stage] += 1

        return {
            "size": len(self.cache),
            "total_items": len(self.cache),
            "staging_items": len(self.staging),
            "staging_stage_distribution": stage_distribution,
            "size_mb": total_size_bytes / (1024 * 1024),
            "total_accesses": sum(self.access_count.values()),
            "most_accessed": self._get_most_accessed(5),
            "top_queries": self._get_most_accessed(5),
            "research_mode": {
                "trust_gating_enabled": self.enable_trust_gating,
                "metrics": self.research_metrics,
            },
        }

    def _get_most_accessed(self, limit: int = 5) -> List[Dict]:
        """Get most accessed queries"""
        sorted_items = sorted(
            self.access_count.items(), key=lambda x: x[1], reverse=True
        )[:limit]

        result = []
        for query_hash, count in sorted_items:
            if query_hash in self.cache:
                result.append(
                    {
                        "query": self.cache[query_hash].get("query", "Unknown")[:50],
                        "access_count": count,
                    }
                )

        return result

    def optimize(self, max_size_mb: float = 100.0) -> Dict:
        """
        Optimize cache by removing least accessed items
        """
        current_size_mb = self.get_stats()["size_mb"]

        if current_size_mb <= max_size_mb:
            return {"freed_mb": 0, "removed_items": 0}

        # Sort by access count (ascending)
        sorted_items = sorted(self.access_count.items(), key=lambda x: x[1])

        removed = 0
        for query_hash, _ in sorted_items:
            if query_hash in self.cache:
                del self.cache[query_hash]
                del self.access_count[query_hash]
                removed += 1

                # Check if we've freed enough space
                if self.get_stats()["size_mb"] <= max_size_mb:
                    break

        self.save_cache()

        new_size_mb = self.get_stats()["size_mb"]
        freed_mb = current_size_mb - new_size_mb

        return {"freed_mb": freed_mb, "removed_items": removed}

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

        to_delete: List[Dict] = []
        to_promote: List[Dict] = []
        to_keep: List[Dict] = []

        for query_hash, item in self.cache.items():
            count = self.access_count.get(query_hash, item.get("access_count", 0))

            # Parse last-accessed timestamp (fall back to created_at)
            try:
                ts_str = item.get("last_accessed") or item.get("created_at")
                last_accessed = datetime.fromisoformat(ts_str)
            except Exception:
                last_accessed = now - timedelta(days=999)  # treat as very old

            age_days = (now - last_accessed).days
            query_text = item.get("query", "")

            entry_base = {
                "hash": query_hash,
                "query": query_text,
                "access_count": count,
                "age_days": age_days,
            }

            if count >= min_access_for_promote:
                # Require net positive feedback to promote to FAQ
                net_likes = item.get("total_likes", 0) - item.get("total_dislikes", 0)
                if net_likes >= 1:
                    to_promote.append(
                        {**entry_base, "response": item.get("response", "")}
                    )
                elif net_likes < 0:
                    to_delete.append({**entry_base, "reason": "popular but disliked"})
                else:
                    to_keep.append(
                        {
                            **entry_base,
                            "reason": f"popular but no quality signal (net_likes={net_likes})",
                        }
                    )
            elif age_days > max_age_days and count < min_access_for_promote:
                to_delete.append(entry_base)
            else:
                to_keep.append(entry_base)

        return {
            "to_delete": to_delete,
            "to_promote": to_promote,
            "to_keep": to_keep,
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
            question = faq.get("question", "").strip()
            answer = faq.get("answer", "").strip()

            if not question or not answer:
                skipped += 1
                continue

            query_hash = self._hash_query(question)

            if query_hash in self.cache:
                skipped += 1
                continue

            self.cache[query_hash] = {
                "query": question,
                "response": answer,
                "context": faq.get("context", ""),
                "created_at": datetime.now().isoformat(),
                "last_accessed": datetime.now().isoformat(),
                "source": "faq_prepopulate",
            }
            self.access_count[query_hash] = 0
            added += 1

        if added:
            self.save_cache()

        print(
            f"📥 FAQ pre-populate: {added} added, {skipped} skipped (already cached / no answer)"
        )
        return {"added": added, "skipped": skipped}
