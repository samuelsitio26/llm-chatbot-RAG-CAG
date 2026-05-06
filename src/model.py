"""
Gemini Model Wrapper for CAG System
Uses google-genai SDK (Vertex AI) — billed to Google Cloud, bukan AI Studio.
Gemini 2.5 Flash Preview — endpoint 'us-central1' & google-genai >= 1.56.0
"""

import os
import re
import time as time_module

from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types


class GeminiChatModel:
    """
    Wrapper untuk Google Gemini via google-genai SDK (Vertex AI backend).
    Autentikasi via GOOGLE_APPLICATION_CREDENTIALS (Service Account JSON)
    atau Application Default Credentials (ADC).
    Billing masuk ke Google Cloud Console, bukan AI Studio.

    CATATAN: gemini-2.5-flash tersedia di endpoint 'us-central1'.
    Model lain (2.0/1.5) sebagai fallback di region yang sama.
    """

    # ── Capability config per model ──────────────────────────────────
    # 'location' : endpoint yang digunakan ('global' atau 'us-central1')
    # 'thinking' : apakah thinking_level bisa dikonfigurasi
    MODEL_CONFIG = {
        "gemini-3-flash-preview": {
            "max_output_tokens": 8192,
            "location": "global",
            "thinking": True,   # supports thinking_level
        },
        "gemini-2.5-flash": {
            "max_output_tokens": 4096,
            "location": "us-central1",
            "thinking": False,
        },
        "gemini-2.5-pro-preview-05-06": {
            "max_output_tokens": 8192,
            "location": "us-central1",
            "thinking": False,
        },
        "gemini-2.0-flash": {
            "max_output_tokens": 2048,
            "location": "us-central1",
            "thinking": False,
        },
        "gemini-1.5-flash": {
            "max_output_tokens": 2048,
            "location": "us-central1",
            "thinking": False,
        },
    }

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name

        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "chatbot-toba")
        self.default_location = os.getenv("VERTEX_LOCATION", "us-central1")

        # Buat client untuk tiap location yang mungkin dipakai
        # (google-genai client dibuat per-request agar location fleksibel)
        self._clients: dict = {}  # cache: location -> genai.Client

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 2  # detik antar request

        print(f"Initializing google-genai (Vertex AI): {model_name}")
        print(f"Project: {self.project_id} | Default location: {self.default_location}")
        print(f"Auth: GOOGLE_APPLICATION_CREDENTIALS atau ADC")
        print(f"Context-based fallback: ENABLED")

    def _get_client(self, location: str) -> genai.Client:
        """Kembalikan (atau buat) genai.Client untuk location tertentu."""
        if location not in self._clients:
            self._clients[location] = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=location,
            )
        return self._clients[location]

    def _classify_intent(self, query: str) -> str:
        """Classify user intent: greeting, tourism, general, or out_of_scope"""
        query_lower = query.lower().strip()

        greeting_words = [
            "halo",
            "hai",
            "hello",
            "hi",
            "hey",
            "hei",
            "horas",
            "selamat",
        ]
        greeting_phrases = [
            "selamat pagi",
            "selamat siang",
            "selamat sore",
            "selamat malam",
            "apa kabar",
        ]

        # Check greeting FIRST (before out_of_scope)
        words = query_lower.split()
        if len(words) <= 3:
            if any(word in greeting_words for word in words):
                return "greeting"
            for phrase in greeting_phrases:
                if query_lower.startswith(phrase):
                    return "greeting"

        # Detect pure math questions (e.g. "2 + 2", "5 x 3")
        import re

        if re.search(r"\d+\s*[\+\-\*\/x]\s*\d+", query_lower):
            return "general_question"

        # Document-style business/place questions should stay grounded in tourism docs.
        # NOTE: "seberapa" is intentionally handled in strong keywords — "bintang berapa",
        # "harga berapa", "seberapa jauh" etc. are tourism/FAQ questions.
        if re.search(
            r"\b(menu|alamat|harga|jam\s+operasional|jam\s+buka|jam\s+tutup|ulasan|review|fasilitas|bintang)\b",
            query_lower,
        ):
            return "tourism"

        # Strong tourism keywords that definitely indicate Toba tourism query
        strong_tourism_keywords = [
            "wisata",
            "pantai",
            "danau",
            "hotel",
            "penginapan",
            "homestay",
            "villa",
            "resort",
            "toba",
            "samosir",
            "balige",
            "parapat",
            "tomok",
            "tuktuk",
            "sipiso",
            "kuliner",
            "batak",
            "ulos",
            "air terjun",
            "menu",
            "warung",
            "rumah makan",
            "restoran",
            "restaurant",
            "kedai",
            "rute",
            "jarak",
            "jauh",
            "seberapa",
            "transportasi",
            "kendaraan",
            "akomodasi",
            "naik apa",
            "cara ke",
            "menuju",
        ]

        # Check strong tourism keywords first (takes highest priority)
        for kw in strong_tourism_keywords:
            if kw in query_lower:
                return "tourism"

        # Weak tourism keywords
        weak_tourism_keywords = [
            "rekomendasi",
            "destinasi",
            "liburan",
            "trip",
            "travel",
            "budget",
            "harga",
            "murah",
            "mahal",
            "honeymoon",
            "keluarga",
            "makanan",
            "cafe",
            "resto",
            "museum",
            "budaya",
            "adat",
            "sumut",
            "sumatera",
            "medan",
            "siantar",
            "karo",
            "dairi",
            "tempat",
            "makan",
            "menginap",
            "jalan-jalan",
            "view",
            "pemandangan",
            "gunung",
            "kulineran",
            "tiket",
            "biaya",
        ]

        for kw in weak_tourism_keywords:
            if kw in query_lower:
                return "tourism"

        # General questions - answer then redirect to tourism
        general_patterns = [
            "siapa",
            "apa itu",
            "kapan",
            "dimana",
            "mengapa",
            "bagaimana",
            "terima kasih",
            "makasih",
            "thanks",
        ]
        for pattern in general_patterns:
            if pattern in query_lower:
                return "general_question"

        # Default: treat as general question
        return "general_question"

    def _rewrite_query(
        self,
        query: str,
        chat_history: list = None,
        conversation_state: dict = None,
    ) -> str:
        """
        Query Rewriting berbasis LLM — memperjelas query ambigu atau follow-up
        sebelum masuk ke intent classifier dan retrieval pipeline.

        Teknik ini mengatasi keterbatasan keyword-based intent detection ketika
        pengguna mengirimkan query:
          - Singkat dan ambigu: "yang lebih murah?", "mana yang bagus?"
          - Follow-up tanpa entitas eksplisit: "fasilitasnya?", "selain itu?"
          - Bahasa informal/campuran: "worth it gak?", "ada lagi?"

        Pipeline:
          1. Cek apakah query membutuhkan rewriting (panjang < 5 kata atau
             mengandung pronoun tanpa konteks eksplisit)
          2. Jika ya: bangun prompt mini ke Gemini dengan chat_history
          3. Hasil rewrite digunakan sebagai query baru untuk intent + retrieval
          4. Query asli TETAP disimpan untuk ditampilkan ke user

        Referensi:
          Ma et al. (2023) ACL — "Query Rewriting for Retrieval-Augmented Large
          Language Models" — rewriting mengurangi retrieval error hingga 27%
          untuk follow-up conversational queries.

          Gao et al. (2023) ACL — "Precise Zero-Shot Dense Retrieval without
          Relevance Labels" (HyDE) — enriching query dengan konteks sebelum
          retrieval secara signifikan mengungguli direct keyword matching.
        """
        query_stripped = query.strip()
        words = query_stripped.split()

        # Heuristik: Tidak perlu rewrite jika:
        # 1. Query sudah panjang dan eksplisit (> 7 kata)
        # 2. Tidak ada riwayat percakapan (chat baru, tidak ada konteks untuk di-resolve)
        ambiguous_pronouns = [
            "itu", "ini", "sana", "situ", "tersebut", "di sana", "di situ",
            "yang itu", "yang ini", "tadi", "sebelumnya", "sama", "juga",
            "alternatif", "selain", "lain", "lainnya", "lagi",
            "lebih", "paling", "terbaik", "termurah", "terdekat",
        ]
        is_short = len(words) <= 6
        has_ambiguous_pronoun = any(p in query_stripped.lower() for p in ambiguous_pronouns)
        has_history = chat_history and len(chat_history) >= 2

        # Jika query jelas dan panjang, skip rewriting untuk hemat biaya API
        if not (is_short or has_ambiguous_pronoun) or not has_history:
            return query_stripped

        # Bangun konteks dari riwayat percakapan (ambil 4 pesan terakhir)
        history_text = ""
        for msg in (chat_history or [])[-8:]:
            role = "User" if msg.get("role") == "user" else "Asisten"
            history_text += f"  {role}: {msg.get('content', '')[:300]}\n"

        last_place = ""
        if conversation_state and conversation_state.get("last_place"):
            last_place = f"\nTempat yang terakhir dibahas: {conversation_state['last_place']}"

        rewrite_prompt = (
            "Berikut adalah riwayat percakapan antara pengguna dan asisten wisata Danau Toba:\n"
            f"{history_text}"
            f"{last_place}\n\n"
            f'Query terbaru dari pengguna: "{query_stripped}"\n\n'
            "Tugas: Tulis ulang query tersebut menjadi pertanyaan mandiri (standalone question) "
            "yang LENGKAP dan EKSPLISIT dalam Bahasa Indonesia, sehingga dapat dipahami tanpa "
            "membaca riwayat percakapan sebelumnya. "
            "Pertahankan makna asli. Jangan tambahkan informasi yang tidak ada di konteks. "
            "HANYA tulis ulang query-nya saja, tanpa penjelasan atau kalimat tambahan."
        )

        try:
            rewritten = self._call_gemini_api(rewrite_prompt, max_tokens=128, temperature=0.1)
            if rewritten and len(rewritten.strip()) > 5:
                rewritten = rewritten.strip().strip('"').strip("'")
                print(f"✏️ Query rewritten: '{query_stripped}' → '{rewritten}'")
                return rewritten
        except Exception as e:
            print(f"⚠️ Query rewrite failed, using original: {e}")

        return query_stripped

    def _is_attraction_query(self, query: str) -> bool:
        """
        Return True when the user is asking about tourist DESTINATIONS / ATTRACTIONS
        (pantai, gunung, air terjun, museum, etc.) and NOT about food/dining places.
        Used to prevent the LLM from mixing restaurants into a 'tempat wisata' answer.
        """
        q = query.lower()

        # Explicit culinary signals — override: user DOES want food
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
            "masakan",
            "makanan",
            "kulineran",
        ]
        for sig in culinary_signals:
            if sig in q:
                return False

        # Attraction signals — user wants natural / cultural / artificial destinations
        attraction_signals = [
            "wisata",
            "destinasi",
            "objek wisata",
            "tempat wisata",
            "rekomendasi wisata",
            "tempat liburan",
            "tempat jalan",
            "tempat berkunjung",
            "pantai",
            "gunung",
            "air terjun",
            "danau",
            "hutan",
            "alam",
            "museum",
            "candi",
            "situs",
            "sejarah",
            "bersejarah",
            "budaya",
            "taman",
            "wahana",
            "desa wisata",
            "agrowisata",
            "ekowisata",
        ]
        return any(sig in q for sig in attraction_signals)

    def _extract_subject_from_query(self, query: str) -> str:
        """Extract the most likely subject/place mentioned in a document-grounded query."""
        query_clean = re.sub(r"\s+", " ", query).strip(" ?!.,")
        patterns = [
            # Format dengan 'di'
            r"(?:menu|alamat|harga|jam\s+operasional|jam\s+buka|jam\s+tutup|ulasan|review|fasilitas)\s+(?:makanan\s+)?di\s+(.+)$",
            r"(?:apa saja|apa|berapa|bagaimana)\s+.+?\s+di\s+(.+)$",
            r"(?:tentang|info(?:rmasi)?\s+(?:tentang)?)\s+(.+)$",
            # Format tanpa 'di': "ulasan D'Barans Cafe", "menu dbarans cafe"
            r"(?:menu|ulasan|review|alamat|harga|jam|fasilitas)\s+(.{4,})$",
            # Format lokasi: "X berada dimana", "X ada dimana"
            r"(.+?)\s+(?:berada|terletak|ada)\s+(?:di\s+)?(?:mana|dimana)\s*[?.]?$",
            # Format: "dimana X", "di mana letak X"
            r"(?:dimana|di\s+mana)\s+(?:letak\s+|lokasi\s+|alamat\s+)?(.+?)\s*[?.]?$",
            # Format: "lokasi X dimana", "alamat X berada"
            r"(?:lokasi|letak|alamat)\s+(.+?)(?:\s+dimana|\s+berada|\s+ada|\s+terletak)\s*[?.]?$",
            # Format: "tempat penginapan X berada dimana", "hotel X ada dimana"
            r"(?:tempat\s+)?(?:penginapan|hotel|resort|villa|homestay|cafe|restoran|warung|rumah\s+makan|wisata)\s+(.+?)\s+(?:berada|ada|terletak|dimana|di\s+mana)",
            # Standalone type+name: "tempat penginapan labersa", "hotel labersa"
            r"(?:tempat\s+)?(?:penginapan|hotel|resort|villa|homestay|cafe|restoran|warung|rumah\s+makan|wisata|objek\s+wisata)\s+(.{4,})$",
        ]

        # Prefix tipe tempat yang dibuang dari hasil ekstraksi
        TYPE_PREFIX = (
            r"^(?:tempat\s+)?"
            r"(?:penginapan|hotel|resort|villa|homestay|cafe|restoran|"
            r"warung|rumah\s+makan|wisata|objek\s+wisata)\s+"
        )

        for pattern in patterns:
            match = re.search(pattern, query_clean, flags=re.IGNORECASE)
            if match:
                subject = match.group(1).strip(" ?!.,")
                # Buang prefix tipe jika ada
                stripped = re.sub(TYPE_PREFIX, "", subject, flags=re.IGNORECASE).strip(
                    " ?!.,"
                )
                if len(stripped) >= 3:
                    subject = stripped
                if len(subject) >= 3:
                    if subject.lower() in ["danau toba", "toba"]:
                        return ""
                    return subject

        return ""

    def _build_document_unavailable_response(self, query: str) -> str:
        """Return an honest fallback when the requested fact is not found in the docs."""
        subject = self._extract_subject_from_query(query)
        if subject:
            return (
                f"Maaf, informasi tentang {subject} belum tersedia dalam dokumen yang saya miliki. "
                "Silakan coba nama tempat lain atau ubah pertanyaan agar lebih spesifik."
            )
        return (
            "Maaf, informasi tersebut belum tersedia dalam dokumen yang saya miliki. "
            "Silakan coba nama tempat lain atau ubah pertanyaan agar lebih spesifik."
        )

    def _is_query_relevant_to_context(self, query: str, context: str) -> bool:
        """Check if query is actually relevant to the retrieved context"""
        if not context or len(context) < 50:
            return False

        query_lower = query.lower()
        context_lower = context.lower()

        # If context contains tourism-related content, it's likely relevant for tourism queries
        tourism_context_keywords = [
            "wisata",
            "pantai",
            "hotel",
            "restoran",
            "cafe",
            "danau",
            "toba",
            "balige",
            "samosir",
            "parapat",
            "kuliner",
            "penginapan",
        ]

        has_tourism_context = any(
            kw in context_lower for kw in tourism_context_keywords
        )

        # Check query type
        is_tourism_query = any(
            kw in query_lower
            for kw in [
                "wisata",
                "makan",
                "hotel",
                "tempat",
                "pantai",
                "kuliner",
                "penginapan",
                "toba",
            ]
        )

        # If both query and context are tourism-related, consider it relevant
        if has_tourism_context and is_tourism_query:
            return True

        # Extract main keywords from query for more specific matching
        query_words = set(query_lower.split())
        stopwords = {
            "di", "ke", "dari", "yang", "untuk", "dan", "atau", "dengan", "adalah", "ini", "itu", 
            "ada", "tidak", "bisa", "apa", "mana", "bagaimana", "berapa", "saya", "kamu", "kami", 
            "mereka", "nya", "ter", "paling", "cara", "membuat", "buat", "tentang", "seperti", 
            "kalau", "jika", "bila", "kapan", "dimana", "siapa", "dalam", "pada", "kepada", 
            "karena", "sebab", "sehingga", "akan", "sudah", "belum", "masih", "telah", "lalu", 
            "kemudian", "saat", "ketika", "sebelum", "sesudah", "setelah", "juga", "hanya", "saja", 
            "lagi", "banyak", "sedikit", "semua", "seluruh", "beberapa", "suatu", "satu", "dua", 
            "tiga", "pertama", "kedua", "ketiga", "sangat", "sekali", "lebih", "kurang", "baik", 
            "buruk", "besar", "kecil", "baru", "lama", "jauh", "dekat", "tinggi", "rendah", 
            "murah", "mahal", "bagus", "jelek", "indah", "cantik", "menarik", "cocok", "pas", 
            "enak", "lezat", "nikmat", "sedap", "mantap", "halal", "haram", "buka", "tutup", 
            "jam", "hari", "bulan", "tahun", "minggu", "libur", "liburan", "wisata", "jalan", 
            "perjalanan", "tiket", "masuk", "harga", "biaya", "ongkos", "tarif", "sewa", 
            "rental", "pesan", "booking", "kamar", "fasilitas", "menu", "makanan", "minuman", 
            "minum", "pesanan", "porsi", "rasa", "tempat", "lokasi", "alamat", "daerah"
        }

        meaningful_words = query_words - stopwords

        # Check if meaningful query words appear in context
        matches = 0
        for word in meaningful_words:
            if len(word) > 2 and word in context_lower:
                matches += 1

        # Need at least some overlap
        if len(meaningful_words) > 0:
            relevance_ratio = matches / len(meaningful_words)
            return relevance_ratio >= 0.2  # At least 20% of keywords should match

        return has_tourism_context

    def _get_general_answer(self, query: str) -> str:
        """Answer general questions via Gemini."""
        gemini_answer = self._ask_gemini_general(query)
        if gemini_answer:
            return gemini_answer
        return "Maaf, saya sedang tidak bisa memproses pertanyaan Anda. Silakan coba lagi. 🙏"

    def _ask_gemini_general(self, query: str) -> str:
        """Ask Gemini with general knowledge when no document context is available.
        Used as fallback when RAG retrieval finds no relevant chunks.
        """
        api_key = self._get_available_api_key()
        if not api_key:
            return None

        # --- DuckDuckGo Web Search Integration ---
        web_context = ""
        try:
            import asyncio
            from ddgs import DDGS
            
            # Setup event loop for duckduckgo_search in FastAPI worker thread
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            print(f"🌐 [Web RAG] Mencari di DuckDuckGo untuk query: {query[:30]}...")
            with DDGS() as ddgs_client:
                results = [r for r in ddgs_client.text(query, max_results=3)]
            
            if results:
                formatted_results = "\n".join([f"- {r.get('title', '')}: {r.get('body', '')}" for r in results])
                web_context = f"\n\n[Hasil Pencarian Internet (Web RAG)]:\n{formatted_results}\n\n"
        except Exception as e:
            print(f"⚠️ [Web RAG] Gagal memanggil DuckDuckGo: {e}")
            web_context = ""
        # -----------------------------------------

        if web_context:
            prompt = (
                "Kamu adalah Asisten Wisata Danau Toba yang ramah dan informatif.\n"
                f'Pengguna bertanya: "{query}"\n'
                f"{web_context}"
                "Gunakan [Hasil Pencarian Internet] di atas sebagai referensi tambahan.\n"
                "PENTING: Jika pertanyaan TIDAK BERKAITAN dengan pariwisata, kuliner, geologi, budaya, "
                "atau informasi yang relevan dengan Sumatera Utara / Danau Toba (misal: resep masakan umum, coding, dsb), "
                "TOLAK dengan sopan dan jelaskan bahwa kamu adalah asisten wisata Danau Toba.\n"
                "Jawab dengan format rapi dan gunakan Bahasa Indonesia."
            )
        else:
            prompt = (
                "Kamu adalah asisten wisata Danau Toba yang ramah dan informatif.\n"
                f'Pengguna bertanya: "{query}"\n\n'
                "Tidak ada dokumen spesifik yang ditemukan di database.\n"
                "Jawab berdasarkan pengetahuan umummu jika pertanyaan masih berkaitan "
                "dengan pariwisata, budaya Batak, Sumatera Utara, atau topik yang tidak "
                "terlalu jauh dari konteks wisata.\n"
                "Jika pertanyaan BENAR-BENAR tidak relevan (kata kasar, NSFW, atau "
                "topik berbahaya), tolak dengan sopan dan arahkan ke topik wisata Danau Toba.\n"
                "Gunakan emoji dan format rapi. Jawab dalam Bahasa Indonesia."
            )

        try:
            result = self._call_gemini_api(prompt, max_tokens=1024, temperature=0.7)
            if result and len(result.strip()) > 10:
                return result
        except Exception as e:
            print(f"⚠️ Error in _ask_gemini_general: {e}")
        return None

    def _get_out_of_scope_response(self, query: str) -> str:
        """Response for questions outside our knowledge domain — via Gemini."""
        gemini_answer = self._ask_gemini_general(query)
        if gemini_answer:
            return gemini_answer
        return "Maaf, saya sedang tidak bisa memproses pertanyaan Anda. Silakan coba lagi. 🙏"

    def _get_greeting_response(self) -> str:
        """Return a greeting response via Gemini."""
        prompt = (
            "Kamu adalah asisten wisata Danau Toba yang ramah.\n"
            "Pengguna menyapa kamu. Balas dengan sapaan hangat yang singkat, "
            "perkenalkan diri sebagai Asisten Wisata Danau Toba, dan tanya apa yang ingin diketahui. "
            "Gunakan emoji secukupnya. Jawab dalam Bahasa Indonesia, maksimal 5 baris."
        )
        result = self._call_gemini_api(prompt, max_tokens=200, temperature=0.8)
        if result:
            return result
        return "Horas! 👋 Saya Asisten Wisata Danau Toba. Ada yang ingin Anda tanyakan?"

    # ── API key helpers tidak lagi digunakan (Vertex AI pakai ADC) ──
    def _get_available_api_key(self):
        """Stub — Vertex AI tidak memerlukan API key manual."""
        return "vertex-ai"

    def _mark_key_failed(self, key):
        """Stub — tidak relevan untuk Vertex AI."""
        pass

    def _build_models_to_try(self) -> list:
        """
        Urutan fallback: gemini-2.5-flash dulu,
        lalu model Gemini 2.x/1.5 sebagai cadangan.
        """
        all_fallbacks = {
            "gemini-2.5-flash":                ["gemini-2.0-flash", "gemini-1.5-flash"],
            "gemini-3-flash-preview":          ["gemini-2.5-flash", "gemini-1.5-flash"],
            "gemini-2.5-pro-preview-05-06":    ["gemini-2.5-flash", "gemini-1.5-flash"],
            "gemini-2.0-flash":                ["gemini-2.5-flash", "gemini-1.5-flash"],
            "gemini-1.5-flash":                ["gemini-2.5-flash"],
        }
        fallbacks = all_fallbacks.get(self.model_name, ["gemini-2.5-flash"])
        return [self.model_name] + [m for m in fallbacks if m != self.model_name]

    def _call_gemini_api(
        self, prompt: str, max_tokens: int = 512, temperature: float = 0.7
    ) -> str:
        """Panggil Gemini via google-genai SDK (Vertex AI) — primary dulu, fallback jika gagal."""

        # Rate limiting sederhana
        current_time = time_module.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            print(f"Rate limit protection: waiting {wait_time:.1f}s...")
            time_module.sleep(wait_time)
        self.last_request_time = time_module.time()

        models_to_try = self._build_models_to_try()
        last_error = None

        for model_name in models_to_try:
            cfg = self.MODEL_CONFIG.get(
                model_name,
                {"max_output_tokens": 2048, "location": "us-central1", "thinking": False},
            )
            effective_max_tokens = max(max_tokens, cfg["max_output_tokens"])
            location = cfg["location"]
            client = self._get_client(location)

            # Config generasi
            generate_kwargs: dict = {
                "model": model_name,
                "config": types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=effective_max_tokens,
                    top_p=0.9,
                ),
            }

            # Gemini 3 mendukung thinking_level — set budget ke 0 untuk kecepatan
            if cfg.get("thinking"):
                generate_kwargs["config"] = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=effective_max_tokens,
                    top_p=0.9,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                )

            for attempt in range(3):
                try:
                    print(f"[{model_name}|{location}] maxTokens={effective_max_tokens}, attempt {attempt + 1}...")

                    response = client.models.generate_content(
                        contents=prompt,
                        **generate_kwargs,
                    )

                    if response and response.text:
                        full_text = response.text.strip()
                        if len(full_text) > 10:
                            print(f"Response from [{model_name}] ({len(full_text)} chars)")
                            return full_text

                    print(f"[{model_name}] Empty response, skipping...")
                    break

                except Exception as e:
                    last_error = e
                    error_str = str(e)

                    # Quota / rate limit
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        print(f"Quota exceeded on [{model_name}], attempt {attempt + 1}/3")
                        if attempt < 2:
                            time_module.sleep(10)
                            continue
                        break  # coba model berikutnya

                    # Model tidak tersedia / invalid
                    if any(x in error_str for x in ["404", "400", "NOT_FOUND", "INVALID_ARGUMENT"]):
                        print(f"[{model_name}] error: {error_str[:100]}")
                        break

                    # Network error
                    if any(x in error_str for x in ["resolve", "connection", "timeout"]):
                        print(f"Network error: {error_str[:100]}")
                        return None

                    print(f"[{model_name}] attempt {attempt + 1} failed: {error_str[:100]}")
                    if attempt < 2:
                        time_module.sleep(2)
                    continue

        print(f"All models failed: {str(last_error)[:100] if last_error else 'unknown'}")
        return None

    def generate_response(
        self,
        query: str,
        context: str = "",
        chat_history: list = None,
        conversation_state: dict = None,
        max_new_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        user_preferences: list = None,
        is_first_message: bool = True,
    ) -> str:
        """Generate response using Gemini API with intelligent fallback"""

        # ── Query Rewriting (Ma et al. 2023; Gao et al. 2023) ──────────────
        # Perjelas query ambigu atau follow-up sebelum masuk ke intent classifier.
        # Query asli (query) tetap digunakan untuk tampilan ke user;
        # effective_query digunakan untuk intent detection dan retrieval.
        effective_query = self._rewrite_query(
            query,
            chat_history=chat_history,
            conversation_state=conversation_state,
        )

        intent = self._classify_intent(effective_query)
        print(f"🎯 Intent: {intent} | Query: {effective_query[:60]}...")

        # Handle different intents
        if intent == "greeting":
            return self._get_greeting_response()

        if intent == "out_of_scope":
            return self._get_out_of_scope_response(query)

        has_context = context and len(context.strip()) > 100

        # For general queries without tourism context, be honest
        if intent == "general_question" and not has_context:
            return self._get_out_of_scope_response(query)

        # Check if context is actually relevant
        if has_context and not self._is_query_relevant_to_context(query, context):
            print("⚠️ Retrieved context not relevant to query")
            if intent == "tourism":
                # Konteks PDF tidak relevan → coba DuckDuckGo sebelum menyerah
                print("🌐 [Web Fallback] Konteks PDF tidak relevan — mencari di DuckDuckGo...")
                web_answer = self._ask_gemini_general(query)
                if web_answer:
                    return web_answer
                return self._build_document_unavailable_response(query)

            print("⚠️ Falling back to LLM general knowledge")
            general_answer = self._ask_gemini_general(query)
            if general_answer:
                return general_answer
            return "Maaf, saya sedang tidak bisa memproses pertanyaan Anda. Silakan coba lagi. 🙏"

        if has_context:
            # Build personalization hint from user's favorite categories
            pref_hint = ""
            CATEGORY_LABELS = {
                "alam": "Wisata Alam (gunung, danau, air terjun)",
                "budaya": "Wisata Budaya (museum, desa adat, tradisi Batak)",
                "kuliner": "Kuliner khas Batak",
                "sejarah": "Wisata Sejarah (situs, monumen)",
                "religi": "Wisata Religi",
                "air": "Wisata Air (pantai, kolam, water sport)",
                "petualangan": "Petualangan (hiking, camping, rafting)",
                "fotografi": "Spot Foto Instagram",
            }
            if user_preferences:
                labels = [CATEGORY_LABELS.get(p, p) for p in user_preferences]
                pref_hint = f"\n\nCATATAN PREFERENSI PENGGUNA: Pengguna ini menyukai {', '.join(labels)}. Jika relevan, prioritaskan rekomendasi sesuai minat tersebut.\n"

            greeting_rule = (
                "10. Ini adalah pesan PERTAMA dalam percakapan — boleh membuka jawaban dengan sapaan singkat yang hangat."
                if is_first_message
                else "10. Ini adalah lanjutan percakapan — JANGAN memulai jawaban dengan sapaan (Halo, Horas, Selamat datang, dsb). Langsung jawab pertanyaan."
            )

            # Format chat history for context-aware multi-turn conversation
            history_section = ""
            if chat_history and len(chat_history) > 0:
                history_lines = []
                for msg in chat_history[-12:]:  # Last 12 messages (6 turns)
                    role = "Pengguna" if msg.get("role") == "user" else "Asisten"
                    content = msg.get("content", "")[:600]
                    history_lines.append(f"  {role}: {content}")
                history_section = (
                    "\n\nKONTEKS PERCAKAPAN SEBELUMNYA:\n"
                    + "\n".join(history_lines)
                    + "\n\n(Gunakan konteks percakapan di atas untuk memahami maksud pengguna "
                    "jika pertanyaan baru merujuk ke topik sebelumnya, misalnya 'tempat itu', "
                    "'yang tadi', 'saingannya', 'alternatif lain', dll.)\n"
                )

            state_section = ""
            if conversation_state and isinstance(conversation_state, dict):
                state_bits = []
                if conversation_state.get("last_place"):
                    state_bits.append(
                        f"- Tempat terakhir dibahas: {conversation_state.get('last_place')}"
                    )
                if conversation_state.get("last_topic"):
                    state_bits.append(
                        f"- Topik aktif: {conversation_state.get('last_topic')}"
                    )
                if conversation_state.get("last_intent"):
                    state_bits.append(
                        f"- Intent terakhir: {conversation_state.get('last_intent')}"
                    )
                excluded = conversation_state.get("excluded_entities") or []
                if isinstance(excluded, list) and excluded:
                    state_bits.append(
                        "- Tempat yang harus dihindari sebagai jawaban utama: "
                        + ", ".join(excluded[:5])
                    )
                if state_bits:
                    state_section = (
                        "\n\nRINGKASAN STATE PERCAKAPAN (PERSISTEN):\n"
                        + "\n".join(state_bits)
                        + "\n(Gunakan ringkasan ini untuk coreference seperti: itu, tersebut, di sana, fasilitasnya, selain itu.)\n"
                    )

            # Build query type hint for rule #17
            if self._is_attraction_query(query):
                query_type_hint = (
                    "\n\nTIPE QUERY SAAT INI: Pengguna bertanya tentang TEMPAT WISATA "
                    "(destinasi alam, budaya, buatan). "
                    "WAJIB hanya tampilkan destinasi wisata alam/budaya/buatan. "
                    "DILARANG KERAS memasukkan restoran, warung, cafe, rumah makan, atau kedai "
                    "sebagai rekomendasi tempat wisata.\n"
                )
            else:
                query_type_hint = ""

            prompt = f"""Kamu adalah asisten wisata Danau Toba yang ramah, informatif, dan detail.

INSTRUKSI PENTING:
1. Jawab berdasarkan INFORMASI DOKUMEN di bawah dengan LENGKAP dan DETAIL
2. Untuk setiap tempat wisata/hotel/rumah makan, SELALU sebutkan NAMA LENGKAPNYA sebagaimana tertulis di dokumen
3. Gunakan format yang rapi dengan emoji dan bullet points
4. Berikan minimal 3-5 rekomendasi jika tersedia dalam dokumen
5. Jika informasi BENAR-BENAR tidak ada dalam dokumen, gunakan pengetahuan umum atau informasi dari internet yang relevan untuk menjawab. Jangan langsung bilang 'tidak tersedia' jika pertanyaan masih dalam ranah wisata, geologi, sejarah, atau budaya Danau Toba.
6. JANGAN mengarang informasi wisata, harga tiket masuk, atau fakta tentang tempat yang tidak ada dalam dokumen. Khusus transportasi lokal umum (ojek, bentor, angkot, sewa motor/mobil), boleh gunakan estimasi pengetahuan umum dan sajikan secara natural.
7. JANGAN menyebutkan nomor halaman, nomor chunk, atau referensi teknis dokumen
8. JANGAN pernah menulis teks placeholder seperti "(Tidak disebutkan namanya...)", "(Nama tidak tersedia)", atau sejenisnya — gunakan nama yang tertulis di dokumen apa adanya
9. Akhiri dengan ajakan untuk bertanya lebih lanjut
10. Jika pengguna menanyakan SATU tempat spesifik, fokus jawab tempat itu saja, bukan daftar rekomendasi umum.
11. Jika dokumen memuat field eksplisit seperti "Menu", "Harga", "Jam Operasional", "Alamat", "Lokasi", atau "Long & Lat", salin fakta tersebut dengan setia dari dokumen.
12. Jika dokumen "Data Terstruktur: Lokasi Database" tersedia dalam konteks, WAJIB masukkan SEMUA tempat yang tercantum di sana ke dalam jawaban — jangan melewatkan satu pun.
13. Untuk pertanyaan "apa saja" atau "daftar", tampilkan SELURUH tempat yang ada dalam konteks, bukan hanya sebagian.
14. PARTIAL NAME MATCHING: Jika nama yang disebutkan pengguna hanya SEBAGIAN dari nama lengkap di dokumen, anggap itu tempat yang sama dan jawab lengkap. PENTING: Gunakan nama entitas yang ADA di dokumen/konteks, bukan nama yang diinvensi. Contoh BENAR: user sebut "Meat" → dokumen punya "Desa Wisata Meat" → jawab tentang "Desa Wisata Meat". Contoh SALAH: user sebut "Wisata Meat" → JANGAN jawab "Air Terjun Meat" jika itu tidak ada di dokumen.
15. QUERY LOKASI (dimana/alamat/lokasi): Jika konteks mengandung field Lokasi, Alamat, Long & Lat, atau koordinat dari tempat yang ditanyakan, WAJIB tampilkan semua data tersebut. DILARANG KERAS mengatakan "lokasi tidak tersedia" atau "belum tersedia secara rinci" jika data lokasi ADA dalam konteks.
16. QUERY TRANSPORTASI / RUTE: Jika konteks mengandung "[Data Rute]", gunakan data jarak dan lokasi tersebut untuk menjawab pertanyaan tentang rute, kendaraan, atau cara menuju. Ikuti panduan berikut:
   a) PRIORITAS UTAMA: Jika dokumen memuat data transportasi spesifik (KBT, KPT, Kapal Pora Pora, Parisma, Kapal Kaldera, dll), sebutkan dengan nama, rute, dan tarifnya.
   b) TRANSPORTASI LOKAL: Untuk transportasi lokal jarak dekat di kawasan Danau Toba / Kabupaten Toba yang TIDAK ada di dokumen (ojek, bentor/becak motor, angkot, sewa motor/mobil), kamu DIIZINKAN menggunakan pengetahuan umum untuk menyebut opsi tersebut beserta estimasi tarif realistis di kawasan tersebut. Sajikan secara natural tanpa memberi label sumber.
   c) Selalu sebutkan jarak dan estimasi waktu tempuh berdasarkan [Data Rute] yang tersedia.
   d) Urutkan dari yang paling relevan: transportasi lokal jarak dekat dulu, baru transportasi antar kota/kapal ferry jika relevan.
   e) FORMAT JAWABAN TRANSPORTASI: Gunakan format terstruktur berikut:
      - Baris pembuka: satu kalimat menyebut jarak total dan perkiraan waktu tempuh.
      - Bagian **Pilihan Transportasi**: daftar bernomor; tiap opsi berisi nama moda, estimasi tarif, dan catatan singkat (cara naik / durasi).
      - Bagian **Tips Perjalanan** (jika relevan): waktu terbaik berangkat, negosiasi tarif, koneksi antar moda, biaya masuk jika ada.
      - Tutup dengan satu kalimat singkat ajakan tanya lebih lanjut.
17. KATEGORI 'TEMPAT WISATA' vs 'KULINER': Ini SANGAT PENTING. Bedakan dua kategori ini secara tegas:
   • "Tempat wisata" / "destinasi wisata" / "objek wisata" = DESTINASI ALAM (pantai, gunung, air terjun, danau, hutan, gua), WISATA BUDAYA (museum, situs sejarah, candi, rumah adat, desa wisata), dan WISATA BUATAN (taman hiburan, taman rekreasi, agrowisata, ekowisata). BUKAN tempat makan.
   • "Kuliner" / "tempat makan" / "rekomendasi makan" = restoran, warung, rumah makan, cafe, kedai, dll. BUKAN tempat wisata alam/budaya.
   Jika query pengguna mengandung kata 'wisata', 'destinasi', 'objek wisata', 'tempat liburan', atau 'rekomendasi wisata' TANPA menyebut 'makan/kuliner', JANGAN memasukkan restoran/warung/cafe/rumah makan sebagai rekomendasi.
   Jika query pengguna mengandung 'kuliner', 'makan', 'restoran', 'warung', 'cafe', JANGAN memasukkan pantai/gunung/air terjun sebagai rekomendasi.
18. ANTI-HALUSINASI NAMA ENTITAS — INI SANGAT KRITIS (berlaku untuk SEMUA tempat, bukan hanya satu):
   PRINSIP UTAMA: Gunakan nama entitas PERSIS seperti yang tertulis di konteks dokumen atau field "Nama"
   di "[Data Spesifik Lokasi Database]". DILARANG KERAS menginvensi, mengganti, atau memodifikasi nama.

   ATURAN A — Kata deskriptif bukan nama entitas baru:
   • Kata-kata dalam field "Deskripsi" adalah ATRIBUT tempat tersebut, BUKAN nama tempat baru.
   • "air jernih"    ≠ nama "Air Terjun [X]"   → JANGAN buat air terjun baru
   • "pasir putih"   ≠ nama "Pantai [X]"        → JANGAN buat pantai baru
   • "bukit hijau"   ≠ nama "Bukit [X]"         → JANGAN buat bukit baru
   • "kolam renang"  ≠ nama "Waterpark [X]"     → JANGAN buat waterpark baru
   • "hutan pinus"   ≠ nama "Wisata Hutan [X]"  → JANGAN buat destinasi baru

   ATURAN B — Nama singkat/sebagian tidak boleh menghasilkan nama baru:
   • User sebut "Wisata Situmurun"   → gunakan nama persis di DB: "Air Terjun Situmurun"
   • User sebut "Hotel Labersa"      → gunakan nama persis di DB: "Labersa Grand Waterpark & Hotel"
   • User sebut "Pantai Bulbul"      → gunakan nama persis di DB: "Pantai Lumban Bulbul"
   • User sebut "Sipiso"             → gunakan nama persis di DB: "Air Terjun Sipiso-piso"
   • User sebut "Wisata X" atau "Tempat X" → cari nama TEPAT di konteks yang mengandung kata X,
     jangan ubah kategorinya (mis: "Desa Wisata X" jangan dijadikan "Air Terjun X" atau "Pantai X")

   ATURAN C — Jika ada beberapa entitas dengan kata kunci yang sama:
   • Sebutkan MASING-MASING entitas sesuai nama persisnya di dokumen.
   • Contoh: ada "Pantai Meat" DAN "Desa Wisata Meat" → sebutkan keduanya dengan nama masing-masing.
   • JANGAN gabungkan atau ciptakan entitas baru dari dua entitas yang berbeda.

   ATURAN D — Prioritas sumber nama entitas:
   1. Field "Nama" di "[Data Spesifik Lokasi Database]" → PRIORITAS TERTINGGI, wajib digunakan
   2. Nama yang tertulis tebal/eksplisit di paragraf dokumen PDF → gunakan apa adanya
   3. JANGAN gunakan pengetahuan umum untuk mengarang nama entitas yang tidak ada di konteks
{query_type_hint}{greeting_rule}
{pref_hint}{history_section}{state_section}
INFORMASI DOKUMEN:
{context[:6000]}

PERTANYAAN: {query}

JAWABAN:"""

            # Call Gemini — fallback model otomatis via _build_models_to_try
            result = self._call_gemini_api(
                prompt, max_tokens=max_new_tokens, temperature=temperature
            )

            # Jika semua model gagal, fallback ke general knowledge (1x saja)
            if result is None or len(result) < 10:
                print("🔄 API failed — fallback general knowledge (1x only)...")
                answer = self._ask_gemini_general(query)
                return (
                    answer
                    or "Maaf, saya sedang tidak bisa memproses pertanyaan Anda. Silakan coba lagi. 🙏"
                )

            return result
        else:
            # No context available — untuk intent tourism, COBA WEB SEARCH dulu
            # sebelum menyerah. Ini mencegah sistem mengatakan "tidak tersedia"
            # untuk pertanyaan yang valid (sejarah, event, geologi Danau Toba)
            # yang tidak tercakup dalam PDF lokal.
            #
            # Referensi: Trivedi et al. (2022) IRCoT — "iterative retrieval from
            # multiple sources prevents answer refusal on valid questions that
            # fall outside the primary document corpus."
            if intent == "tourism":
                print("🌐 [Web Fallback] Tidak ada konteks PDF — mencari di DuckDuckGo...")
                web_answer = self._ask_gemini_general(query)
                if web_answer:
                    return web_answer
                # Jika web search juga gagal, baru kembalikan pesan tidak tersedia
                return self._build_document_unavailable_response(query)

            # No context available — try LLM general knowledge
            general_answer = self._ask_gemini_general(query)
            if general_answer:
                return general_answer
            return "Maaf, saya sedang tidak bisa memproses pertanyaan Anda. Silakan coba lagi. 🙏"

    def __call__(self, prompt: str, max_new_tokens: int = 2048, **kwargs) -> str:
        return self.generate_response(
            query=prompt, max_new_tokens=max_new_tokens, **kwargs
        )
