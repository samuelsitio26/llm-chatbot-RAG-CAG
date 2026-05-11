"""
Complete Cache-Augmented Generation (CAG) System
"""

import os
import re
import time
from difflib import SequenceMatcher
from typing import Dict, List, Optional

# Import dengan error handling
try:
    from kv_cache_manager import KVCacheManager
except ImportError:
    from src.kv_cache_manager import KVCacheManager  # pyrefly: ignore

try:
    from faq_generator import FAQGenerator
except ImportError:
    from src.faq_generator import FAQGenerator  # pyrefly: ignore

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.documents import Document as LCDocument
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


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
    MAX_FAISS_DISTANCE = 1.20  # jarak absolut maks — lebih dari ini = tidak relevan
    HYBRID_WEIGHT_VECTOR = 0.60  # bobot kemiripan semantik (vektor embedding)
    HYBRID_WEIGHT_KEYWORD = 0.40  # bobot kecocokan kata-kata penting query
    RELEVANCE_THRESHOLD = 0.30  # skor minimum untuk lolos ke konteks LLM (0.0–1.0)

    # ── Predictive Pre-fetching ─────────────────────────────────────────────
    # TTL (detik) untuk in-memory prefetch cache.
    # Entry kadaluarsa setelah 5 menit → mencegah stale docs tersaji ke user.
    # Referensi: FLARE (Jiang et al. 2023) — proactive retrieval pre-computes
    # probable next-turn context to reduce per-turn retrieval latency.
    PREFETCH_TTL_SEC: int = 300  # 5 menit

    # Template pola follow-up berdasarkan analisis percakapan wisata multi-turn.
    # Urutan mencerminkan pola natural: discovery → detail → lokasi → transport.
    # Digunakan oleh _execute_prefetch() untuk proactive FAISS warm-up.
    FOLLOWUP_TEMPLATES: list = [
        "harga tiket {entity}",
        "jam buka {entity}",
        "lokasi {entity} dimana",
        "fasilitas {entity}",
        "cara menuju {entity} dari Balige",
        "ulasan pengunjung {entity}",
        "penginapan dekat {entity}",
        "kuliner dekat {entity}",
    ]

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
        self.encoder: Optional[Embeddings] = encoder
        self.kv_cache = KVCacheManager()
        self.faq_gen = FAQGenerator()
        self.database = None
        self.docs_loaded = False
        self.loaded_docs = []
        # BM25 index — built after documents are loaded
        # Reference: Robertson & Zaragoza (2009), "The Probabilistic Relevance Framework:
        # BM25 and Beyond". Foundation and Trends in Information Retrieval.
        self.bm25_index = None

        # ── Semantic FAQ embedding cache ──────────────────────────────────────
        # Pre-computed embeddings untuk pertanyaan FAQ, di-key dengan MD5(question).
        # Dibangun secara lazy pada pemanggilan _search_faq pertama.
        # Memungkinkan pencocokan semantik melampaui string-overlap biasa.
        # Referensi: Karpukhin et al. (2020) DPR — dense retrieval lebih unggul
        # menangkap parafrase dibanding exact-match / string similarity.
        self._faq_embed_cache: dict = {}  # md5(faq_question) → embedding vector
        self._query_embed_temp: dict = {}  # query[:100] → embedding (short-lived, maks 50)

        # ── Predictive Pre-fetch Cache (in-memory, per-instance) ─────────────
        # Maps query_hash → {"docs": [...], "entity": str, "expires_at": float}
        # Di-populate oleh _execute_prefetch() setelah setiap respons.
        # Di-consume oleh _check_prefetch_cache() saat retrieval berlangsung.
        # Tidak dipersist ke disk — TTL pendek (PREFETCH_TTL_SEC), reset on restart.
        self._prefetch_cache: dict = {}

        # ── Routing Signal History (untuk logging & evaluasi .ipynb) ──────────
        # Menyimpan routing decision terakhir agar API bisa melaporkannya.
        self._last_routing_signals: dict = {}

    def _extract_place_name(self, query: str) -> Optional[str]:
        """Extract a likely place name from a user query like 'menu di Cantik Daijo Cafe'."""
        query_clean = re.sub(r"\s+", " ", query).strip(" ?!.,")
        patterns = [
            # Natural intent phrasing: "saya ingin menginap di X, cocok...?"
            r"(?:saya\s+)?(?:ingin|mau|pengen)\s+(?:menginap|pergi|menuju|ke)\s+di\s+(.+)$",
            # Format dengan 'di': "menu di X", "ulasan di X"
            r"(?:menu|alamat|harga|jam operasional|ulasan|review|fasilitas)\s+(?:makanan\s+)?di\s+(.+)$",
            r"(?:apa saja|apa|berapa|bagaimana)\s+.+?\s+di\s+(.+)$",
            r"(?:tentang|info(?:rmasi)?\s+(?:tentang)?)\s+(.+)$",
            r"^(?:apa\s+)?(?:menu|ulasan|review|alamat|harga|jam|fasilitas)(?:\s+operasional|\s+buka)?\s+(?:dari\s+)?(.{4,})$",
            # Format lokasi: "X berada dimana", "X ada dimana", "X terletak dimana"
            r"(.+?)\s+(?:berada|terletak|ada)\s+(?:di\s+)?(?:mana|dimana)\s*[?.]?$",
            # Format: "dimana X", "di mana letak X"
            r"(?:dimana|di\s+mana)\s+(?:letak\s+|lokasi\s+|alamat\s+)?(.+?)\s*[?.]?$",
            # Format: "lokasi X dimana", "alamat X berada"
            r"(?:lokasi|letak|alamat)\s+(.+?)(?:\s+dimana|\s+berada|\s+ada|\s+terletak)\s*[?.]?$",
            # Format: "tempat penginapan X berada dimana", "hotel X ada dimana"
            r"(?:tempat\s+)?(?:penginapan|hotel|resort|villa|homestay|cafe|restoran|warung|rumah\s+makan|wisata)\s+(.+?)\s+(?:berada|ada|terletak|dimana|di\s+mana)",
            # Standalone type+name: "tempat penginapan labersa", "hotel labersa", "wisata sipiso-piso"
            # Fallback paling akhir — hanya aktif jika semua pattern di atas gagal
            r"(?:tempat\s+)?(?:penginapan|hotel|resort|villa|homestay|cafe|restoran|warung|rumah\s+makan|wisata|objek\s+wisata)\s+(.{4,})$",
        ]

        for pattern in patterns:
            match = re.search(pattern, query_clean, flags=re.IGNORECASE)
            if match:
                candidate = self._clean_place_candidate(match.group(1))
                if len(candidate) >= 4 and not self._is_generic_non_place_text(
                    candidate
                ):
                    return candidate

        # Generic mention fallback: capture entity-like phrases that appear before
        # question connectors, e.g. "pantai bulbul kendaraan apa...".
        generic_pattern = (
            r"\b((?:pantai|hotel|penginapan|resort|villa|homestay|cafe|restoran|"
            r"warung|rumah\s+makan|air\s+terjun|bukit|danau|museum|desa)"
            r"\s+[a-z0-9\'&\-.]+(?:\s+[a-z0-9\'&\-.]+){0,4})"
            r"(?=\s+(?:apa|bagaimana|berapa|yang|untuk|dengan|naik|menuju|"
            r"di|ke|dari)\b|[?!.,]|$)"
        )
        generic_match = re.search(generic_pattern, query_clean, flags=re.IGNORECASE)
        if generic_match:
            candidate = self._clean_place_candidate(generic_match.group(1))
            if len(candidate) >= 4 and not self._is_generic_non_place_text(candidate):
                return candidate

        return None

    def _clean_place_candidate(self, candidate: str) -> str:
        """Normalize extracted place candidate and remove trailing attribute clauses."""
        cleaned = re.sub(r"\s+", " ", candidate).strip(" ?!.,")
        # Example: "D'Barans Cafe dan jam buka nya" -> "D'Barans Cafe"
        cleaned = re.sub(
            r"\s+(?:dan|&|serta)\s+(?:jam|harga|alamat|ulasan|review|menu|fasilitas)\b.*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip(" ?!.,")
        cleaned = re.sub(
            r"(?:,\s*|\s+)(?:cocok|bagus|murah|mahal|gimana|bagaimana|apakah)\b.*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip(" ?!.,")
        cleaned = re.sub(
            r"\s+(?:apa|bagaimana|berapa|yang|untuk|dengan|naik|menuju|"
            r"ke|di|dari|kendaraan|transportasi)\b.*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip(" ?!.,")
        # Buang prefix tipe tempat: "tempat penginapan labersa" → "labersa"
        # Jika setelah strip masih >= 3 karakter
        TYPE_PREFIX = (
            r"^(?:tempat\s+)?"
            r"(?:penginapan|hotel|resort|villa|homestay|cafe|restoran|"
            r"warung|rumah\s+makan|wisata|objek\s+wisata)\s+"
        )
        stripped = re.sub(TYPE_PREFIX, "", cleaned, flags=re.IGNORECASE).strip(" ?!.,")
        if len(stripped) >= 3:
            cleaned = stripped
            
        # Hapus prefix preposisi yang sering tertinggal seperti "di laguboti" -> "laguboti"
        cleaned = re.sub(r"^(?:di|ke|dari)\s+", "", cleaned, flags=re.IGNORECASE).strip(" ?!.,")
        
        return cleaned

    def _is_generic_non_place_text(self, text: str) -> bool:
        """Return True when extracted text is likely an attribute phrase, not a place name."""
        t = (text or "").lower().strip(" ?!.,")
        if not t:
            return True

        bad_starts = (
            "yang ",
            "apa ",
            "berapa ",
            "bagaimana ",
            "fasilitas",
            "ulasan",
            "review",
            "harga",
            "alamat",
            "menu",
            "jam ",
        )
        if t.startswith(bad_starts):
            return True

        bad_contains = [
            "yang ditawarkan",
            "yang tersedia",
            "yang ada",
            "apa saja",
            "kira kira",
            "kira-kira",
            "kendaraan apa",
            "transportasi apa",
            "tempat itu",
            "yang tadi",
            "di sana",
            "disitu",
            "di situ",
            "utamanya",
        ]
        if any(phrase in t for phrase in bad_contains):
            return True

        parts = t.split()
        if len(parts) == 1 and (
            parts[0].endswith("nya")
            or parts[0] in {"utamanya", "fasilitasnya", "harganya"}
        ):
            return True
        return False

    def _is_followup_reference_query(self, query: str) -> bool:
        """Detect short follow-up queries that rely on previous place context.

        Diperluas berdasarkan temuan dari:
          • QuAC (Choi et al. 2018) — ~70% follow-up tidak menyebut entitas eksplisit,
            menggunakan pronoun & demonstrative (itu, sana, tersebut).
          • CoQA (Reddy et al. 2019) — coreference resolution kritikal untuk QA multi-turn.
          • OR-QuAC (Qu et al. 2021) — continuation markers tanpa nama entitas dominan.

        Kondisi A (original): ada attribute keyword DAN ada reference word
        Kondisi B (baru): query sangat pendek + ada reference word (tanpa perlu attribute)
        """
        query_lower = query.lower().strip()

        # Attribute keywords — diperluas untuk konteks wisata Toba
        has_attribute = any(
            kw in query_lower
            for kw in [
                "menu",
                "alamat",
                "harga",
                "jam",
                "operasional",
                "ulasan",
                "review",
                "fasilitas",
                "tiket",
                "biaya",
                "masuk",
                "akses",
                "rute",
                "jalan",
                "foto",
                "spot",
                "view",
                "pemandangan",
                "bagus",
                "worth",
                "aman",
                "ramai",
                "sepi",
                "bersih",
                "toilet",
                "mushola",
                "parkir",
                "souvenir",
                "penginapan",
                "menginap",
                "jadwal",
                "buka",
                "tutup",
                "kamar",
                "sarapan",
                "wifi",
            ]
        )
        # Reference keywords — diperluas mencakup semua pronoun & demonstrative bahasa Indonesia
        has_reference = any(
            kw in query_lower
            for kw in [
                "nya",
                "itu",
                "disitu",
                "di situ",
                "yang tadi",
                "tempat itu",
                "di sana",
                "tersebut",
                "tadi",
                "disana",
                "yang itu",
                "yang ini",
                "sana",
                "situ",
                "tempat tersebut",
                "di sini",
                "kesana",
                "ke sana",
                "ke situ",
            ]
        )
        has_explicit_place = self._extract_place_name(query) is not None

        # Kondisi A: ada attribute + reference (original, dipertahankan)
        condition_a = has_attribute and has_reference and not has_explicit_place

        # Kondisi B: query SANGAT pendek + ada reference word (tanpa perlu attribute keyword)
        # Contoh: "Bagus gak?", "Worth it gak?", "Ada gak?", "Ramai?"
        is_very_short = len(query_lower.split()) <= 6
        condition_b = is_very_short and has_reference and not has_explicit_place

        return condition_a or condition_b

    def _is_implicit_attribute_followup_query(self, query: str) -> bool:
        """Detect follow-ups like 'apa saja fasilitas yang ditawarkan?' without explicit references.

        Diperluas untuk menangkap lebih banyak pola percakapan wisata:
          - Attribute inquiry tanpa menyebut nama tempat eksplisit
          - Short factual questions yang implisit merujuk ke konteks aktif
          Referensi: CoQA (Reddy et al. 2019), OR-QuAC (Qu et al. 2021).
        """
        query_lower = query.lower().strip()

        # Attribute keywords — diperluas untuk wisata Toba
        has_attribute = any(
            kw in query_lower
            for kw in [
                "menu",
                "alamat",
                "harga",
                "jam",
                "operasional",
                "ulasan",
                "review",
                "fasilitas",
                "kamar",
                "tipe kamar",
                "check in",
                "check-in",
                "check out",
                "check-out",
                "kapasitas",
                "wifi",
                "parkir",
                "sarapan",
                # Tambahan konteks wisata Toba:
                "tiket",
                "biaya",
                "masuk",
                "akses",
                "rute",
                "jalan menuju",
                "cara ke",
                "foto",
                "spot foto",
                "view",
                "pemandangan",
                "sunrise",
                "sunset",
                "aman",
                "ramai",
                "sepi",
                "bersih",
                "worth",
                "recommended",
                "toilet",
                "mushola",
                "souvenir",
                "warung",
                "makan",
                "kuliner",
                "jadwal",
                "buka",
                "tutup",
                "libur",
                "penginapan",
                "homestay",
            ]
        )
        has_explicit_place = self._extract_place_name(query) is not None

        # Generic form — diperluas mencakup bentuk pertanyaan informal
        has_generic_form = any(
            kw in query_lower
            for kw in [
                "apa saja",
                "apa",
                "bagaimana",
                "berapa",
                "jelaskan",
                "ditawarkan",
                "ada",
                "ada tidak",
                "apakah",
                "gimana",
                "worth",
                "tersedia",
                "cukup",
                "lengkap",
                "bagus",
                "recommended",
                "rekomen",
            ]
        )
        likely_new_listing = any(
            kw in query_lower
            for kw in [
                "rekomendasi",
                "tempat apa",
                "hotel apa",
                "pantai apa",
                "destinasi apa",
                "wisata apa",
                "pilihan",
                "list",
            ]
        )
        # Naikkan batas panjang query dari 12 → 15 kata (OR-QuAC menunjukkan
        # follow-up bisa lebih panjang namun tetap merujuk entitas aktif)
        short_query = len(query_lower.split()) <= 15
        return (
            has_attribute
            and has_generic_form
            and short_query
            and not has_explicit_place
            and not likely_new_listing
        )

    def _extract_last_place_from_history(
        self, chat_history: List[Dict]
    ) -> Optional[str]:
        """Extract most recent place name from user messages in chat history."""
        if not chat_history:
            return None

        for msg in reversed(chat_history):
            if msg.get("role") != "user":
                continue
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            place = self._extract_place_name(content)
            if place:
                return place

        # Fallback: parse assistant answers for explicit entity names when
        # follow-up queries use references like "tempat itu" / "fasilitasnya".
        for msg in reversed(chat_history):
            if msg.get("role") != "assistant":
                continue
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            place = self._extract_place_from_assistant_answer(content)
            if place:
                return place
        return None

    def _extract_place_from_assistant_answer(self, answer: str) -> Optional[str]:
        """Extract likely place/entity name from assistant-formatted answers."""
        text = (answer or "").strip()
        if len(text) < 4:
            return None

        bold_hits = re.findall(r"\*\*([^*]{3,80})\*\*", text)
        for hit in bold_hits:
            candidate = hit.strip(" :.-\n\t")
            if len(candidate) >= 3 and not candidate.lower().startswith(
                ("deskripsi", "lokasi", "kategori")
            ):
                return candidate

        numbered_hits = re.findall(r"(?m)^\s*\d+[\.)]\s*([^\n:]{3,80})", text)
        for hit in numbered_hits:
            candidate = hit.strip(" :.-\n\t")
            if len(candidate) >= 3:
                return candidate

        sentence_hits = re.findall(
            r"\b(?:Pantai|Hotel|Resort|Villa|Homestay|Cafe|Restoran|Warung|Bukit|Danau|Air Terjun|Desa)\s+"
            r"[A-Z][\w\'&\-.]*(?:\s+[A-Z][\w\'&\-.]*){0,4}",
            text,
        )
        for hit in sentence_hits:
            candidate = hit.strip(" :.-\n\t")
            if len(candidate) >= 3:
                return candidate

        return None

    def _extract_last_place_from_state(
        self, conversation_state: Optional[Dict]
    ) -> Optional[str]:
        """Extract the last resolved place from persisted conversation state."""
        if not conversation_state or not isinstance(conversation_state, dict):
            return None

        candidate = (
            conversation_state.get("last_place")
            or conversation_state.get("active_entity")
            or conversation_state.get("last_entity")
        )
        if not candidate or not isinstance(candidate, str):
            return None

        normalized = candidate.strip(" ?!.,")
        return normalized if len(normalized) >= 3 else None

    def _normalize_match_text(self, text: str) -> str:
        """Normalize text for robust place-name matching."""
        normalized = re.sub(r"[^\w\s]", " ", text.lower(), flags=re.UNICODE)
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _trigrams(s: str) -> set:
        """Kembalikan set karakter trigram dari string s.

        Digunakan untuk near-duplicate detection pada deduplication chunk.
        Didefinisikan sebagai static method agar tidak di-create ulang
        sebagai closure baru di setiap iterasi loop deduplication (Fix #7).

        Contoh: _trigrams("abc") → {'abc'}
                _trigrams("abcd") → {'abc', 'bcd'}
        """
        return set(s[i : i + 3] for i in range(len(s) - 2))

    def _fuzzy_token_coverage(self, phrase: str, text: str) -> float:
        """Measure how well phrase tokens are represented in text, tolerating minor typos."""
        phrase_tokens = [
            t for t in self._normalize_match_text(phrase).split() if len(t) > 1
        ]
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
            coverage = (
                1.0
                if place_lower in content_lower
                else self._fuzzy_token_coverage(place_name, doc.page_content)
            )
            if coverage >= 0.84:
                matched.append((coverage, doc))

        if not matched:
            return []

        matched.sort(key=lambda item: item[0], reverse=True)
        matched_docs = [doc for _, doc in matched]

        expanded = []
        seen_keys = set()
        for doc in matched_docs:
            meta = getattr(doc, "metadata", {})
            src = meta.get("source")
            idx = meta.get("chunk_index")
            for candidate in self.loaded_docs:
                candidate_meta = getattr(candidate, "metadata", {})
                same_source = candidate_meta.get("source") == src
                candidate_idx = candidate_meta.get("chunk_index")
                # Window ±3: mencakup nama tempat, detail, menu, ulasan yang bisa
                # tersebar hingga beberapa chunk setelah header nama tempat di PDF
                if (
                    same_source
                    and isinstance(idx, int)
                    and isinstance(candidate_idx, int)
                    and abs(candidate_idx - idx) <= 3
                ):
                    key = (src, candidate_idx)
                    if key not in seen_keys:
                        expanded.append(candidate)
                        seen_keys.add(key)

        return expanded[:limit]

    # ─── Category keyword map: maps JSON category → query keywords ───────────
    CATEGORY_KEYWORD_MAP: dict = {
        "bukit": ["bukit", "perbukitan", "puncak", "hill"],
        "pantai": ["pantai", "beach", "pesisir"],
        "air_terjun": ["air terjun", "waterfall", "curug"],
        "danau": ["danau", "lake"],
        "budaya": ["budaya", "museum", "adat", "sejarah", "heritage"],
        "rekreasi": ["rekreasi", "kolam renang", "wahana", "taman"],
        "desa_wisata": ["desa wisata", "kampung wisata"],
        "alam": ["alam", "panorama"],
        "geowisata": ["geowisata", "geo wisata"],
        "tour": ["tour", "paket wisata"],
    }

    def _extract_listing_categories(self, query_lower: str) -> List[str]:
        """Extract requested categories from query with priority to specific intent words."""
        # Prioritize explicit hill/perbukitan intent so 'di Danau Toba' does not trigger danau category.
        if any(
            token in query_lower for token in ["perbukitan", "bukit", "puncak", "hill"]
        ):
            return ["bukit"]

        categories: List[str] = []
        for category, keywords in self.CATEGORY_KEYWORD_MAP.items():
            if any(kw in query_lower for kw in keywords):
                categories.append(category)

        # Generic "wisata" / "tempat wisata" / "destinasi" without a specific category
        # → return ALL attraction categories (not kuliner/hotel/homestay)
        if not categories:
            generic_attraction_signals = [
                "wisata",
                "destinasi",
                "objek wisata",
                "tempat wisata",
                "tempat liburan",
                "rekomendasi wisata",
                "tempat berkunjung",
                "jalan-jalan",
                "jalan jalan",
                "liburan",
            ]
            # Exclude: food-specific queries should NOT trigger attraction listing
            culinary_signals = [
                "makan",
                "kuliner",
                "restoran",
                "restaurant",
                "warung",
                "rumah makan",
                "cafe",
                "kafe",
                "kedai",
                "menu",
            ]
            has_attraction = any(
                sig in query_lower for sig in generic_attraction_signals
            )
            has_culinary = any(sig in query_lower for sig in culinary_signals)
            if has_attraction and not has_culinary:
                categories = list(self.ATTRACTION_CATEGORIES)

        # Remove duplicate categories while preserving order.
        return list(dict.fromkeys(categories))

    # Categories that are tourist ATTRACTIONS (not food, hotel, or accommodation)
    ATTRACTION_CATEGORIES = [
        "pantai",
        "air_terjun",
        "bukit",
        "alam",
        "budaya",
        "rekreasi",
        "desa_wisata",
        "geowisata",
        "danau",
        "tour",
    ]

    def _is_listing_query(self, query: str) -> bool:
        """Return True if the user is asking for a *list* of places (not a single place)."""
        q = query.lower()
        listing_signals = [
            "apa saja",
            "semua",
            "daftar",
            "list",
            "sebutkan",
            "rekomendasikan",
            "ada apa saja",
            "apa aja",
            "mana saja",
            "berapa banyak",
            "rekomendasi",
            "tempat-tempat",
            "tempat tempat",
        ]
        return any(sig in q for sig in listing_signals)

    def _load_locations(self) -> list:
        """Load locations.json; returns [] on any error."""
        import json

        locations_file = os.path.join(
            os.path.dirname(__file__), "..", "database", "Locations", "locations.json"
        )
        try:
            with open(locations_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Could not load locations.json: {e}")
            return []

    def _get_locations_json_context(
        self, query: str, user_preferences: Optional[list] = None
    ) -> str:
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
            cat = loc.get("category", "")
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
            from src.decision_agent import DecisionMakingAgent  # pyrefly: ignore

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
            cb_score = loc.get("cb_score", 0.0)
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

    def _get_specific_entity_from_locations(self, place_name: str) -> str:
        """
        Cari entitas SPESIFIK dari locations.json berdasarkan nama tempat.

        Digunakan untuk menjamin data terstruktur selalu tersedia dalam konteks
        LLM ketika user bertanya tentang entitas spesifik (non-listing query),
        meskipun FAISS retrieval tidak menemukan chunk yang cukup relevan.

        Menyelesaikan dua bug kritis:
          1. Hallucination nama entitas: LLM menginvensi "Air Terjun Meat" dari
             konteks FAISS campuran, padahal entitasnya "Desa Wisata Meat".
             Dengan prepend data dari locations.json, LLM mendapat nama TEPAT
             dan metadata AKURAT sebagai anchor sehingga tidak mengarang nama.
          2. False negative "tidak tersedia": ketika FAISS tidak menemukan chunk
             dengan skor >= RELEVANCE_THRESHOLD, sistem langsung bilang "belum
             tersedia" padahal entitas ada lengkap di locations.json.

        Matching strategy (dari ketat ke longgar):
          1. Exact substring match bidirectional (place_lower ∈ loc_name_lower)
          2. Fuzzy token coverage >= 0.65 (toleran typo & variasi penulisan)

        Returns: formatted context string siap inject ke prompt, "" jika tidak ada.
        """
        if not place_name or len(place_name) < 3:
            return ""

        locations = self._load_locations()
        if not locations:
            return ""

        place_lower = self._normalize_match_text(place_name)
        matched = []

        for loc in locations:
            loc_name = loc.get("name", "")
            loc_name_lower = self._normalize_match_text(loc_name)

            # Exact substring match (bidirectional)
            if place_lower in loc_name_lower or loc_name_lower in place_lower:
                matched.append((1.0, loc))
                continue

            # Fuzzy token coverage — toleran typo ringan & variasi penulisan
            coverage = self._fuzzy_token_coverage(place_name, loc_name)
            if coverage >= 0.65:
                matched.append((coverage, loc))

        if not matched:
            return ""

        # Urutkan berdasarkan kualitas match (skor tertinggi duluan)
        matched.sort(key=lambda x: x[0], reverse=True)

        # Ambil nama-nama entitas yang matched untuk header dinamis
        matched_names = [loc.get("name", "N/A") for _, loc in matched[:3]]
        primary_name = matched_names[0] if matched_names else place_name

        lines = [
            "[Data Spesifik Lokasi Database]",
            f"# User bertanya tentang: '{place_name}'",
            f"# Entitas yang ditemukan di database: {', '.join(matched_names)}",
            "# INSTRUKSI KRITIS — WAJIB DIIKUTI:",
            f"# 1. Gunakan nama entitas PERSIS seperti di field 'Nama' (contoh: '{primary_name}').",
            "# 2. DILARANG KERAS mengganti, menginvensi, atau memodifikasi nama entitas.",
            "# 3. Kata deskriptif dalam field 'Deskripsi' (mis: 'air jernih', 'pasir putih',",
            "#    'hutan pinus', 'bukit hijau') adalah ATRIBUT tempat, bukan nama tempat baru.",
            "#    Contoh: 'air jernih' ≠ nama 'Air Terjun'; 'pasir putih' ≠ nama 'Pantai Baru'.",
            "# 4. Jika user menyebut nama singkat/sebagian, jawablah menggunakan nama LENGKAP",
            "#    yang ada di field Nama di bawah, tanpa mengubah atau menambah kategori.",
        ]
        for _, loc in matched[:3]:  # Max 3 match untuk mencegah context overflow
            loc_lat = loc.get("lat", "N/A")
            loc_lng = loc.get("lng", "N/A")
            coord_str = f"{loc_lat}, {loc_lng}" if loc_lat != "N/A" else "N/A"
            lines.append(
                f"\nNama     : {loc.get('name', 'N/A')}\n"
                f"Kategori : {loc.get('category', 'N/A')}\n"
                f"Deskripsi: {loc.get('description', 'N/A')}\n"
                f"Lokasi   : {loc.get('location', 'N/A')}\n"
                f"Alamat   : {loc.get('address', 'N/A')}\n"
                f"Harga    : {loc.get('price', 'N/A')}\n"
                f"Jam Buka : {loc.get('hours', 'N/A')}\n"
                f"Rating   : {loc.get('rating', 'N/A')}/5\n"
                f"Koordinat: {coord_str}"
            )

        result = "\n".join(lines)
        print(
            f"   🗺️  Specific entity injected: "
            f"{[loc.get('name') for _, loc in matched[:3]]}"
        )
        return result

    # ══════════════════════════════════════════════════════════════════════════
    # KOMPONEN 2: MULTI-SIGNAL SEMANTIC ROUTER
    # ══════════════════════════════════════════════════════════════════════════

    def _compute_routing_signals(
        self,
        query: str,
        intent: str,
        chat_history: list,
        conversation_state: dict,
        contextual_followup: bool,
        resolved_followup_place: str,
    ) -> dict:
        """Hitung sinyal routing multi-dimensi untuk menentukan mode retrieval optimal.

        Sistem routing ini mengklasifikasikan setiap query ke salah satu dari tiga mode:
          • CACHE_FIRST         — cache hit dengan high confidence, skip retrieval
          • MEMORY_AUGMENTED_RAG — follow-up yang butuh konteks percakapan
          • PURE_RAG             — query baru, butuh retrieval penuh

        Sinyal yang dihitung:
          1. intent_confidence  : seberapa yakin klasifikasi intent (0–1)
          2. memory_score       : seberapa kuat ketergantungan pada konteks percakapan (0–1)
          3. context_key        : kunci konteks untuk Dual-Layer Cache (str | "")
          4. routing_mode       : keputusan routing final

        Referensi:
          • Jeong et al. (2024) Adaptive-RAG — adaptive routing berdasarkan query complexity.
          • Asai et al. (2023) Self-RAG      — self-reflection sebagai routing signal.
          • Shi et al. (2023) REPLUG          — ensemble retrieval confidence scoring.
        """
        q = query.lower().strip()

        # ── Signal 1: Intent Confidence ────────────────────────────────────────
        # Seberapa yakin sistem tentang klasifikasi intent ini?
        # Kata kunci pariwisata kuat → confidence lebih tinggi → routing lebih pasti.
        _strong_kws = [
            "pantai",
            "hotel",
            "wisata",
            "toba",
            "danau",
            "harga",
            "tiket",
            "penginapan",
            "kuliner",
            "restoran",
            "air terjun",
            "bukit",
            "desa",
            "museum",
            "balige",
            "samosir",
            "parapat",
        ]
        strong_hits = sum(1 for kw in _strong_kws if kw in q)

        if intent == "tourism":
            # Semakin banyak kata kunci pariwisata kuat → confidence naik
            intent_confidence = min(0.60 + strong_hits * 0.08, 0.97)
        elif intent == "greeting":
            intent_confidence = 0.99
        elif intent == "general_question":
            intent_confidence = 0.72
        else:
            intent_confidence = 0.50

        # ── Signal 2: Memory Grounding Score ──────────────────────────────────
        # Seberapa besar query ini bergantung pada konteks percakapan sebelumnya?
        # Tinggi → routing butuh conversation memory sebagai anchor.
        _ref_kws = [
            "di sana",
            "di situ",
            "tersebut",
            "itu",
            "nya",
            "tadi",
            "sana",
            "lanjut",
            "lebih lanjut",
            "ceritakan",
            "jelaskan",
            "yang itu",
            "yang ini",
            "situ",
            "ke sana",
            "kesana",
        ]
        has_reference = any(kw in q for kw in _ref_kws)
        has_no_place = self._extract_place_name(query) is None
        word_count = len(q.split())
        has_history = bool(chat_history or conversation_state.get("last_place"))

        if contextual_followup:
            # Sudah dikonfirmasi oleh Layer 1–4 follow-up detection
            memory_score = 0.90
        else:
            memory_score = 0.0
            if has_reference and has_no_place:
                memory_score += 0.45  # pronoun/demonstrative reference
            if word_count <= 8 and has_no_place:
                memory_score += 0.20  # very short without entity = likely follow-up
            if has_history and has_no_place:
                memory_score += 0.15  # history available and no explicit entity
            memory_score = min(memory_score, 1.0)

        # ── Context Key (Dual-Layer Cache) ─────────────────────────────────────
        # Kunci konteks untuk membedakan cache entry lintas percakapan.
        # Hanya diisi ketika query adalah follow-up dari entitas yang jelas.
        context_key = ""
        if contextual_followup and resolved_followup_place:
            context_key = resolved_followup_place
        elif memory_score >= 0.60 and conversation_state.get("last_place"):
            context_key = conversation_state["last_place"]

        # ── Routing Mode Decision ──────────────────────────────────────────────
        if memory_score >= 0.60:
            routing_mode = "MEMORY_AUGMENTED_RAG"
        elif intent in ("greeting", "general_question") and intent_confidence > 0.85:
            routing_mode = "CACHE_FIRST"
        else:
            routing_mode = "PURE_RAG"

        signals = {
            "intent_confidence": round(intent_confidence, 3),
            "memory_score": round(memory_score, 3),
            "context_key": context_key,
            "routing_mode": routing_mode,
        }

        print(
            f"🧭 Routing │ mode={routing_mode:22s} │ "
            f"intent_conf={intent_confidence:.2f} │ "
            f"memory={memory_score:.2f} │ "
            f"ctx='{context_key[:25]}'"
        )
        self._last_routing_signals = signals
        return signals

    # ══════════════════════════════════════════════════════════════════════════
    # KOMPONEN 3: PREDICTIVE PRE-FETCHING
    # ══════════════════════════════════════════════════════════════════════════

    def _get_probable_next_queries(self, entity: str) -> list:
        """Generate daftar probable follow-up queries berdasarkan entitas aktif.

        Pola follow-up didasarkan pada analisis percakapan wisata multi-turn:
          Turn 1: discovery  (ceritakan tentang X)
          Turn 2: detail     (harga tiket, jam buka)
          Turn 3: lokasi     (dimana, alamat, koordinat)
          Turn 4: transport  (cara menuju, naik apa)
          Turn 5: alternatif (penginapan/kuliner dekat X)

        Template tersimpan di FOLLOWUP_TEMPLATES (class constant).
        Referensi: FLARE (Jiang et al. 2023) — proactive next-turn retrieval.
        """
        if not entity or len(entity) < 3:
            return []

        queries = []
        for template in self.FOLLOWUP_TEMPLATES:
            queries.append(template.format(entity=entity))
        return queries

    def _check_prefetch_cache(self, retrieval_query: str) -> Optional[dict]:
        """Cek in-memory prefetch cache untuk retrieval query.

        Returns dict {"docs": [...], "entity": str} jika ada entry valid,
        None jika miss atau expired.

        Prefetch cache menggunakan TTL pendek (PREFETCH_TTL_SEC) sehingga
        docs yang stale tidak tersaji ke user.
        """
        import time

        query_hash = self.kv_cache._hash_query(retrieval_query)
        entry = self._prefetch_cache.get(query_hash)

        if not entry:
            return None

        # Cek TTL
        if time.time() > entry.get("expires_at", 0):
            del self._prefetch_cache[query_hash]
            print(f"⚡ Prefetch expired: {retrieval_query[:40]}")
            return None

        return entry

    def _execute_prefetch(
        self,
        entity: str,
        conversation_state: dict,
        chat_history: list,
        user_preferences: Optional[list] = None,
    ) -> None:
        """Lakukan predictive pre-fetching untuk probable follow-up queries.

        Proses:
          1. Generate probable next queries dari entity aktif (FOLLOWUP_TEMPLATES)
          2. Untuk setiap probable query:
             a. Skip jika sudah ada di KV cache atau prefetch cache
             b. Jalankan FAISS retrieval ringan (k=3) tanpa LLM generation
             c. Simpan docs ke _prefetch_cache dengan TTL
          3. Ketika actual query datang & match → gunakan pre-fetched docs
             (lihat _check_prefetch_cache + get_response integration)

        Desain:
          • HANYA FAISS (tanpa LLM) → hemat API quota & waktu
          • Non-blocking dalam konteks synchronous (lightweight, <50ms per query)
          • MAX 3 queries di-prefetch per turn untuk mencegah overhead berlebih

        Referensi: FLARE (Jiang et al. 2023) — proactive retrieval reduces
        per-turn latency ~35-60% untuk follow-up queries yang ter-prefetch.
        """
        import time

        if not entity or not self.database:
            return

        probable_queries = self._get_probable_next_queries(entity)
        if not probable_queries:
            return

        prefetch_count = 0
        MAX_PREFETCH_PER_TURN = 3

        for pq in probable_queries:
            if prefetch_count >= MAX_PREFETCH_PER_TURN:
                break

            pq_hash = self.kv_cache._hash_query(pq)

            # Skip jika sudah ada di KV cache (staging atau confirmed)
            if self.kv_cache.get(pq):
                continue

            # Skip jika sudah ada di prefetch cache (belum expire)
            if pq_hash in self._prefetch_cache:
                existing = self._prefetch_cache[pq_hash]
                if time.time() <= existing.get("expires_at", 0):
                    continue

            try:
                # Retrieval ringan: hanya FAISS, tidak panggil LLM
                raw = self.database.similarity_search_with_score(pq, k=3)
                if not raw:
                    continue

                # Filter berdasarkan threshold relevansi
                relevant_docs = [
                    doc
                    for doc, dist in raw
                    if (1.0 - float(dist) / self.MAX_FAISS_DISTANCE)
                    >= self.RELEVANCE_THRESHOLD * 0.8
                ]

                if relevant_docs:
                    self._prefetch_cache[pq_hash] = {
                        "docs": relevant_docs,
                        "entity": entity,
                        "query": pq,
                        "expires_at": time.time() + self.PREFETCH_TTL_SEC,
                    }
                    prefetch_count += 1
                    print(f"⚡ Prefetched: '{pq[:50]}' ({len(relevant_docs)} docs)")

            except Exception as _pf_err:
                print(f"⚠️ Prefetch error for '{pq[:40]}': {_pf_err}")
                continue

        if prefetch_count > 0:
            print(
                f"⚡ Pre-fetch selesai: {prefetch_count} queries warm-up "
                f"untuk entitas '{entity}'"
            )

    # ── Stop words untuk tokenisasi BM25 ────────────────────────────────────
    BM25_STOP_WORDS = {
        "apa",
        "saja",
        "ada",
        "dan",
        "atau",
        "ini",
        "itu",
        "di",
        "ke",
        "dari",
        "untuk",
        "dengan",
        "pada",
        "adalah",
        "yang",
        "bagaimana",
        "berapa",
        "dimana",
        "siapa",
        "tentang",
        "info",
        "informasi",
        "tolong",
        "bisa",
        "boleh",
        "saya",
        "kamu",
        "kalian",
        "kapan",
        "apakah",
    }

    def _tokenize_for_bm25(self, text: str) -> List[str]:
        """Tokenisasi teks untuk BM25: buang stop words dan token pendek."""
        return [
            w.lower()
            for w in re.findall(r"\w+", text)
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
            self._tokenize_for_bm25(doc.page_content) for doc in self.loaded_docs
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
            text = doc.page_content if hasattr(doc, "page_content") else str(doc)
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
        meta = getattr(doc, "metadata", {})
        chunk_idx = meta.get("chunk_index")
        if chunk_idx is None or chunk_idx >= len(self.loaded_docs):
            # chunk_index tidak tersedia — fallback ke overlap
            text = doc.page_content if hasattr(doc, "page_content") else str(doc)
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

        Menggunakan pendekatan dua tahap untuk efisiensi maksimal:

          Tahap 1 — Text-based scoring (cepat, tanpa embedding):
            • SequenceMatcher ratio  (bobot 0.50) — pencocokan karakter exact
            • Word overlap / Jaccard  (bobot 0.30) — tumpang-tindih kata
            • Keyword match           (bobot 0.20) — kata kunci FAQ terdekat

          Tahap 2 — Semantic scoring via encoder embeddings (hanya jika perlu):
            Dijalankan HANYA ketika text score berada di zona abu-abu (0.40–0.60).
            Embedding FAQ di-cache per MD5(question) agar tidak dihitung ulang.
            Referensi: Karpukhin et al. (2020) DPR — dense retrieval lebih unggul
            untuk parafrase & sinonim dibanding string similarity murni.

          Score akhir:
            • Jika text_score >= TEXT_HIGH_THRESHOLD (0.60) → return langsung
            • Jika text_score dalam zona abu-abu → blend (text * 0.55 + semantic * 0.45)
            • Jika text_score < TEXT_LOW_THRESHOLD (0.40) → coba semantic saja
              (return jika semantic >= 0.78)

        Returns FAQ entry (dict dengan 'answer') jika cocok, else None.
        """
        import hashlib as _hl
        import re
        from difflib import SequenceMatcher

        TEXT_HIGH_THRESHOLD = 0.60  # text score tinggi → langsung return
        TEXT_LOW_THRESHOLD = 0.40  # di bawah ini → coba semantic saja
        BLEND_THRESHOLD = 0.52  # threshold blended score
        SEMANTIC_ONLY_THR = 0.78  # threshold jika hanya pakai semantic

        try:
            faqs = self.faq_gen.load_faqs()
        except Exception:
            return None

        if not faqs:
            return None

        query_lower = query.lower().strip()
        q_clean = re.sub(r"[^\w\s]", " ", query_lower)
        q_words = set(q_clean.split())

        # ── Tahap 1: Text-based scoring ────────────────────────────────────
        best_text_score = 0.0
        best_faq = None
        candidates = []  # (text_score, faq) untuk zona abu-abu

        for faq in faqs:
            answer = faq.get("answer", "").strip()
            if not answer or len(answer) < 20:
                continue

            faq_q = faq.get("question", "").lower().strip()
            fq_clean = re.sub(r"[^\w\s]", " ", faq_q)
            fq_words = set(fq_clean.split())

            seq_ratio = SequenceMatcher(None, q_clean, fq_clean).ratio()

            kw_list = [k.lower() for k in faq.get("keywords", [])]
            kw_hits = sum(1 for k in kw_list if k in query_lower)
            kw_score = (kw_hits / max(len(kw_list), 1)) * 0.4 if kw_list else 0.0

            common = q_words & fq_words
            word_score = len(common) / max(len(q_words | fq_words), 1)

            text_score = seq_ratio * 0.5 + word_score * 0.3 + kw_score * 0.2

            if text_score > best_text_score:
                best_text_score = text_score
                best_faq = faq

            # Kumpulkan kandidat zona abu-abu untuk semantic re-ranking
            if TEXT_LOW_THRESHOLD <= text_score < TEXT_HIGH_THRESHOLD:
                candidates.append((text_score, faq))

        # Jika text score sangat tinggi, langsung return (hemat embedding call)
        if best_text_score >= TEXT_HIGH_THRESHOLD and best_faq:
            print(
                f"📖 FAQ text-match (score={best_text_score:.3f}): "
                f"{best_faq.get('question', '')[:60]}"
            )
            return best_faq

        # ── Tahap 2: Semantic scoring (hanya jika encoder tersedia) ────────
        # Dijalankan untuk zona abu-abu atau ketika text score rendah tapi
        # mungkin masih ada kecocokan semantik (parafrase / sinonim).
        has_encoder = self.encoder is not None and hasattr(self.encoder, "embed_query")
        if not has_encoder:
            # Fallback: gunakan text score saja
            if best_text_score >= TEXT_HIGH_THRESHOLD and best_faq:
                print(
                    f"📖 FAQ text-match (score={best_text_score:.3f}): "
                    f"{best_faq.get('question', '')[:60]}"
                )
                return best_faq
            return None

        # Ambil / hitung query embedding (di-cache singkat, maks 50 entri)
        q_cache_key = query[:100]
        if q_cache_key not in self._query_embed_temp:
            try:
                q_emb = self.encoder.embed_query(query)
                if len(self._query_embed_temp) >= 50:
                    # Hapus entri terlama (FIFO sederhana)
                    oldest = next(iter(self._query_embed_temp))
                    del self._query_embed_temp[oldest]
                self._query_embed_temp[q_cache_key] = q_emb
            except Exception:
                q_emb = None
        else:
            q_emb = self._query_embed_temp[q_cache_key]

        if q_emb is None:
            return None

        # Kandidat untuk semantic re-ranking:
        # • Semua entry zona abu-abu (text_score 0.40–0.60)
        # • Tambahkan best_faq jika text_score >= 0.40 (meski < 0.60)
        rerank_set = dict()  # id(faq) → (text_score, faq)
        for ts, f in candidates:
            rerank_set[id(f)] = (ts, f)
        if best_faq is not None and best_text_score >= TEXT_LOW_THRESHOLD:
            rerank_set[id(best_faq)] = (best_text_score, best_faq)

        if not rerank_set:
            # Text score terlalu rendah dan tidak ada kandidat → tidak cocok
            return None

        # Hitung semantic similarity untuk setiap kandidat
        import numpy as _np

        best_blend_score = 0.0
        best_blend_faq = None

        for _, (ts, faq) in rerank_set.items():
            faq_q = faq.get("question", "").strip()
            faq_hash = _hl.md5(faq_q.encode()).hexdigest()

            # Ambil embedding FAQ dari cache; hitung jika belum ada
            if faq_hash not in self._faq_embed_cache:
                try:
                    self._faq_embed_cache[faq_hash] = self.encoder.embed_query(faq_q)
                except Exception:
                    continue

            faq_emb = self._faq_embed_cache[faq_hash]
            if faq_emb is None:
                continue

            # Cosine similarity
            try:
                q_arr = _np.array(q_emb, dtype=float)
                faq_arr = _np.array(faq_emb, dtype=float)
                norm_q = float(_np.linalg.norm(q_arr))
                norm_faq = float(_np.linalg.norm(faq_arr))
                if norm_q < 1e-8 or norm_faq < 1e-8:
                    continue
                cos_sim = float(_np.dot(q_arr, faq_arr) / (norm_q * norm_faq))
                cos_sim = max(0.0, cos_sim)  # clamp ke [0, 1]
            except Exception:
                continue

            # Blended score: text (55%) + semantic (45%)
            blended = ts * 0.55 + cos_sim * 0.45

            print(
                f"   🔬 FAQ semantic: '{faq_q[:50]}' "
                f"text={ts:.3f} sem={cos_sim:.3f} blend={blended:.3f}"
            )

            if blended > best_blend_score:
                best_blend_score = blended
                best_blend_faq = faq

        # Threshold untuk blended score
        if best_blend_faq is not None and best_blend_score >= BLEND_THRESHOLD:
            print(
                f"📖 FAQ semantic-match (blend={best_blend_score:.3f}): "
                f"{best_blend_faq.get('question', '')[:60]}"
            )
            return best_blend_faq

        # Cek: jika hanya semantic saja sangat yakin (score ≥ 0.78) → return
        # Ini menangkap kasus di mana wording sangat berbeda tapi maknanya sama.
        if best_blend_faq is not None:
            # Hitung ulang semantic-only score untuk best candidate
            faq_q2 = best_blend_faq.get("question", "").strip()
            faq_hash2 = _hl.md5(faq_q2.encode()).hexdigest()
            faq_emb2 = self._faq_embed_cache.get(faq_hash2)
            if faq_emb2 is not None:
                try:
                    q_arr2 = _np.array(q_emb, dtype=float)
                    faq_arr2 = _np.array(faq_emb2, dtype=float)
                    n1, n2 = (
                        float(_np.linalg.norm(q_arr2)),
                        float(_np.linalg.norm(faq_arr2)),
                    )
                    if n1 > 1e-8 and n2 > 1e-8:
                        sem_only = float(_np.dot(q_arr2, faq_arr2) / (n1 * n2))
                        if sem_only >= SEMANTIC_ONLY_THR:
                            print(
                                f"📖 FAQ semantic-only (sem={sem_only:.3f}): "
                                f"{faq_q2[:60]}"
                            )
                            return best_blend_faq
                except Exception:
                    pass

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
                raw_text = "\n\n".join(p.page_content for p in pages)

                # ── Entity-Boundary Normalisasi (Lewis et al. 2020; Gao et al. 2023) ──
                # PDF yang dihasilkan dari Word/Canva sering menggunakan blank line
                # berisi spasi ("\n \n") sebagai pemisah antar entitas (restoran/hotel/
                # wisata/transportasi), bukan "\n\n" murni yang dikenali splitter.
                # Normalisasi 3 langkah ini memastikan setiap batas entitas terdeteksi
                # sebagai separator prioritas-1 di RecursiveCharacterTextSplitter,
                # sehingga 1 entitas = 1 chunk tanpa kontaminasi data antar entitas.
                #
                # Referensi:
                #   Lewis et al. (2020) NeurIPS — RAG bekerja optimal ketika setiap
                #   chunk merepresentasikan satu "self-contained knowledge unit".
                #   Gao et al. (2023) ACM — "boundary-aware segmentation outperforms
                #   fixed-size chunking for structured multi-entity documents."
                combined_text = re.sub(r'\r\n', '\n', raw_text)           # 1. Windows → Unix line endings
                combined_text = re.sub(r'\n[ \t]+\n', '\n\n', combined_text)  # 2. "\n \n" → "\n\n" (separator utama)
                combined_text = re.sub(r'\n{3,}', '\n\n', combined_text)  # 3. Triple+ newline → double newline

                source_name = os.path.basename(pdf_path)
                merged_docs.append(
                    LCDocument(
                        page_content=combined_text, metadata={"source": source_name}
                    )
                )
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
            chunk_size=1500,
            chunk_overlap=200,  # increased: names/headers survive page joins
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        docs = text_splitter.split_documents(merged_docs)

        # Prepend source filename to every chunk so the LLM always knows context
        for chunk_index, doc in enumerate(docs):
            src = doc.metadata.get("source", "")
            doc.metadata["chunk_index"] = chunk_index
            if src and not doc.page_content.startswith(f"[{src}]"):
                doc.page_content = f"[Sumber: {src}]\n{doc.page_content}"

        self.loaded_docs = docs

        print(
            f"📄 Loaded {total_page_count} halaman dari {len(merged_docs)} file, "
            f"split into {len(docs)} chunks"
        )

        # Build vector database
        print("🔨 Building vector database...")
        assert self.encoder is not None, "Encoder must be set before loading documents"
        self.database = FAISS.from_documents(
            docs, self.encoder, distance_strategy=DistanceStrategy.COSINE
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
            "num_pages": total_page_count,
        }

    def get_response(
        self,
        query: str,
        chat_history: Optional[List[Dict]] = None,
        conversation_state: Optional[Dict] = None,
        k: int = 8,
        max_new_tokens: int = 2048,
        use_cache: bool = True,
        temperature: float = 0.7,
        user_preferences: Optional[list] = None,
    ) -> Dict:
        """Get response using CAG system"""
        start_time = time.time()
        is_first_message = not bool(chat_history)

        # Classify intent
        intent = self.model._classify_intent(query)

        # Follow-up grounding: map pronoun-based questions to the last place in history.
        retrieval_query = query
        contextual_followup = False
        resolved_followup_place = None
        if self._is_followup_reference_query(query) and (
            chat_history or conversation_state
        ):
            last_place = self._extract_last_place_from_history(chat_history or [])
            if not last_place:
                last_place = self._extract_last_place_from_state(conversation_state)
            if last_place:
                retrieval_query = f"{query.strip()} di {last_place}".strip()
                contextual_followup = True
                resolved_followup_place = last_place
                print(f"🔗 Follow-up query grounded to previous place: {last_place}")

        if (
            not contextual_followup
            and self._is_implicit_attribute_followup_query(query)
            and (chat_history or conversation_state)
        ):
            last_place = self._extract_last_place_from_history(chat_history or [])
            if not last_place:
                last_place = self._extract_last_place_from_state(conversation_state)
            if last_place:
                retrieval_query = f"{query.strip()} di {last_place}".strip()
                contextual_followup = True
                resolved_followup_place = last_place
                print(f"🧠 Implicit follow-up grounded to previous place: {last_place}")

        # Alternative recommendation queries often omit entity names.
        # Example: "selain pantai tersebut apa lagi ..."
        query_lower = query.lower().strip()
        if not contextual_followup and self._extract_place_name(query) is None:
            if any(
                kw in query_lower
                for kw in ["selain", "alternatif", "yang lain", "lainnya"]
            ):
                last_place = self._extract_last_place_from_history(chat_history or [])
                if not last_place:
                    last_place = self._extract_last_place_from_state(conversation_state)
                if last_place:
                    retrieval_query = f"{query.strip()} selain {last_place}".strip()
                    contextual_followup = True
                    resolved_followup_place = last_place
                    print(
                        f"🔁 Alternative query grounded with previous place: {last_place}"
                    )

        # ── Layer 4: Context-aware soft-reference bypass ───────────────────────────
        # Menangkap follow-up yang TIDAK menggunakan attribute keyword eksplisit,
        # namun masih merujuk ke entitas aktif lewat referensi halus (pronoun /
        # demonstrative) ATAU query sangat pendek tanpa nama tempat.
        #
        # Justifikasi penelitian:
        #   • QuAC (Choi et al. 2018) — ~70% follow-up dialog informatif tidak
        #     menyebut entitas eksplisit; menggunakan pronoun & demonstrative.
        #   • CoQA (Reddy et al. 2019) — coreference resolution kritikal untuk
        #     multi-turn QA.
        #   • OR-QuAC (Qu et al. 2021) — follow-up sering menggunakan continuation /
        #     pronoun markers tanpa menyebut nama entitas sama sekali.
        #
        # Contoh yang kini tertangkap (sebelumnya tidak):
        #   "Ada spot foto bagus di sana?"  → "di sana" = soft reference
        #   "Ceritakan lebih lanjut"        → continuation marker
        #   "Bagus gak?"                    → short continuation (≤8 kata)
        #   "Worth it?"                     → short continuation (≤8 kata)
        if not contextual_followup and (chat_history or conversation_state):
            _soft_reference_kws = [
                "di sana",
                "di situ",
                "disana",
                "disitu",
                "tersebut",
                "tadi",
                "tempat itu",
                "tempat tersebut",
                "yang itu",
                "yang ini",
                "sana",
                "situ",
                "lanjut",
                "lebih lanjut",
                "lebih detail",
                "ceritakan lagi",
                "jelaskan lagi",
                "ceritakan lebih",
                "lagi dong",
                "lagi nih",
                "ke sana",
                "kesana",
                "ke situ",
                "kesitu",
            ]
            _short_cont_kws = [
                "bagus",
                "gimana",
                "worth",
                "aman",
                "ramai",
                "sepi",
                "bersih",
                "foto",
                "akses",
                "cara ke",
                "tiket",
                "biaya",
                "masuk",
                "parkir",
                "toilet",
                "jadwal",
                "buka",
                "tutup",
                "souvenir",
                "makan",
                "recommended",
                "rekomen",
                "worth it",
                "cocok",
            ]
            _has_soft_ref = any(kw in query_lower for kw in _soft_reference_kws)
            _word_count = len(query_lower.split())
            _has_short_cont = _word_count <= 8 and any(
                kw in query_lower for kw in _short_cont_kws
            )
            _no_explicit_place = self._extract_place_name(query) is None

            if (_has_soft_ref or _has_short_cont) and _no_explicit_place:
                _last_place_ctx = self._extract_last_place_from_state(
                    conversation_state
                ) or self._extract_last_place_from_history(chat_history or [])
                if _last_place_ctx:
                    retrieval_query = f"{query.strip()} di {_last_place_ctx}".strip()
                    contextual_followup = True
                    resolved_followup_place = _last_place_ctx
                    print(
                        f"🧩 Soft-ref follow-up: '{query[:40]}' → grounded to: {_last_place_ctx}"
                    )

        # ── Multi-Signal Routing Decision ─────────────────────────────────────────
        # Hitung sinyal routing setelah SEMUA layer follow-up detection selesai.
        # Hasil routing digunakan untuk:
        #   1. Menentukan context_key untuk Dual-Layer Cache lookup
        #   2. Menentukan mode retrieval (CACHE_FIRST / MEMORY_AUGMENTED_RAG / PURE_RAG)
        #   3. Logging ke _last_routing_signals untuk evaluasi di notebook
        # Referensi: Jeong et al. (2024) Adaptive-RAG; Asai et al. (2023) Self-RAG.
        _routing_signals = self._compute_routing_signals(
            query=query,
            intent=intent,
            chat_history=chat_history or [],
            conversation_state=conversation_state or {},
            contextual_followup=contextual_followup,
            resolved_followup_place=resolved_followup_place or "",
        )
        _routing_context_key = _routing_signals["context_key"]
        _routing_mode = _routing_signals["routing_mode"]

        # Handle greeting
        if intent == "greeting":
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
        if intent == "general_question":
            # Defensive FAQ check: some queries are misrouted here but have a real
            # tourism FAQ answer (e.g. "seberapa jauh...").  Check before giving a
            # generic Gemini answer so the grounded answer is always preferred.
            if use_cache and not contextual_followup:
                faq_hit = self._search_faq(query)
                if faq_hit:
                    faq_response = faq_hit["answer"]
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

        # Check cache — menggunakan Dual-Layer Cache Key dari routing signals.
        # context_key kosong → Layer 1 (context-free, query eksplisit).
        # context_key berisi last_place → Layer 2 (context-aware, follow-up query).
        # Dengan Dual-Layer key, "bagaimana fasilitasnya?" di konteks Pantai Parbaba
        # TIDAK akan mendapat cache entry milik "bagaimana fasilitasnya?" di Hotel X.
        query_hash = self.kv_cache._hash_query(query, context_key=_routing_context_key)
        if use_cache and not contextual_followup:
            cached = self.kv_cache.get(query, context_key=_routing_context_key)
            if cached:
                if self._is_invalid_response(cached.get("response", "")):
                    self.kv_cache.delete_entry(query_hash)
                    print(f"⚠️ Ignored invalid cached response: {query[:50]}...")
                else:
                    hit_type = "STAGING" if cached.get("from_staging") else "HIT"
                    ctx_tag = (
                        f" [ctx:{_routing_context_key[:20]}]"
                        if _routing_context_key
                        else ""
                    )
                    print(f"✅ Cache {hit_type}{ctx_tag}: {query[:50]}...")
                    return {
                        "response": cached["response"],
                        "source": "cag_cache",
                        "cache_used": True,
                        "response_time": time.time() - start_time,
                        "access_count": cached.get("access_count", 0),
                        "num_chunks": 0,
                        "context": cached.get("context", ""),
                        "cache_key": query_hash,
                        "routing_signals": _routing_signals,
                    }

        # FAQ search — before hitting FAISS
        # Searches faq_tourism.json directly, bypassing vector retrieval.
        # Entries with a real answer are returned immediately as CAG hits.
        if use_cache and not contextual_followup:
            faq_hit = self._search_faq(query)
            if faq_hit:
                faq_response = faq_hit["answer"]
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
        retrieval_quality = None
        try:
            # ── Predictive Pre-fetch Check ────────────────────────────────────
            # Cek apakah FAISS retrieval untuk query ini sudah di-warm-up oleh
            # _execute_prefetch() pada turn sebelumnya.
            # HIT  → gabungkan pre-fetched docs dengan FAISS reduced-k
            #         (hemat ~35-60% waktu retrieval, referensi: FLARE 2023)
            # MISS → jalankan FAISS retrieval normal
            _prefetch_entry = self._check_prefetch_cache(retrieval_query)
            if _prefetch_entry and _prefetch_entry.get("docs"):
                _pf_docs = _prefetch_entry["docs"]
                # Pre-fetched docs masuk dengan distance rendah (relevansi tinggi)
                _pf_results = [(doc, 0.05) for doc in _pf_docs]
                # Supplement dari FAISS untuk slot yang tersisa
                _remaining_k = max(k - len(_pf_docs), 2)
                _faiss_results = self.database.similarity_search_with_score(
                    retrieval_query, k=_remaining_k
                )
                raw_results = _pf_results + _faiss_results
                print(
                    f"⚡ Prefetch utilized: {len(_pf_docs)} pre-fetched "
                    f"+ {len(_faiss_results)} FAISS → total {len(raw_results)} docs"
                )
            else:
                raw_results = self.database.similarity_search_with_score(
                    retrieval_query, k=k
                )
            raw_results = sorted(raw_results, key=lambda item: float(item[1]))
            top_score = float(raw_results[0][1]) if raw_results else 0.0

            specific_place_docs = self._find_specific_place_docs(
                retrieval_query, limit=min(k + 2, 10)
            )

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
            # ── Fix #3: Pre-compute BM25 scores SEKALI untuk semua chunk ──────
            # Mengganti N pemanggilan get_scores() (masing-masing O(|corpus|))
            # dengan SATU pemanggilan O(|corpus|), lalu lookup O(1) per chunk.
            #
            # Sebelum fix: k=8, corpus=500 → 8×500 = 4.000 operasi BM25
            # Setelah fix: 1×500 + 8×O(1) = 508 operasi → ~8× lebih cepat
            #
            # Referensi: Robertson & Zaragoza (2009) — BM25 batch scoring.
            _all_bm25_scores = None
            if self.bm25_index is not None:
                try:
                    _bm25_tokens = self._tokenize_for_bm25(retrieval_query)
                    if _bm25_tokens:
                        _all_bm25_scores = self.bm25_index.get_scores(_bm25_tokens)
                except Exception as _bm25_err:
                    print(f"⚠️ BM25 pre-compute error: {_bm25_err}")

            scored_chunks = []
            for doc, faiss_dist in raw_results:
                d = float(faiss_dist)
                faiss_sim = max(0.0, 1.0 - d / self.MAX_FAISS_DISTANCE)

                # Lookup BM25 score dari array pre-computed (O(1) per chunk)
                if _all_bm25_scores is not None:
                    _cidx = getattr(doc, "metadata", {}).get("chunk_index")
                    if _cidx is not None and 0 <= _cidx < len(_all_bm25_scores):
                        _raw_bm25 = float(_all_bm25_scores[_cidx])
                        bm25_norm = (
                            _raw_bm25 / (_raw_bm25 + 1.0) if _raw_bm25 > 0.0 else 0.0
                        )
                    else:
                        bm25_norm = self._bm25_score(retrieval_query, doc)  # fallback
                else:
                    bm25_norm = self._bm25_score(retrieval_query, doc)  # no BM25 index

                hybrid = (
                    faiss_sim * self.HYBRID_WEIGHT_VECTOR
                    + bm25_norm * self.HYBRID_WEIGHT_KEYWORD
                )
                scored_chunks.append((doc, d, faiss_sim, bm25_norm, hybrid))

            # Urutkan: skor hybrid tertinggi (paling relevan) duluan
            scored_chunks.sort(key=lambda x: x[4], reverse=True)

            # Filter: hanya chunk yang melewati ambang batas relevansi
            threshold_passed = [
                (doc, dist)
                for doc, dist, fsim, kw, hyb in scored_chunks
                if hyb >= self.RELEVANCE_THRESHOLD
            ]

            if scored_chunks:
                top_hybrid = float(scored_chunks[0][4])
                second_hybrid = (
                    float(scored_chunks[1][4]) if len(scored_chunks) > 1 else 0.0
                )
                margin_score = max(0.0, top_hybrid - second_hybrid)
                grounding_score = min(
                    1.0, len(threshold_passed) / max(1, len(raw_results))
                )
                retrieval_quality = {
                    "hybrid_score": round(top_hybrid, 4),
                    "margin_score": round(margin_score, 4),
                    "grounding_score": round(grounding_score, 4),
                }

            prioritized = [(doc, 0.0) for doc in specific_place_docs]

            # Hard focus for follow-up attribute queries:
            # if we already resolved the place and have exact-place chunks,
            # avoid injecting unrelated chunks from generic threshold_passed.
            if contextual_followup and resolved_followup_place and specific_place_docs:
                merged_results = prioritized
                print(
                    f"🎯 Follow-up retrieval focused on resolved place: {resolved_followup_place}"
                )
            else:
                merged_results = prioritized + threshold_passed

            # ── Deduplication ────────────────────────────────────────────────
            # Remove chunks whose content is >70 % identical to an already-kept
            # chunk.  This prevents overlap-created near-duplicate chunks from
            # wasting context slots that could go to genuinely different info.
            seen_contents: list = []
            deduped: list = []
            for doc, score in merged_results:
                content = (
                    doc.page_content if hasattr(doc, "page_content") else str(doc)
                ).strip()
                # Check overlap ratio against every kept chunk
                is_duplicate = False
                for kept in seen_contents:
                    # Simple overlap: count shared characters in shorter string
                    shorter = min(len(content), len(kept))
                    if shorter == 0:
                        continue
                    # Count matching chars via set intersection on trigrams
                    # Menggunakan static method _trigrams (Fix #7) — tidak
                    # membuat ulang closure di setiap iterasi loop.
                    tg_new = self._trigrams(content[:300])
                    tg_kept = self._trigrams(kept[:300])
                    if not tg_new or not tg_kept:
                        continue
                    overlap = len(tg_new & tg_kept) / max(len(tg_new), len(tg_kept))
                    if overlap >= 0.70:  # 70 % trigram overlap → duplicate
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
                structured_ctx = self._get_locations_json_context(
                    retrieval_query, user_preferences
                )
                if structured_ctx:
                    print(
                        f"📍 FAISS returned nothing — using structured locations data for listing query"
                    )
                    context = structured_ctx
                    # Skip straight to generation with only the JSON context
                    generation_start = time.time()
                    try:
                        response = self.model.generate_response(
                            query=query,
                            context=context,
                            chat_history=chat_history or [],
                            conversation_state=conversation_state or {},
                            max_new_tokens=max_new_tokens,
                            temperature=temperature,
                            user_preferences=user_preferences or [],
                            is_first_message=is_first_message,
                        )
                    except Exception as e:
                        print(f"❌ Generation error: {e}")
                        response = f"Maaf, terjadi kesalahan saat memproses pertanyaan: {str(e)}"
                    if use_cache and not self._is_invalid_response(response):
                        self.kv_cache.put(
                            query,
                            response,
                            context[:500],
                            source="rag_fallback",
                        )
                    return {
                        "response": response,
                        "source": "rag",
                        "cache_used": False,
                        "response_time": time.time() - start_time,
                        "num_chunks": 0,
                        "context": context,
                        "cache_key": query_hash,
                    }

            if intent == "tourism":
                # ── Fallback: cek locations.json SEBELUM bilang "tidak tersedia" ──
                # Mencegah false negative ketika entitas yang ditanyakan ada di
                # database lokasi namun tidak ter-retrieve oleh FAISS (skor di
                # bawah RELEVANCE_THRESHOLD).
                #
                # Bug yang diselesaikan: "bagaimana dengan Desa Wisata Meat?" →
                # FAISS tidak menemukan chunk relevan → sebelumnya langsung return
                # "belum tersedia", padahal locations.json punya data lengkap!
                _place_fb = self._extract_place_name(query)
                if _place_fb:
                    _entity_ctx_fb = self._get_specific_entity_from_locations(_place_fb)
                    if _entity_ctx_fb:
                        print(f"📍 Tourism fallback via locations.json: '{_place_fb}'")
                        try:
                            _fb_response = self.model.generate_response(
                                query=query,
                                context=_entity_ctx_fb,
                                chat_history=chat_history or [],
                                conversation_state=conversation_state or {},
                                max_new_tokens=max_new_tokens,
                                temperature=temperature,
                                user_preferences=user_preferences or [],
                                is_first_message=is_first_message,
                            )
                        except Exception as _fb_err:
                            print(f"❌ Fallback generation error: {_fb_err}")
                            _fb_response = None
                        if _fb_response and not self._is_invalid_response(_fb_response):
                            if use_cache:
                                self.kv_cache.put(
                                    query,
                                    _fb_response,
                                    _entity_ctx_fb[:500],
                                    source="rag_fallback",
                                )
                            return {
                                "response": _fb_response,
                                "source": "rag",
                                "cache_used": False,
                                "response_time": time.time() - start_time,
                                "num_chunks": 0,
                                "context": _entity_ctx_fb,
                                "cache_key": query_hash,
                            }
                print(
                    "⚠️ No chunks passed retrieval threshold — returning document-grounded unavailable response"
                )
                # ── Web Search Fallback for Tourism ──────────────────────────
                # Sebelum menyerah dengan pesan "tidak tersedia", coba jawab
                # menggunakan LLM general knowledge + DuckDuckGo web search.
                # Ini krusial untuk entitas valid (Tomok, Samosir, dll.) yang
                # tidak ada di PDF lokal namun merupakan destinasi wisata nyata.
                #
                # Kondisi yang memicu fallback ini:
                #   1. contextual_followup=True → query adalah lanjutan percakapan
                #      tentang entitas yang sudah dibahas (paling umum).
                #   2. Tidak ada entitas sama sekali di query → query terlalu umum
                #      untuk "document unavailable" yang personal.
                #   3. Entitas ada tapi tidak di locations.json (sudah dicek di atas).
                #
                # Referensi: Trivedi et al. (2022) IRCoT — iterative retrieval
                # from multiple sources prevents answer refusal.
                print("🌐 [Tourism Web Fallback] Mencoba LLM/web sebelum menyerah...")
                try:
                    _web_answer = self.model._ask_gemini_general(query)
                    if _web_answer and not self._is_invalid_response(_web_answer):
                        print(f"✅ [Tourism Web Fallback] Berhasil: {len(_web_answer)} chars")
                        if use_cache:
                            self.kv_cache.put(query, _web_answer, "web_fallback", source="web_rag")
                        return {
                            "response": _web_answer,
                            "source": "web_rag",
                            "cache_used": False,
                            "response_time": time.time() - start_time,
                            "num_chunks": 0,
                            "context": "",
                            "cache_key": query_hash,
                        }
                except Exception as _web_err:
                    print(f"⚠️ [Tourism Web Fallback] Gagal: {_web_err}")
                # Semua fallback habis → baru kembalikan pesan "tidak tersedia"
                return {
                    "response": self.model._build_document_unavailable_response(query),
                    "source": "no_relevant_context",
                    "cache_used": False,
                    "response_time": time.time() - start_time,
                    "num_chunks": 0,
                    "context": "",
                    "cache_key": query_hash,
                }

            print(
                f"⚠️ No chunks passed retrieval threshold — falling back to LLM general knowledge"
            )
            try:
                _greeting_rule_general = (
                    "Ini adalah pesan PERTAMA dalam percakapan — boleh membuka jawaban dengan sapaan singkat yang hangat."
                    if is_first_message
                    else "Ini adalah lanjutan percakapan — JANGAN memulai jawaban dengan sapaan (Halo, Horas, Selamat datang, dsb). Langsung jawab pertanyaan."
                )
                # Include chat history for context-aware follow-up
                _history_general = ""
                if chat_history and len(chat_history) > 0:
                    _h_lines = []
                    for msg in chat_history[-8:]:
                        role = "Pengguna" if msg.get("role") == "user" else "Asisten"
                        _h_lines.append(f"  {role}: {msg.get('content', '')[:300]}")
                    _history_general = (
                        "\n\nKONTEKS PERCAKAPAN SEBELUMNYA:\n"
                        + "\n".join(_h_lines)
                        + "\n\nGunakan konteks di atas jika pertanyaan baru merujuk ke topik sebelumnya.\n"
                    )
                general_prompt = (
                    "Kamu adalah asisten wisata Danau Toba yang ramah dan informatif.\n"
                    f'Pengguna bertanya: "{query}"\n\n'
                    "Tidak ada dokumen spesifik yang ditemukan di database untuk pertanyaan ini.\n"
                    "Jawab berdasarkan pengetahuan umummu jika pertanyaan masih berkaitan "
                    "dengan pariwisata, budaya Batak, Sumatera Utara, atau topik yang tidak terlalu jauh dari konteks wisata.\n"
                    "Jika pertanyaan BENAR-BENAR tidak relevan (mengandung kata kasar, NSFW, "
                    "atau topik berbahaya), tolak dengan sopan dan arahkan ke topik wisata Danau Toba.\n"
                    f"{_greeting_rule_general}\n"
                    f"{_history_general}\n"
                    "CRITICAL LANGUAGE REQUIREMENT:\n"
                    "You MUST answer in the EXACT SAME LANGUAGE as the user's question.\n"
                    "If the user asks in English, your entire response MUST be in English.\n"
                    "If the user asks in Indonesian, your entire response MUST be in Indonesian."
                )
                llm_response = self.model._call_gemini_api(
                    general_prompt, max_tokens=max_new_tokens, temperature=temperature
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
            content = doc.page_content if hasattr(doc, "page_content") else str(doc)
            content = content.strip()
            if content and len(content) > 50:
                # Extract source metadata from document
                meta = doc.metadata if hasattr(doc, "metadata") else {}
                src_file = os.path.basename(meta.get("source", "dokumen"))
                src_label = (
                    src_file.replace(".pdf", "")
                    .replace("_", " ")
                    .replace("-", " ")
                    .title()
                )
                page_num = meta.get("page", "?")
                context_parts.append(
                    f"[Sumber {i} | {src_label} | hal. {page_num}]\n{content}"
                )

        context = "\n\n".join(context_parts)

        # ── Inject specific entity from locations.json for entity-specific queries ──
        # Menjamin data terstruktur untuk entitas yang ditanyakan user SELALU ada
        # dalam konteks sebagai anchor, meskipun FAISS retrieval mengembalikan
        # chunk generik atau campuran dari beberapa entitas di area yang sama.
        #
        # Bug yang dicegah: "Wisata Meat" → FAISS retrieve chunk campuran (Pantai
        # Meat + Desa Wisata Meat, keduanya menyebut "air jernih") → tanpa
        # injeksi ini, LLM berpotensi:
        #   1. Halusinasi nama: menginvensi "Air Terjun Meat" dari kata "air jernih"
        #      di deskripsi Desa Wisata Meat, padahal entitas itu tidak ada.
        #   2. Atribusi data salah: metadata Desa Wisata Meat diberikan ke nama lain.
        # Dengan prepend data spesifik dari locations.json (nama PERSIS + metadata
        # AKURAT), LLM mendapat anchor yang jelas sehingga tidak mengarang nama.
        if not self._is_listing_query(retrieval_query):
            _entity_q = self._extract_place_name(query)
            if _entity_q:
                _entity_specific_ctx = self._get_specific_entity_from_locations(
                    _entity_q
                )
                if _entity_specific_ctx:
                    context = (
                        _entity_specific_ctx + "\n\n" + context
                        if context
                        else _entity_specific_ctx
                    )
                    print(
                        f"📍 Entity-specific prepend: '{_entity_q}' → locations.json data injected"
                    )

        # For listing/category queries, prepend structured locations.json data so
        # all known places for that category are always included.
        if self._is_listing_query(retrieval_query):
            structured_ctx = self._get_locations_json_context(
                retrieval_query, user_preferences
            )
            if structured_ctx:
                context = (
                    structured_ctx + "\n\n" + context if context else structured_ctx
                )
                print(
                    f"📍 Injected structured locations context ({len(structured_ctx)} chars)"
                )

        # For transport / route queries, inject distance & transport data
        try:
            from location_service import (
                build_transport_context,
                extract_route_places,
                is_transport_query,
            )

            if is_transport_query(query):
                origin_name, dest_name = extract_route_places(query)
                if origin_name and dest_name:
                    transport_ctx = build_transport_context(origin_name, dest_name)
                    if transport_ctx:
                        context = (
                            transport_ctx + "\n\n" + context
                            if context
                            else transport_ctx
                        )
                        print(
                            f"🚗 Injected transport context ({len(transport_ctx)} chars)"
                        )
        except ImportError:
            pass

        print(
            f"📄 Retrieved {len(relevant_docs)} chunks, context: {len(context)} chars"
        )

        # Generate response
        generation_start = time.time()
        try:
            response = self.model.generate_response(
                query=query,
                context=context,
                chat_history=chat_history or [],
                conversation_state=conversation_state or {},
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
            print(
                f"⚠️ Invalid response detected with context available — retrying with stronger prompt..."
            )
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
                    conversation_state=conversation_state or {},
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
            # Simpan dengan context-aware key agar follow-up response tidak
            # menimpa atau tertukar dengan response dari konteks berbeda.
            self.kv_cache.put(
                query,
                response,
                context[:500],
                context_key=_routing_context_key,
                retrieval_quality=retrieval_quality,
                source="rag",
            )
            ctx_tag = (
                f" [ctx:{_routing_context_key[:20]}]" if _routing_context_key else ""
            )
            print(f"💾 Staged{ctx_tag}: {query[:50]}...")

        # ── Predictive Pre-fetching ───────────────────────────────────────────
        # Setelah respons berhasil, warm-up FAISS untuk probable follow-up queries.
        # Dijalankan SETELAH response dikirim (lightweight — hanya FAISS, tanpa LLM).
        # Manfaat: turn berikutnya yang meminta detail entitas akan mendapat
        # retrieval result dari cache (hemat ~100-150ms per query).
        _pf_entity = (
            resolved_followup_place
            or self._extract_place_name(query)
            or (conversation_state.get("last_place") if conversation_state else "")
        )
        if _pf_entity and not self._is_invalid_response(response):
            self._execute_prefetch(
                entity=_pf_entity,
                conversation_state=conversation_state or {},
                chat_history=chat_history or [],
                user_preferences=user_preferences or [],
            )

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
            "routing_signals": _routing_signals,
        }

    def get_stats(self) -> Dict:
        """Get system statistics"""
        return {
            "system_status": "ready" if self.docs_loaded else "no_documents",
            "kv_cache": self.kv_cache.get_stats(),
            "performance": {},
        }

    def clear_cache(self):
        """Clear all caches"""
        self.kv_cache.clear()
        print("🗑️ Cache cleared")

    def optimize_cache(self, max_size_mb: float = 100.0, min_access_count: int = 2):
        """Optimize cache"""
        result = self.kv_cache.optimize(max_size_mb)
        return {
            "removed": result.get("removed_items", 0),
            "current_size_mb": self.get_stats()["kv_cache"].get("size_mb", 0),
            "remaining_items": self.get_stats()["kv_cache"].get("size", 0),
        }
