"""
Complete Cache-Augmented Generation (CAG) System
"""
from typing import Dict, List, Optional
import time
import os

# Import dengan error handling
try:
    from kv_cache_manager import KVCacheManager
except ImportError:
    from src.kv_cache_manager import KVCacheManager

try:
    from decision_agent import DecisionMakingAgent
except ImportError:
    from src.decision_agent import DecisionMakingAgent

try:
    from faq_generator import FAQGenerator
except ImportError:
    from src.faq_generator import FAQGenerator

try:
    from evaluation import PerformanceEvaluator
except ImportError:
    from src.evaluation import PerformanceEvaluator

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy


class CAGSystem:
    """Complete Cache-Augmented Generation System"""

    # Cosine-distance threshold for FAISS retrieval.
    # FAISS with COSINE strategy returns L2 distance of normalized vectors:
    #   0     = identical  (cosine_sim = 1.0)
    #   0.80  = cosine_sim ≈ 0.68  (often too strict)
    #   1.0   = cosine_sim ≈ 0.50
    #   1.414 = orthogonal (cosine_sim = 0.0)
    # 1.0 keeps topically-relevant chunks while still rejecting off-topic ones.
    RETRIEVAL_THRESHOLD = 1.0

    INVALID_PATTERNS = [
        "homestay tidak tersedia",
        "tidak tersedia dalam database",
        "Halo is a term",
        "space opera",
        "science fiction",
        "video game",
        "Data tidak mention",
        "Locak Hotel",
        "saya memerlukan dokumen",
        "informasi tentang kategori",
        # Error responses - should never be cached
        "gemini api sedang sibuk",
        "rate limit",
        "silakan tunggu",
        "silakan coba lagi",
        "terjadi kesalahan",
        "429 client error",
        "too many requests",
        "name resolution error",
        "failed to resolve",
        # No-context fallback - never cache these
        "tidak menemukan informasi yang relevan",
        "coba ajukan pertanyaan yang lebih spesifik",
    ]
    
    def __init__(self, model, encoder):
        self.model = model
        self.encoder = encoder
        self.kv_cache = KVCacheManager()
        self.agent = DecisionMakingAgent()
        self.faq_gen = FAQGenerator()
        self.evaluator = PerformanceEvaluator()
        self.database = None
        self.docs_loaded = False
    
    def _is_invalid_response(self, response: str) -> bool:
        """Check if a response is invalid"""
        if not response or len(response.strip()) < 30:
            return True
        
        response_lower = response.lower()
        for pattern in self.INVALID_PATTERNS:
            if pattern.lower() in response_lower:
                return True
        
        return False

    def _search_faq(self, query: str) -> Optional[Dict]:
        """
        Search FAQ file for a question similar to `query`.
        Returns the FAQ entry (with answer) if similarity >= 0.55, else None.
        Uses difflib SequenceMatcher + keyword overlap scoring.
        Only returns entries that have a non-empty answer.
        """
        from difflib import SequenceMatcher
        import re

        try:
            faqs = self.faq_gen.load_faqs()
        except Exception:
            return None

        query_lower = query.lower().strip()
        # Normalise: remove punctuation, lowercase
        q_clean = re.sub(r'[^\w\s]', ' ', query_lower)
        q_words = set(q_clean.split())

        best_score = 0.0
        best_faq   = None

        for faq in faqs:
            answer = faq.get('answer', '').strip()
            if not answer or len(answer) < 20:
                continue  # skip entries without real answers

            faq_q = faq.get('question', '').lower().strip()
            fq_clean = re.sub(r'[^\w\s]', ' ', faq_q)
            fq_words = set(fq_clean.split())

            # String similarity
            seq_ratio = SequenceMatcher(None, q_clean, fq_clean).ratio()

            # Keyword overlap (Jaccard)
            kw_list = [k.lower() for k in faq.get('keywords', [])]
            kw_hits = sum(1 for k in kw_list if k in query_lower)
            kw_score = (kw_hits / max(len(kw_list), 1)) * 0.4 if kw_list else 0

            # Word overlap
            common = q_words & fq_words
            word_score = len(common) / max(len(q_words | fq_words), 1)

            # Combined score (sequence match weighted highest)
            combined = seq_ratio * 0.5 + word_score * 0.3 + kw_score * 0.2

            if combined > best_score:
                best_score = combined
                best_faq = faq

        SIMILARITY_THRESHOLD = 0.45  # tuned: broad enough for paraphrasing
        if best_score >= SIMILARITY_THRESHOLD and best_faq:
            print(f"📖 FAQ match (score={best_score:.3f}): {best_faq.get('question', '')[:60]}")
            return best_faq

        return None
    
    def load_documents(self, pdf_paths: List[str], use_summaries: bool = False):
        """Load documents and build vector database"""
        start_time = time.time()
        
        print(f"📚 Loading {len(pdf_paths)} documents for CAG...")
        
        # Load PDFs
        pages = []
        for pdf_path in pdf_paths:
            if not os.path.exists(pdf_path):
                print(f"⚠️ File not found: {pdf_path}")
                continue
            
            try:
                loader = PyPDFLoader(pdf_path)
                pages.extend(loader.load())
                print(f"   ✅ Loaded: {os.path.basename(pdf_path)}")
            except Exception as e:
                print(f"   ❌ Error loading {pdf_path}: {str(e)}")
        
        if not pages:
            print("❌ No documents loaded!")
            return {"num_chunks": 0, "processing_time": 0}
        
        # Split into chunks
        print("🔍 Splitting into chunks...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=50,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        docs = text_splitter.split_documents(pages)
        
        print(f"📄 Loaded {len(pages)} pages, split into {len(docs)} chunks")
        
        # Build vector database
        print("🔨 Building vector database...")
        self.database = FAISS.from_documents(
            docs,
            self.encoder,
            distance_strategy=DistanceStrategy.COSINE
        )
        
        self.docs_loaded = True
        elapsed = time.time() - start_time
        
        print(f"✅ CAG ready: {len(docs)} chunks in {elapsed:.2f}s")
        
        return {
            "num_chunks": len(docs),
            "processing_time": elapsed,
            "num_pages": len(pages)
        }
    
    def get_response(
        self,
        query: str,
        chat_history: List[Dict] = None,
        k: int = 5,
        max_new_tokens: int = 2048,
        use_cache: bool = True,
        temperature: float = 0.7
    ) -> Dict:
        """Get response using CAG system"""
        start_time = time.time()
        
        # Classify intent
        intent = self.model._classify_intent(query)
        
        # Handle greeting
        if intent == 'greeting':
            response = self.model._get_greeting_response()
            return {
                "response": response,
                "source": "greeting",
                "cache_used": False,
                "response_time": time.time() - start_time,
                "num_chunks": 0,
                "context": "",
                "cache_key": None,
            }
        
        # Handle general questions (math, etc.)
        if intent == 'general_question':
            response = self.model._get_general_answer(query)
            return {
                "response": response,
                "source": "general_answer",
                "cache_used": False,
                "response_time": time.time() - start_time,
                "num_chunks": 0,
                "context": "",
                "cache_key": None,
            }
        
        # Check if documents loaded
        if not self.database:
            return {
                "response": "⚠️ Silakan upload dokumen PDF terlebih dahulu ke folder database/vectordatabase/",
                "source": "error",
                "cache_used": False,
                "response_time": time.time() - start_time,
                "num_chunks": 0,
                "context": "",
                "cache_key": None,
            }
        
        # Check cache
        query_hash = self.kv_cache._hash_query(query)
        if use_cache:
            cached = self.kv_cache.get(query)
            if cached and not self._is_invalid_response(cached.get("response", "")):
                hit_type = "STAGING" if cached.get("from_staging") else "HIT"
                print(f"✅ Cache {hit_type}: {query[:50]}...")
                return {
                    "response": cached["response"],
                    "source": "cag_cache",
                    "cache_used": True,
                    "response_time": time.time() - start_time,
                    "access_count": cached.get("access_count", 0),
                    "num_chunks": 0,
                    "context": cached.get("context", ""),
                    "cache_key": query_hash,
                }

        # FAQ search — before hitting FAISS
        # Searches faq_tourism.json directly, bypassing vector retrieval.
        # Entries with a real answer are returned immediately as CAG hits.
        if use_cache:
            faq_hit = self._search_faq(query)
            if faq_hit:
                faq_response = faq_hit['answer']
                # Put in staging so it can be confirmed and tracked
                self.kv_cache.put(query, faq_response, "from_faq")
                return {
                    "response": faq_response,
                    "source": "cag_cache",
                    "cache_used": True,
                    "response_time": time.time() - start_time,
                    "num_chunks": 0,
                    "context": "from_faq",
                    "cache_key": query_hash,
                }
        
        # RAG: Retrieve relevant chunks — Layer 1: Retrieval Confidence Gate
        retrieval_start = time.time()
        try:
            raw_results = self.database.similarity_search_with_score(query, k=k)
            # Filter by threshold (FAISS cosine distance: lower = more similar)
            relevant_docs = [
                doc for doc, score in raw_results
                if score <= self.RETRIEVAL_THRESHOLD
            ]
            if raw_results:
                top_score = raw_results[0][1]
                print(f"🔍 Retrieval: {len(raw_results)} raw → {len(relevant_docs)} passed threshold ({self.RETRIEVAL_THRESHOLD}), top_score={top_score:.4f}")
        except Exception as e:
            print(f"❌ Retrieval error: {e}")
            relevant_docs = []
        retrieval_time = time.time() - retrieval_start

        # === Layer 1 Gate: no relevant context → refuse to hallucinate ===
        if not relevant_docs:
            print(f"🚫 No chunks passed retrieval threshold — aborting generation")
            return {
                "response": "Maaf, saya tidak menemukan informasi yang relevan tentang pertanyaan ini di database wisata Danau Toba. Coba ajukan pertanyaan yang lebih spesifik seputar Danau Toba.",
                "source": "no_relevant_context",
                "cache_used": False,
                "response_time": time.time() - start_time,
                "num_chunks": 0,
                "context": "",
                "cache_key": query_hash,
            }

        # Build context
        context_parts = []
        for i, doc in enumerate(relevant_docs, 1):
            content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
            content = content.strip()
            if content and len(content) > 50:
                context_parts.append(f"[Sumber {i}]\n{content}")
        
        context = "\n\n".join(context_parts)
        print(f"📄 Retrieved {len(relevant_docs)} chunks, context: {len(context)} chars")
        
        # Generate response
        generation_start = time.time()
        try:
            response = self.model.generate_response(
                query=query,
                context=context,
                chat_history=chat_history or [],
                max_new_tokens=max_new_tokens,
                temperature=temperature
            )
        except Exception as e:
            print(f"❌ Generation error: {e}")
            response = f"Maaf, terjadi kesalahan saat memproses pertanyaan: {str(e)}"
        
        generation_time = time.time() - generation_start
        total_time = time.time() - start_time
        
        # Cache valid response → goes to STAGING (not confirmed cache).
        # Staging entries are promoted to confirmed cache only after quality
        # validation (multiple likes from different users), and eventually
        # promoted to the FAQ dataset.
        if use_cache and not self._is_invalid_response(response):
            self.kv_cache.put(query, response, context[:500])
            print(f"💾 Staged: {query[:50]}...")

        return {
            "response": response,
            "source": "rag",
            "cache_used": False,
            "response_time": total_time,
            "retrieval_time": retrieval_time,
            "generation_time": generation_time,
            "num_chunks": len(relevant_docs),
            "context": context,
            "cache_key": query_hash,
        }
    
    def get_stats(self) -> Dict:
        """Get system statistics"""
        return {
            "system_status": "ready" if self.docs_loaded else "no_documents",
            "kv_cache": self.kv_cache.get_stats(),
            "performance": {}
        }
    
    def clear_cache(self):
        """Clear all caches"""
        self.kv_cache.clear()
        print("🗑️ Cache cleared")
    
    def optimize_cache(self, max_size_mb: float = 100.0, min_access_count: int = 2):
        """Optimize cache"""
        result = self.kv_cache.optimize(max_size_mb)
        return {
            "removed": result.get('removed_items', 0),
            "current_size_mb": self.get_stats()['kv_cache'].get('size_mb', 0),
            "remaining_items": self.get_stats()['kv_cache'].get('size', 0)
        }
