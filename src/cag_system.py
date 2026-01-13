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
    from summary_cache import SummaryCache
except ImportError:
    from src.summary_cache import SummaryCache

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
    ]
    
    def __init__(self, model, encoder):
        self.model = model
        self.encoder = encoder
        self.kv_cache = KVCacheManager()
        self.summary_cache = SummaryCache()
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
        max_new_tokens: int = 512,
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
                "num_chunks": 0
            }
        
        # Handle general questions (math, etc.)
        if intent == 'general_question':
            response = self.model._get_general_answer(query)
            return {
                "response": response,
                "source": "general_answer",
                "cache_used": False,
                "response_time": time.time() - start_time,
                "num_chunks": 0
            }
        
        # Check if documents loaded
        if not self.database:
            return {
                "response": "⚠️ Silakan upload dokumen PDF terlebih dahulu ke folder data/tourism/",
                "source": "error",
                "cache_used": False,
                "response_time": time.time() - start_time,
                "num_chunks": 0
            }
        
        # Check cache
        if use_cache:
            cached = self.kv_cache.get(query)
            if cached and not self._is_invalid_response(cached.get("response", "")):
                print(f"✅ Cache HIT: {query[:50]}...")
                return {
                    "response": cached["response"],
                    "source": "cag_cache",
                    "cache_used": True,
                    "response_time": time.time() - start_time,
                    "access_count": cached.get("access_count", 0),
                    "num_chunks": 0
                }
        
        # RAG: Retrieve relevant chunks
        retrieval_start = time.time()
        try:
            relevant_docs = self.database.similarity_search(query, k=k)
        except Exception as e:
            print(f"❌ Retrieval error: {e}")
            relevant_docs = []
        retrieval_time = time.time() - retrieval_start
        
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
        
        # Cache valid response
        if use_cache and not self._is_invalid_response(response):
            self.kv_cache.put(query, response, context[:500])
            print(f"💾 Cached: {query[:50]}...")
        
        return {
            "response": response,
            "source": "rag",
            "cache_used": False,
            "response_time": total_time,
            "retrieval_time": retrieval_time,
            "generation_time": generation_time,
            "num_chunks": len(relevant_docs)
        }
    
    def get_stats(self) -> Dict:
        """Get system statistics"""
        return {
            "system_status": "ready" if self.docs_loaded else "no_documents",
            "kv_cache": self.kv_cache.get_stats(),
            "summary_cache": self.summary_cache.get_stats(),
            "performance": {}
        }
    
    def clear_cache(self):
        """Clear all caches"""
        self.kv_cache.clear()
        self.summary_cache.clear()
        print("🗑️ Cache cleared")
    
    def optimize_cache(self, max_size_mb: float = 100.0, min_access_count: int = 2):
        """Optimize cache"""
        result = self.kv_cache.optimize(max_size_mb)
        return {
            "removed": result.get('removed_items', 0),
            "current_size_mb": self.get_stats()['kv_cache'].get('size_mb', 0),
            "remaining_items": self.get_stats()['kv_cache'].get('size', 0)
        }
