"""
Complete Cache-Augmented Generation (CAG) System
"""
from typing import Dict, List, Optional
import time
import os
import re
from difflib import SequenceMatcher

# Import dengan error handling
try:
    from kv_cache_manager import KVCacheManager
except ImportError:
    from src.kv_cache_manager import KVCacheManager

try:
    from faq_generator import FAQGenerator
except ImportError:
    from src.faq_generator import FAQGenerator

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document as LCDocument
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy


class CAGSystem:
    """Complete Cache-Augmented Generation System"""

    # ──────────────────────────────────────────────────────────────────────────
    # PARAMETER RETRIEVAL DOKUMEN
    # FAISS + DistanceStrategy.COSINE mengembalikan JARAK L2 (bukan similarity).
    # Artinya: nilai LEBIH KECIL = LEBIH MIRIP  (0.0 = identik, > 1.0 = jauh)
    #
    # Setiap chunk dinilai dengan HYBRID SCORE gabungan (0.0 – 1.0):
    #
    #   faiss_sim = 1 - (jarak / MAX_FAISS_DISTANCE)   ← kemiripan semantik/vektor
    #   kw_score  = proporsi kata query yang ada di chunk ← kecocokan keyword
    #   hybrid    = faiss_sim × HYBRID_WEIGHT_VECTOR
    #             + kw_score  × HYBRID_WEIGHT_KEYWORD
    #
    # Chunk LOLOS jika hybrid >= RELEVANCE_THRESHOLD
    # Makin TINGGI RELEVANCE_THRESHOLD → seleksi makin KETAT
    # ──────────────────────────────────────────────────────────────────────────
    MAX_FAISS_DISTANCE    = 1.20   # jarak absolut maks — lebih dari ini = tidak relevan
    HYBRID_WEIGHT_VECTOR  = 0.60   # bobot kemiripan semantik (vektor embedding)
    HYBRID_WEIGHT_KEYWORD = 0.40   # bobot kecocokan kata-kata penting query
    RELEVANCE_THRESHOLD   = 0.30   # skor minimum untuk lolos ke konteks LLM (0.0–1.0)

    INVALID_PATTERNS = [
        "homestay tidak tersedia",
        "tidak tersedia dalam database",
        "belum tersedia dalam dokumen",
        "belum tersedia dalam dokumen yang saya miliki",
        "informasi mengenai menu",
        "tidak memiliki daftar menu spesifik",
        "berdasarkan pengalaman dan pengetahuan umum",
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
        self.faq_gen = FAQGenerator()
        self.database = None
        self.docs_loaded = False
        self.loaded_docs = []

    def _extract_place_name(self, query: str) -> Optional[str]:
        """Extract a likely place name from a user query like 'menu di Cantik Daijo Cafe'."""
        query_clean = re.sub(r'\s+', ' ', query).strip(" ?!.,")
        patterns = [
            r'(?:menu|alamat|harga|jam operasional|ulasan)\s+(?:makanan\s+)?di\s+(.+)$',
            r'(?:apa saja|apa|berapa|bagaimana)\s+.+?\s+di\s+(.+)$',
            r'(?:tentang|info(?:rmasi)?\s+(?:tentang)?)\s+(.+)$',
        ]

        for pattern in patterns:
            match = re.search(pattern, query_clean, flags=re.IGNORECASE)
            if match:
                candidate = self._clean_place_candidate(match.group(1))
                if len(candidate) >= 4:
                    return candidate

        return None

    def _clean_place_candidate(self, candidate: str) -> str:
        """Normalize extracted place candidate and remove trailing attribute clauses."""
        cleaned = re.sub(r'\s+', ' ', candidate).strip(" ?!.,")
        # Example: "D'Barans Cafe dan jam buka nya" -> "D'Barans Cafe"
        cleaned = re.sub(
            r'\s+(?:dan|&|serta)\s+(?:jam|harga|alamat|ulasan|review|menu|fasilitas)\b.*$',
            '',
            cleaned,
            flags=re.IGNORECASE,
        ).strip(" ?!.,")
        return cleaned

    def _is_followup_reference_query(self, query: str) -> bool:
        """Detect short follow-up queries that rely on previous place context."""
        query_lower = query.lower().strip()
        has_attribute = any(kw in query_lower for kw in [
            'menu', 'alamat', 'harga', 'jam', 'operasional', 'ulasan', 'review', 'fasilitas'
        ])
        has_reference = any(kw in query_lower for kw in [
            'nya', 'itu', 'disitu', 'di situ', 'yang tadi', 'tempat itu', 'di sana'
        ])
        has_explicit_place = self._extract_place_name(query) is not None
        return has_attribute and has_reference and not has_explicit_place

    def _extract_last_place_from_history(self, chat_history: List[Dict]) -> Optional[str]:
        """Extract most recent place name from user messages in chat history."""
        if not chat_history:
            return None

        for msg in reversed(chat_history):
            if msg.get('role') != 'user':
                continue
            content = (msg.get('content') or '').strip()
            if not content:
                continue
            place = self._extract_place_name(content)
            if place:
                return place
        return None

    def _normalize_match_text(self, text: str) -> str:
        """Normalize text for robust place-name matching."""
        normalized = re.sub(r'[^\w\s]', ' ', text.lower(), flags=re.UNICODE)
        return re.sub(r'\s+', ' ', normalized).strip()

    def _fuzzy_token_coverage(self, phrase: str, text: str) -> float:
        """Measure how well phrase tokens are represented in text, tolerating minor typos."""
        phrase_tokens = [t for t in self._normalize_match_text(phrase).split() if len(t) > 1]
        if not phrase_tokens:
            return 0.0

        text_tokens = set(self._normalize_match_text(text).split())
        if not text_tokens:
            return 0.0

        matched = 0
        for phrase_token in phrase_tokens:
            if phrase_token in text_tokens:
                matched += 1
                continue

            has_fuzzy_match = any(
                abs(len(candidate) - len(phrase_token)) <= 2
                and SequenceMatcher(None, phrase_token, candidate).ratio() >= 0.84
                for candidate in text_tokens
            )
            if has_fuzzy_match:
                matched += 1

        return matched / len(phrase_tokens)

    def _find_specific_place_docs(self, query: str, limit: int = 3) -> List:
        """Find chunks that explicitly mention a specific place asked in the query."""
        place_name = self._extract_place_name(query)
        if not place_name or not self.loaded_docs:
            return []

        place_lower = self._normalize_match_text(place_name)
        matched = []
        for doc in self.loaded_docs:
            content_lower = self._normalize_match_text(doc.page_content)
            coverage = 1.0 if place_lower in content_lower else self._fuzzy_token_coverage(place_name, doc.page_content)
            if coverage >= 0.84:
                matched.append((coverage, doc))

        if not matched:
            return []

        matched.sort(key=lambda item: item[0], reverse=True)
        matched_docs = [doc for _, doc in matched]

        expanded = []
        seen_keys = set()
        for doc in matched_docs:
            meta = getattr(doc, 'metadata', {})
            src = meta.get('source')
            idx = meta.get('chunk_index')
            for candidate in self.loaded_docs:
                candidate_meta = getattr(candidate, 'metadata', {})
                same_source = candidate_meta.get('source') == src
                candidate_idx = candidate_meta.get('chunk_index')
                if same_source and isinstance(idx, int) and isinstance(candidate_idx, int) and abs(candidate_idx - idx) <= 1:
                    key = (src, candidate_idx)
                    if key not in seen_keys:
                        expanded.append(candidate)
                        seen_keys.add(key)

        return expanded[:limit]

    # ─── Category keyword map: maps JSON category → query keywords ───────────
    CATEGORY_KEYWORD_MAP: dict = {
        'bukit':       ['bukit', 'perbukitan', 'puncak', 'hill'],
        'pantai':      ['pantai', 'beach', 'pesisir'],
        'air_terjun':  ['air terjun', 'waterfall', 'curug'],
        'danau':       ['danau', 'lake'],
        'budaya':      ['budaya', 'museum', 'adat', 'sejarah', 'heritage'],
        'rekreasi':    ['rekreasi', 'kolam renang', 'wahana', 'taman'],
        'desa_wisata': ['desa wisata', 'kampung wisata'],
        'alam':        ['alam', 'panorama'],
        'geowisata':   ['geowisata', 'geo wisata'],
        'tour':        ['tour', 'paket wisata'],
    }

    def _extract_listing_categories(self, query_lower: str) -> List[str]:
        """Extract requested categories from query with priority to specific intent words."""
        # Prioritize explicit hill/perbukitan intent so 'di Danau Toba' does not trigger danau category.
        if any(token in query_lower for token in ['perbukitan', 'bukit', 'puncak', 'hill']):
            return ['bukit']

        categories: List[str] = []
        for category, keywords in self.CATEGORY_KEYWORD_MAP.items():
            if any(kw in query_lower for kw in keywords):
                categories.append(category)

        # Remove duplicate categories while preserving order.
        return list(dict.fromkeys(categories))

    def _is_listing_query(self, query: str) -> bool:
        """Return True if the user is asking for a *list* of places (not a single place)."""
        q = query.lower()
        listing_signals = ['apa saja', 'semua', 'daftar', 'list', 'sebutkan', 'rekomendasikan',
                           'ada apa saja', 'apa aja', 'mana saja', 'berapa banyak']
        return any(sig in q for sig in listing_signals)

    def _load_locations(self) -> list:
        """Load locations.json; returns [] on any error."""
        import json
        locations_file = os.path.join(
            os.path.dirname(__file__), '..', 'database', 'Locations', 'locations.json'
        )
        try:
            with open(locations_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Could not load locations.json: {e}")
            return []

    def _get_locations_json_context(self, query: str) -> str:
        """
        Build a structured context block from locations.json for category/listing queries.
        Returns empty string if no relevant locations found.
        """
        query_lower = query.lower()

        # Detect which categories the query is asking about
        target_categories = self._extract_listing_categories(query_lower)

        if not target_categories:
            return ""

        locations = self._load_locations()
        if not locations:
            return ""

        matched = []
        for loc in locations:
            cat = loc.get('category', '')
            if cat in target_categories:
                matched.append(loc)

        if not matched:
            return ""

        # Sort by rating descending
        matched.sort(key=lambda x: x.get('rating', 0), reverse=True)

        lines = ["[Data Terstruktur: Lokasi Database]"]
        for i, loc in enumerate(matched, 1):
            lines.append(
                f"Tempat {i}: {loc.get('name', 'N/A')}\n"
                f"- Kategori : {loc.get('category', 'N/A')}\n"
                f"- Deskripsi: {loc.get('description', 'N/A')}\n"
                f"- Lokasi   : {loc.get('location', 'N/A')}\n"
                f"- Alamat   : {loc.get('address', 'N/A')}\n"
                f"- Harga    : {loc.get('price', 'N/A')}\n"
                f"- Jam Buka : {loc.get('hours', 'N/A')}\n"
                f"- Rating   : {loc.get('rating', 'N/A')}/5"
            )
        return "\n\n".join(lines)

    def _keyword_overlap_score(self, query: str, chunk_text: str) -> float:
        """
        Hitung proporsi kata penting dari query yang muncul di dalam chunk.

        Cara kerja:
          - Buang stop words (kata umum) dan kata pendek (< 3 karakter)
          - Hitung berapa banyak kata penting yang ditemukan di teks chunk
          - Kembalikan rasio: hits / total_kata_penting  (0.0 – 1.0)

        Contoh:
          query = "menu Cantik Daijo Cafe"
          → kata penting: [menu, Cantik, Daijo, Cafe]
          → chunk mengandung semua 4 kata → skor = 1.0
          → chunk mengandung 2 kata       → skor = 0.5
          → chunk tidak ada satu pun      → skor = 0.0
        """
        STOP_WORDS = {
            'apa', 'saja', 'ada', 'dan', 'atau', 'ini', 'itu', 'di',
            'ke', 'dari', 'untuk', 'dengan', 'pada', 'adalah', 'yang',
            'bagaimana', 'berapa', 'dimana', 'siapa', 'tentang',
            'info', 'informasi', 'tolong', 'bisa', 'boleh',
            'saya', 'kamu', 'kalian', 'kapan', 'apakah',
        }
        q_words = [
            w.lower() for w in re.findall(r'\w+', query)
            if w.lower() not in STOP_WORDS and len(w) > 2
        ]
        if not q_words:
            return 0.0
        chunk_lower = chunk_text.lower()
        hits = sum(1 for w in q_words if w in chunk_lower)
        return hits / len(q_words)

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

        SIMILARITY_THRESHOLD = 0.60  # raised: stricter matching to avoid false positives
        if best_score >= SIMILARITY_THRESHOLD and best_faq:
            print(f"📖 FAQ match (score={best_score:.3f}): {best_faq.get('question', '')[:60]}")
            return best_faq

        return None
    
    def load_documents(self, pdf_paths: List[str], use_summaries: bool = False):
        """Load documents and build vector database"""
        start_time = time.time()
        
        print(f"📚 Loading {len(pdf_paths)} documents for CAG...")

        # --- Load PDFs: merge all pages per file into ONE document so that
        #     chunk_overlap can bridge page boundaries (fixes entity-name/
        #     description splits that would otherwise be lost between pages).

        merged_docs = []
        total_page_count = 0
        for pdf_path in pdf_paths:
            if not os.path.exists(pdf_path):
                print(f"⚠️ File not found: {pdf_path}")
                continue

            try:
                loader = PyPDFLoader(pdf_path)
                pages = loader.load()
                # Merge all pages into a single document; keep source metadata
                combined_text = "\n\n".join(p.page_content for p in pages)
                source_name = os.path.basename(pdf_path)
                merged_docs.append(LCDocument(
                    page_content=combined_text,
                    metadata={"source": source_name}
                ))
                total_page_count += len(pages)
                print(f"   ✅ Loaded: {source_name} ({len(pages)} halaman)")
            except Exception as e:
                print(f"   ❌ Error loading {pdf_path}: {str(e)}")
        
        if not merged_docs:
            print("❌ No documents loaded!")
            return {"num_chunks": 0, "processing_time": 0}
        
        # Split into chunks — overlap now works across page boundaries
        print("🔍 Splitting into chunks...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=768,
            chunk_overlap=150,       # increased: names/headers survive page joins
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        docs = text_splitter.split_documents(merged_docs)

        # Prepend source filename to every chunk so the LLM always knows context
        for chunk_index, doc in enumerate(docs):
            src = doc.metadata.get("source", "")
            doc.metadata["chunk_index"] = chunk_index
            if src and not doc.page_content.startswith(f"[{src}]"):
                doc.page_content = f"[Sumber: {src}]\n{doc.page_content}"

        self.loaded_docs = docs
        
        print(f"📄 Loaded {total_page_count} halaman dari {len(merged_docs)} file, "
              f"split into {len(docs)} chunks")
        
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
            "num_pages": total_page_count
        }
    
    def get_response(
        self,
        query: str,
        chat_history: List[Dict] = None,
        k: int = 8,
        max_new_tokens: int = 2048,
        use_cache: bool = True,
        temperature: float = 0.7,
        user_preferences: list = None,
    ) -> Dict:
        """Get response using CAG system"""
        start_time = time.time()
        is_first_message = not bool(chat_history)
        
        # Classify intent
        intent = self.model._classify_intent(query)

        # Follow-up grounding: map pronoun-based questions to the last place in history.
        retrieval_query = query
        contextual_followup = False
        if self._is_followup_reference_query(query) and chat_history:
            last_place = self._extract_last_place_from_history(chat_history)
            if last_place:
                retrieval_query = f"{query.strip()} di {last_place}".strip()
                contextual_followup = True
                print(f"🔗 Follow-up query grounded to previous place: {last_place}")
        
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
                "response": "⚠️ Silakan upload dokumen PDF terlebih dahulu ke folder database/documents/",
                "source": "error",
                "cache_used": False,
                "response_time": time.time() - start_time,
                "num_chunks": 0,
                "context": "",
                "cache_key": None,
            }
        
        # Check cache
        query_hash = self.kv_cache._hash_query(query)
        if use_cache and not contextual_followup:
            cached = self.kv_cache.get(query)
            if cached:
                if self._is_invalid_response(cached.get("response", "")):
                    self.kv_cache.delete_entry(query_hash)
                    print(f"⚠️ Ignored invalid cached response: {query[:50]}...")
                else:
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
        if use_cache and not contextual_followup:
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
        
        # For listing queries (apa saja, daftar, etc.), retrieve more FAISS chunks
        if self._is_listing_query(retrieval_query):
            k = max(k, 15)

        # RAG: Retrieve relevant chunks — Layer 1: Retrieval Confidence Gate
        retrieval_start = time.time()
        try:
            raw_results = self.database.similarity_search_with_score(retrieval_query, k=k)
            raw_results = sorted(raw_results, key=lambda item: float(item[1]))
            top_score = float(raw_results[0][1]) if raw_results else 0.0

            specific_place_docs = self._find_specific_place_docs(retrieval_query, limit=min(max(k // 2, 2), 4))

            # ── Hybrid Scoring ───────────────────────────────────────────────
            # Setiap chunk mendapat HYBRID SCORE (0.0–1.0) dari dua komponen:
            #
            #   1. faiss_sim : kemiripan semantik dari embedding vektor
            #                  konversi: makin kecil jarak FAISS → makin besar sim
            #   2. kw_score  : proporsi kata penting query yang ada di teks chunk
            #
            # Chunk LOLOS jika hybrid_score >= RELEVANCE_THRESHOLD
            # ─────────────────────────────────────────────────────────────────
            scored_chunks = []
            for doc, faiss_dist in raw_results:
                d         = float(faiss_dist)
                faiss_sim = max(0.0, 1.0 - d / self.MAX_FAISS_DISTANCE)
                kw_score  = self._keyword_overlap_score(retrieval_query, doc.page_content)
                hybrid    = (faiss_sim * self.HYBRID_WEIGHT_VECTOR
                             + kw_score * self.HYBRID_WEIGHT_KEYWORD)
                scored_chunks.append((doc, d, faiss_sim, kw_score, hybrid))

            # Urutkan: skor hybrid tertinggi (paling relevan) duluan
            scored_chunks.sort(key=lambda x: x[4], reverse=True)

            # Filter: hanya chunk yang melewati ambang batas relevansi
            threshold_passed = [
                (doc, dist) for doc, dist, fsim, kw, hyb in scored_chunks
                if hyb >= self.RELEVANCE_THRESHOLD
            ]

            prioritized = [(doc, 0.0) for doc in specific_place_docs]
            merged_results = prioritized + threshold_passed

            # ── Deduplication ────────────────────────────────────────────────
            # Remove chunks whose content is >70 % identical to an already-kept
            # chunk.  This prevents overlap-created near-duplicate chunks from
            # wasting context slots that could go to genuinely different info.
            seen_contents: list = []
            deduped: list = []
            for doc, score in merged_results:
                content = (doc.page_content if hasattr(doc, 'page_content') else str(doc)).strip()
                # Check overlap ratio against every kept chunk
                is_duplicate = False
                for kept in seen_contents:
                    # Simple overlap: count shared characters in shorter string
                    shorter = min(len(content), len(kept))
                    if shorter == 0:
                        continue
                    # Count matching chars via set intersection on trigrams
                    def trigrams(s):
                        return set(s[i:i+3] for i in range(len(s) - 2))
                    tg_new  = trigrams(content[:300])
                    tg_kept = trigrams(kept[:300])
                    if not tg_new or not tg_kept:
                        continue
                    overlap = len(tg_new & tg_kept) / max(len(tg_new), len(tg_kept))
                    if overlap >= 0.70:          # 70 % trigram overlap → duplicate
                        is_duplicate = True
                        break
                if not is_duplicate:
                    deduped.append(doc)
                    seen_contents.append(content)

            relevant_docs = deduped[:k]

            if scored_chunks:
                top = scored_chunks[0]
                print(
                    f"🔍 Retrieval: {len(raw_results)} raw"
                    f" → {len(threshold_passed)} lolos threshold (hybrid ≥ {self.RELEVANCE_THRESHOLD})"
                    f" → {len(specific_place_docs)} exact-place match"
                    f" → {len(relevant_docs)} after dedup"
                    f" | best: hybrid={top[4]:.2f} (vektor={top[2]:.2f}, keyword={top[3]:.2f})"
                )
        except Exception as e:
            print(f"❌ Retrieval error: {e}")
            relevant_docs = []
        retrieval_time = time.time() - retrieval_start

        # === Layer 1: no context from docs → fallback to LLM general knowledge ===
        if not relevant_docs:
            # For listing/category queries, try locations.json as a fallback source.
            if self._is_listing_query(retrieval_query):
                structured_ctx = self._get_locations_json_context(retrieval_query)
                if structured_ctx:
                    print(f"📍 FAISS returned nothing — using structured locations data for listing query")
                    context = structured_ctx
                    # Skip straight to generation with only the JSON context
                    generation_start = time.time()
                    try:
                        response = self.model.generate_response(
                            query=query,
                            context=context,
                            chat_history=chat_history or [],
                            max_new_tokens=max_new_tokens,
                            temperature=temperature,
                            user_preferences=user_preferences or [],
                            is_first_message=is_first_message,
                        )
                    except Exception as e:
                        print(f"❌ Generation error: {e}")
                        response = f"Maaf, terjadi kesalahan saat memproses pertanyaan: {str(e)}"
                    if use_cache and not self._is_invalid_response(response):
                        self.kv_cache.put(query, response, context[:500])
                    return {
                        "response": response,
                        "source": "rag",
                        "cache_used": False,
                        "response_time": time.time() - start_time,
                        "num_chunks": 0,
                        "context": context,
                        "cache_key": query_hash,
                    }

            if intent == 'tourism':
                print("⚠️ No chunks passed retrieval threshold — returning document-grounded unavailable response")
                return {
                    "response": self.model._build_document_unavailable_response(query),
                    "source": "no_relevant_context",
                    "cache_used": False,
                    "response_time": time.time() - start_time,
                    "num_chunks": 0,
                    "context": "",
                    "cache_key": query_hash,
                }

            print(f"⚠️ No chunks passed retrieval threshold — falling back to LLM general knowledge")
            try:
                _greeting_rule_general = (
                    "Ini adalah pesan PERTAMA dalam percakapan — boleh membuka jawaban dengan sapaan singkat yang hangat."
                    if is_first_message else
                    "Ini adalah lanjutan percakapan — JANGAN memulai jawaban dengan sapaan (Halo, Horas, Selamat datang, dsb). Langsung jawab pertanyaan."
                )
                # Include chat history for context-aware follow-up
                _history_general = ""
                if chat_history and len(chat_history) > 0:
                    _h_lines = []
                    for msg in chat_history[-8:]:
                        role = "Pengguna" if msg.get('role') == 'user' else "Asisten"
                        _h_lines.append(f"  {role}: {msg.get('content', '')[:300]}")
                    _history_general = (
                        "\n\nKONTEKS PERCAKAPAN SEBELUMNYA:\n"
                        + "\n".join(_h_lines)
                        + "\n\nGunakan konteks di atas jika pertanyaan baru merujuk ke topik sebelumnya.\n"
                    )
                general_prompt = (
                    "Kamu adalah asisten wisata Danau Toba yang ramah dan informatif.\n"
                    f"Pengguna bertanya: \"{query}\"\n\n"
                    "Tidak ada dokumen spesifik yang ditemukan di database untuk pertanyaan ini.\n"
                    "Jawab berdasarkan pengetahuan umummu jika pertanyaan masih berkaitan "
                    "dengan pariwisata, budaya Batak, Sumatera Utara, atau topik yang tidak terlalu jauh dari konteks wisata.\n"
                    "Jika pertanyaan BENAR-BENAR tidak relevan (mengandung kata kasar, NSFW, "
                    "atau topik berbahaya), tolak dengan sopan dan arahkan ke topik wisata Danau Toba.\n"
                    f"{_greeting_rule_general}\n"
                    f"{_history_general}"
                    "Gunakan emoji dan format rapi. Jawab dalam Bahasa Indonesia."
                )
                llm_response = self.model._call_gemini_api(
                    general_prompt,
                    max_tokens=max_new_tokens,
                    temperature=temperature
                )
                if llm_response and len(llm_response.strip()) > 20:
                    return {
                        "response": llm_response,
                        "source": "llm_general",
                        "cache_used": False,
                        "response_time": time.time() - start_time,
                        "num_chunks": 0,
                        "context": "",
                        "cache_key": query_hash,
                    }
            except Exception as e:
                print(f"❌ LLM general knowledge error: {e}")

            # LLM juga gagal (API down) → pesan minimal
            return {
                "response": "Maaf, saya sedang tidak bisa memproses pertanyaan Anda saat ini. Silakan coba lagi dalam beberapa saat. 🙏",
                "source": "error",
                "cache_used": False,
                "response_time": time.time() - start_time,
                "num_chunks": 0,
                "context": "",
                "cache_key": query_hash,
            }

        # Build context — include source filename & page so Gemini can attribute info correctly
        context_parts = []
        for i, doc in enumerate(relevant_docs, 1):
            content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
            content = content.strip()
            if content and len(content) > 50:
                # Extract source metadata from document
                meta        = doc.metadata if hasattr(doc, 'metadata') else {}
                src_file    = os.path.basename(meta.get('source', 'dokumen'))
                src_label   = src_file.replace('.pdf', '').replace('_', ' ').replace('-', ' ').title()
                page_num    = meta.get('page', '?')
                context_parts.append(f"[Sumber {i} | {src_label} | hal. {page_num}]\n{content}")
        
        context = "\n\n".join(context_parts)

        # For listing/category queries, prepend structured locations.json data so
        # all known places for that category are always included.
        if self._is_listing_query(retrieval_query):
            structured_ctx = self._get_locations_json_context(retrieval_query)
            if structured_ctx:
                context = structured_ctx + "\n\n" + context if context else structured_ctx
                print(f"📍 Injected structured locations context ({len(structured_ctx)} chars)")

        print(f"📄 Retrieved {len(relevant_docs)} chunks, context: {len(context)} chars")
        
        # Generate response
        generation_start = time.time()
        try:
            response = self.model.generate_response(
                query=query,
                context=context,
                chat_history=chat_history or [],
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                user_preferences=user_preferences or [],
                is_first_message=is_first_message,
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
