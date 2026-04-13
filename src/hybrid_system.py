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
    # Sistem ini menggunakan HYBRID RETRIEVAL: FAISS (dense) + BM25 (sparse).
    #
    # Pendekatan ini didukung oleh literatur:
    #   • Karpukhin et al. (2020) "Dense Passage Retrieval" (Facebook AI)
    #     → embedding vektor unggul untuk semantic matching
    #   • Robertson & Zaragoza (2009) "The Probabilistic Relevance Framework:
    #     BM25 and Beyond" → BM25 unggul untuk exact keyword matching
    #   • Ma et al. (2021) "Simple yet Effective Neural Ranking and Reranking
    #     Baselines for Cross-Lingual Information Retrieval" → hybrid BM25+dense
    #     konsisten memberikan hasil lebih baik dari masing-masing komponen
    #
    # FAISS + DistanceStrategy.COSINE mengembalikan JARAK L2 (bukan similarity).
    # Artinya: nilai LEBIH KECIL = LEBIH MIRIP  (0.0 = identik, > 1.0 = jauh)
    #
    # Setiap chunk dinilai dengan HYBRID SCORE gabungan (0.0 – 1.0):
    #
    #   faiss_sim = 1 - (jarak / MAX_FAISS_DISTANCE)   ← kemiripan semantik/vektor (FAISS)
    #   bm25_norm = bm25_raw / (bm25_raw + 1)          ← kecocokan keyword probabilistik (BM25)
    #   hybrid    = faiss_sim × HYBRID_WEIGHT_VECTOR
    #             + bm25_norm × HYBRID_WEIGHT_KEYWORD
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
        "informasi mengenai ulasan",
        "ulasan untuk",
        "informasi mengenai lokasi",
        "belum tersedia dalam dokumen yang saya miliki",
        "belum tersedia secara rinci",
        "lokasi pasti",
        "tidak tersedia secara rinci",
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
        # BM25 index — built after documents are loaded
        # Reference: Robertson & Zaragoza (2009), "The Probabilistic Relevance Framework:
        # BM25 and Beyond". Foundation and Trends in Information Retrieval.
        self.bm25_index = None

    def _extract_place_name(self, query: str) -> Optional[str]:
        """Extract a likely place name from a user query like 'menu di Cantik Daijo Cafe'."""
        query_clean = re.sub(r'\s+', ' ', query).strip(" ?!.,")
        patterns = [
            # Format dengan 'di': "menu di X", "ulasan di X"
            r'(?:menu|alamat|harga|jam operasional|ulasan|review|fasilitas)\s+(?:makanan\s+)?di\s+(.+)$',
            r'(?:apa saja|apa|berapa|bagaimana)\s+.+?\s+di\s+(.+)$',
            r'(?:tentang|info(?:rmasi)?\s+(?:tentang)?)\s+(.+)$',
            # Format tanpa 'di': "ulasan D'Barans Cafe", "menu dbarans cafe"
            r'(?:menu|ulasan|review|alamat|harga|jam|fasilitas)\s+(.{4,})$',
            # Format lokasi: "X berada dimana", "X ada dimana", "X terletak dimana"
            r'(.+?)\s+(?:berada|terletak|ada)\s+(?:di\s+)?(?:mana|dimana)\s*[?.]?$',
            # Format: "dimana X", "di mana letak X"
            r'(?:dimana|di\s+mana)\s+(?:letak\s+|lokasi\s+|alamat\s+)?(.+?)\s*[?.]?$',
            # Format: "lokasi X dimana", "alamat X berada"
            r'(?:lokasi|letak|alamat)\s+(.+?)(?:\s+dimana|\s+berada|\s+ada|\s+terletak)\s*[?.]?$',
            # Format: "tempat penginapan X berada dimana", "hotel X ada dimana"
            r'(?:tempat\s+)?(?:penginapan|hotel|resort|villa|homestay|cafe|restoran|warung|rumah\s+makan|wisata)\s+(.+?)\s+(?:berada|ada|terletak|dimana|di\s+mana)',
            # Standalone type+name: "tempat penginapan labersa", "hotel labersa", "wisata sipiso-piso"
            # Fallback paling akhir — hanya aktif jika semua pattern di atas gagal
            r'(?:tempat\s+)?(?:penginapan|hotel|resort|villa|homestay|cafe|restoran|warung|rumah\s+makan|wisata|objek\s+wisata)\s+(.{4,})$',
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
        # Buang prefix tipe tempat: "tempat penginapan labersa" → "labersa"
        # Jika setelah strip masih >= 3 karakter
        TYPE_PREFIX = (
            r'^(?:tempat\s+)?'
            r'(?:penginapan|hotel|resort|villa|homestay|cafe|restoran|'
            r'warung|rumah\s+makan|wisata|objek\s+wisata)\s+'
        )
        stripped = re.sub(TYPE_PREFIX, '', cleaned, flags=re.IGNORECASE).strip(" ?!.,")
        if len(stripped) >= 3:
            cleaned = stripped
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

    def _find_specific_place_docs(self, query: str, limit: int = 10) -> List:
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
                # Window ±3: mencakup nama tempat, detail, menu, ulasan yang bisa
                # tersebar hingga beberapa chunk setelah header nama tempat di PDF
                if same_source and isinstance(idx, int) and isinstance(candidate_idx, int) and abs(candidate_idx - idx) <= 3:
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

        # Generic "wisata" / "tempat wisata" / "destinasi" without a specific category
        # → return ALL attraction categories (not kuliner/hotel/homestay)
        if not categories:
            generic_attraction_signals = [
                'wisata', 'destinasi', 'objek wisata', 'tempat wisata',
                'tempat liburan', 'rekomendasi wisata', 'tempat berkunjung',
                'jalan-jalan', 'jalan jalan', 'liburan',
            ]
            # Exclude: food-specific queries should NOT trigger attraction listing
            culinary_signals = [
                'makan', 'kuliner', 'restoran', 'restaurant', 'warung',
                'rumah makan', 'cafe', 'kafe', 'kedai', 'menu',
            ]
            has_attraction = any(sig in query_lower for sig in generic_attraction_signals)
            has_culinary = any(sig in query_lower for sig in culinary_signals)
            if has_attraction and not has_culinary:
                categories = list(self.ATTRACTION_CATEGORIES)

        # Remove duplicate categories while preserving order.
        return list(dict.fromkeys(categories))

    # Categories that are tourist ATTRACTIONS (not food, hotel, or accommodation)
    ATTRACTION_CATEGORIES = [
        'pantai', 'air_terjun', 'bukit', 'alam', 'budaya', 'rekreasi',
        'desa_wisata', 'geowisata', 'danau', 'tour',
    ]

    def _is_listing_query(self, query: str) -> bool:
        """Return True if the user is asking for a *list* of places (not a single place)."""
        q = query.lower()
        listing_signals = ['apa saja', 'semua', 'daftar', 'list', 'sebutkan', 'rekomendasikan',
                           'ada apa saja', 'apa aja', 'mana saja', 'berapa banyak',
                           'rekomendasi', 'tempat-tempat', 'tempat tempat']
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

    def _get_locations_json_context(self, query: str, user_preferences: list = None) -> str:
        """
        Build a structured context block from locations.json for category/listing queries.
        Lokasi diurutkan menggunakan Content-Based Filtering (CB score) saat
        user_preferences tersedia; fallback ke rating jika tidak ada preferensi.
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

        # ── Content-Based Filtering ranking ──────────────────────────────
        # Gunakan DecisionMakingAgent untuk menghitung CB score tiap lokasi
        # berdasarkan preferensi yang diekstrak dari query (budget, kategori,
        # aktivitas, tipe grup).  Jika tidak ada preferensi eksplisit, CB score
        # akan menggunakan nilai netral (0.5) sehingga rating tetap menentukan.
        try:
            from decision_agent import DecisionMakingAgent
        except ImportError:
            from src.decision_agent import DecisionMakingAgent

        agent = DecisionMakingAgent()

        # Gabungkan sinyal query + profile preferensi profil user (favorite_categories)
        pref_query = query
        if user_preferences:
            # Tambahkan kata kunci kategori ke query agar preference extraction
            # dapat mendeteksi kategori favorit user bahkan jika tidak disebut
            # secara eksplisit di query saat ini.
            pref_query = query + " " + " ".join(user_preferences)

        scored_locations = agent.rank_locations_cb(matched, pref_query)

        print(
            f"🎯 CB Ranking: {len(scored_locations)} lokasi diurutkan "
            f"(top cb_score={scored_locations[0]['cb_score'] if scored_locations else 'N/A'})"
        )

        lines = ["[Data Terstruktur: Lokasi Database]"]
        for i, loc in enumerate(scored_locations, 1):
            cb_score = loc.get('cb_score', 0.0)
            lines.append(
                f"Tempat {i}: {loc.get('name', 'N/A')} [Skor Relevansi: {cb_score:.2f}]\n"
                f"- Kategori : {loc.get('category', 'N/A')}\n"
                f"- Deskripsi: {loc.get('description', 'N/A')}\n"
                f"- Lokasi   : {loc.get('location', 'N/A')}\n"
                f"- Alamat   : {loc.get('address', 'N/A')}\n"
                f"- Harga    : {loc.get('price', 'N/A')}\n"
                f"- Jam Buka : {loc.get('hours', 'N/A')}\n"
                f"- Rating   : {loc.get('rating', 'N/A')}/5"
            )
        return "\n\n".join(lines)

    # ── Stop words untuk tokenisasi BM25 ────────────────────────────────────
    BM25_STOP_WORDS = {
        'apa', 'saja', 'ada', 'dan', 'atau', 'ini', 'itu', 'di',
        'ke', 'dari', 'untuk', 'dengan', 'pada', 'adalah', 'yang',
        'bagaimana', 'berapa', 'dimana', 'siapa', 'tentang',
        'info', 'informasi', 'tolong', 'bisa', 'boleh',
        'saya', 'kamu', 'kalian', 'kapan', 'apakah',
    }

    def _tokenize_for_bm25(self, text: str) -> List[str]:
        """Tokenisasi teks untuk BM25: buang stop words dan token pendek."""
        return [
            w.lower() for w in re.findall(r'\w+', text)
            if w.lower() not in self.BM25_STOP_WORDS and len(w) > 2
        ]

    def _build_bm25_index(self) -> None:
        """
        Bangun BM25Okapi index dari seluruh chunk yang sudah dimuat.

        BM25 (Okapi BM25) adalah model retrieval probabilistik berbasis
        term frequency dan inverse document frequency dengan normalisasi
        panjang dokumen. Diperkenalkan oleh Robertson et al. (1994) dan
        dijabarkan lebih lanjut di Robertson & Zaragoza (2009).

        Index dibangun sekali saat load_documents() dan digunakan setiap
        kali get_response() menghitung hybrid score.
        """
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            print("⚠️  rank-bm25 tidak terpasang. Jalankan: pip install rank-bm25")
            self.bm25_index = None
            return

        if not self.loaded_docs:
            self.bm25_index = None
            return

        tokenized_corpus = [
            self._tokenize_for_bm25(doc.page_content)
            for doc in self.loaded_docs
        ]
        self.bm25_index = BM25Okapi(tokenized_corpus)
        print(f"   ✅ BM25 index dibangun: {len(self.loaded_docs)} chunks")

    def _bm25_score(self, query: str, doc) -> float:
        """
        Kembalikan skor BM25 yang dinormalisasi ke rentang [0.0 – 1.0) untuk
        satu chunk yang sudah diambil oleh FAISS.

        Normalisasi: score / (score + 1) — fungsi monoton, terbatas di [0, 1).
        Fallback ke keyword overlap sederhana jika BM25 index belum tersedia.

        Parameter doc harus memiliki metadata['chunk_index'] yang berisi
        posisi chunk di self.loaded_docs (diset saat load_documents).
        """
        if self.bm25_index is None:
            # Fallback: keyword overlap sederhana
            text = doc.page_content if hasattr(doc, 'page_content') else str(doc)
            q_words = self._tokenize_for_bm25(query)
            if not q_words:
                return 0.0
            chunk_lower = text.lower()
            hits = sum(1 for w in q_words if w in chunk_lower)
            return hits / len(q_words)

        query_tokens = self._tokenize_for_bm25(query)
        if not query_tokens:
            return 0.0

        # Ambil posisi chunk di corpus BM25 via metadata chunk_index
        meta = getattr(doc, 'metadata', {})
        chunk_idx = meta.get('chunk_index')
        if chunk_idx is None or chunk_idx >= len(self.loaded_docs):
            # chunk_index tidak tersedia — fallback ke overlap
            text = doc.page_content if hasattr(doc, 'page_content') else str(doc)
            q_words = self._tokenize_for_bm25(query)
            if not q_words:
                return 0.0
            hits = sum(1 for w in q_words if w in text.lower())
            return hits / len(q_words)

        # Hitung skor BM25 untuk seluruh corpus, ambil skor chunk ini
        scores = self.bm25_index.get_scores(query_tokens)
        raw = float(scores[chunk_idx])

        # Normalisasi ke [0, 1): f(x) = x / (x + 1)
        return raw / (raw + 1.0) if raw > 0.0 else 0.0

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

        # Bangun BM25 index dari chunk yang sama
        print("📊 Building BM25 index...")
        self._build_bm25_index()

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
            # Defensive FAQ check: some queries are misrouted here but have a real
            # tourism FAQ answer (e.g. "seberapa jauh...").  Check before giving a
            # generic Gemini answer so the grounded answer is always preferred.
            if use_cache and not contextual_followup:
                faq_hit = self._search_faq(query)
                if faq_hit:
                    faq_response = faq_hit['answer']
                    _hash = self.kv_cache._hash_query(query)
                    self.kv_cache.put(query, faq_response, "from_faq")
                    print(f"📖 FAQ match (general_question path): {query[:60]}...")
                    return {
                        "response": faq_response,
                        "source": "cag_cache",
                        "cache_used": True,
                        "response_time": time.time() - start_time,
                        "num_chunks": 0,
                        "context": "from_faq",
                        "cache_key": _hash,
                    }
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

            specific_place_docs = self._find_specific_place_docs(retrieval_query, limit=min(k + 2, 10))

            # ── Hybrid Scoring (FAISS + BM25) ───────────────────────────────
            # Setiap chunk mendapat HYBRID SCORE (0.0–1.0) dari dua komponen:
            #
            #   1. faiss_sim : kemiripan semantik dari embedding vektor (FAISS)
            #                  konversi: makin kecil jarak FAISS → makin besar sim
            #   2. bm25_norm : skor BM25Okapi yang dinormalisasi ke [0,1)
            #                  menangkap exact keyword match + IDF weighting
            #
            # Kombinasi FAISS + BM25 didukung oleh:
            #   Karpukhin et al. (2020) DPR; Ma et al. (2021) hybrid retrieval
            #
            # Chunk LOLOS jika hybrid_score >= RELEVANCE_THRESHOLD
            # ─────────────────────────────────────────────────────────────────
            scored_chunks = []
            for doc, faiss_dist in raw_results:
                d         = float(faiss_dist)
                faiss_sim = max(0.0, 1.0 - d / self.MAX_FAISS_DISTANCE)
                bm25_norm = self._bm25_score(retrieval_query, doc)
                hybrid    = (faiss_sim * self.HYBRID_WEIGHT_VECTOR
                             + bm25_norm * self.HYBRID_WEIGHT_KEYWORD)
                scored_chunks.append((doc, d, faiss_sim, bm25_norm, hybrid))

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
                    f" | best: hybrid={top[4]:.2f} (vektor={top[2]:.2f}, bm25={top[3]:.2f})"
                )
        except Exception as e:
            print(f"❌ Retrieval error: {e}")
            relevant_docs = []
        retrieval_time = time.time() - retrieval_start

        # === Layer 1: no context from docs → fallback to LLM general knowledge ===
        if not relevant_docs:
            # For listing/category queries, try locations.json as a fallback source.
            if self._is_listing_query(retrieval_query):
                structured_ctx = self._get_locations_json_context(retrieval_query, user_preferences)
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
            structured_ctx = self._get_locations_json_context(retrieval_query, user_preferences)
            if structured_ctx:
                context = structured_ctx + "\n\n" + context if context else structured_ctx
                print(f"📍 Injected structured locations context ({len(structured_ctx)} chars)")

        # For transport / route queries, inject distance & transport data
        try:
            from location_service import is_transport_query, extract_route_places, build_transport_context
            if is_transport_query(query):
                origin_name, dest_name = extract_route_places(query)
                if origin_name and dest_name:
                    transport_ctx = build_transport_context(origin_name, dest_name)
                    if transport_ctx:
                        context = transport_ctx + "\n\n" + context if context else transport_ctx
                        print(f"🚗 Injected transport context ({len(transport_ctx)} chars)")
        except ImportError:
            pass

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

        # Retry once if response is invalid but context has substantial data.
        # This catches cases where the LLM says "belum tersedia" despite having
        # the relevant information in the provided context.
        if self._is_invalid_response(response) and len(context) > 300:
            print(f"⚠️ Invalid response detected with context available — retrying with stronger prompt...")
            try:
                retry_context = (
                    f"[PERINGATAN SISTEM: Jawaban sebelumnya ditolak karena mengatakan informasi 'tidak tersedia' "
                    f"padahal konteks dokumen menyediakan data. BACA ULANG konteks dengan teliti dan jawab "
                    f"berdasarkan informasi yang ADA. Jangan menuliskan 'belum tersedia' jika data bisa ditemukan di bawah.]\n\n"
                    + context
                )
                response = self.model.generate_response(
                    query=query,
                    context=retry_context,
                    chat_history=chat_history or [],
                    max_new_tokens=max_new_tokens,
                    temperature=max(temperature, 0.3),
                    user_preferences=user_preferences or [],
                    is_first_message=is_first_message,
                )
                print(f"🔄 Retry response: {len(response)} chars")
            except Exception as e:
                print(f"❌ Retry generation error: {e}")
        
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
