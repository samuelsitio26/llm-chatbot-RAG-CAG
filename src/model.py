"""
Gemini API Model Wrapper for CAG System
Uses Google Gemini API via REST API (no SDK dependency issues)
With intelligent fallback when API fails
"""
import os
import re
import requests
import json
import time as time_module
from dotenv import load_dotenv

load_dotenv()


class GeminiChatModel:
    """
    Wrapper for Google Gemini API using REST API
    No SDK required - uses direct HTTP requests
    Includes context-based fallback when API fails
    """

    # ── Capability config per model ──────────────────────────────────
    MODEL_CONFIG = {
        "gemini-2.5-pro": {
            "max_output_tokens": 8192,
            "timeout":           60,
            "supports_thinking": False,  # thinkingConfig NOT supported → error 400
        },
        "gemini-2.5-flash": {
            "max_output_tokens": 4096,
            "timeout":           30,
            "supports_thinking": True,   # thinkingConfig supported
        },
        "gemini-2.0-flash-exp": {
            "max_output_tokens": 2048,
            "timeout":           30,
            "supports_thinking": False,
        },
        "gemini-1.5-flash": {
            "max_output_tokens": 2048,
            "timeout":           30,
            "supports_thinking": False,
        },
        "gemini-1.5-pro": {
            "max_output_tokens": 4096,
            "timeout":           30,
            "supports_thinking": False,
        },
    }

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name
        
        # Support multiple API keys for rotation
        api_keys_str = os.getenv("GEMINI_API_KEYS", "")
        if api_keys_str:
            self.api_keys = [k.strip() for k in api_keys_str.split(",") if k.strip()]
        else:
            single_key = os.getenv("GEMINI_API_KEY", "")
            self.api_keys = [single_key] if single_key else []
        
        if not self.api_keys:
            print("⚠️ No Gemini API keys found - will use context-based fallback only")
        
        self.current_key_index = 0
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        
        # Rate limiting: track last request time
        self.last_request_time = 0
        self.min_request_interval = 5  # Minimum 5 seconds between requests (safer margin for 15 RPM)
        
        # Track failed keys temporarily
        self.failed_keys = {}  # key -> failure_time
        self.key_cooldown = 60  # seconds before retrying failed key
        
        print(f"🔍 Initializing Gemini API: {model_name}")
        print(f"🔑 API keys available: {len(self.api_keys)}")
        print(f"⏱️ Rate limit protection: {self.min_request_interval}s between requests")
        print(f"🔄 Context-based fallback: ENABLED")
    
    def _classify_intent(self, query: str) -> str:
        """Classify user intent: greeting, tourism, general, or out_of_scope"""
        query_lower = query.lower().strip()
        
        greeting_words = ['halo', 'hai', 'hello', 'hi', 'hey', 'hei', 'horas', 'selamat']
        greeting_phrases = ['selamat pagi', 'selamat siang', 'selamat sore', 'selamat malam', 'apa kabar']
        
        # Check greeting FIRST (before out_of_scope)
        words = query_lower.split()
        if len(words) <= 3:
            if any(word in greeting_words for word in words):
                return 'greeting'
            for phrase in greeting_phrases:
                if query_lower.startswith(phrase):
                    return 'greeting'
        
        # Detect general questions (math, basic questions) - answer then redirect
        import re
        if re.search(r'\d+\s*[\+\-\*\/x]\s*\d+', query_lower) or 'berapa' in query_lower:
            return 'general_question'

        # Document-style business/place questions should stay grounded in tourism docs.
        if re.search(
            r'\b(menu|alamat|harga|jam\s+operasional|jam\s+buka|jam\s+tutup|ulasan|review|fasilitas)\b',
            query_lower,
        ):
            return 'tourism'
        
        # Strong tourism keywords that definitely indicate Toba tourism query
        strong_tourism_keywords = [
            'wisata', 'pantai', 'danau', 'hotel', 'penginapan', 'homestay',
            'villa', 'resort', 'toba', 'samosir', 'balige', 'parapat', 'tomok', 
            'tuktuk', 'sipiso', 'kuliner', 'batak', 'ulos', 'air terjun',
            'menu', 'warung', 'rumah makan', 'restoran', 'restaurant', 'kedai'
        ]
        
        # Check strong tourism keywords first (takes highest priority)
        for kw in strong_tourism_keywords:
            if kw in query_lower:
                return 'tourism'
        
        # Weak tourism keywords
        weak_tourism_keywords = [
            'rekomendasi', 'destinasi', 'liburan', 'trip', 'travel', 'budget', 
            'harga', 'murah', 'mahal', 'honeymoon', 'keluarga', 'makanan', 
            'cafe', 'resto', 'museum', 'budaya', 'adat', 'sumut', 'sumatera', 
            'medan', 'siantar', 'karo', 'dairi', 'tempat', 'makan', 'menginap', 
            'jalan-jalan', 'view', 'pemandangan', 'gunung', 'kulineran'
        ]
        
        for kw in weak_tourism_keywords:
            if kw in query_lower:
                return 'tourism'
        
        # General questions - answer then redirect to tourism
        general_patterns = [
            'siapa', 'apa itu', 'kapan', 'dimana', 'mengapa', 'bagaimana',
            'terima kasih', 'makasih', 'thanks'
        ]
        for pattern in general_patterns:
            if pattern in query_lower:
                return 'general_question'
        
        # Default: treat as general question
        return 'general_question'

    def _extract_subject_from_query(self, query: str) -> str:
        """Extract the most likely subject/place mentioned in a document-grounded query."""
        query_clean = re.sub(r'\s+', ' ', query).strip(' ?!.,')
        patterns = [
            r'(?:menu|alamat|harga|jam\s+operasional|jam\s+buka|jam\s+tutup|ulasan|review|fasilitas)\s+(?:makanan\s+)?di\s+(.+)$',
            r'(?:apa saja|apa|berapa|bagaimana)\s+.+?\s+di\s+(.+)$',
            r'(?:tentang|info(?:rmasi)?\s+(?:tentang)?)\s+(.+)$',
        ]

        for pattern in patterns:
            match = re.search(pattern, query_clean, flags=re.IGNORECASE)
            if match:
                subject = match.group(1).strip(' ?!.,')
                if len(subject) >= 3:
                    return subject

        return ''

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
        tourism_context_keywords = ['wisata', 'pantai', 'hotel', 'restoran', 'cafe', 'danau', 
                                     'toba', 'balige', 'samosir', 'parapat', 'kuliner', 'penginapan']
        
        has_tourism_context = any(kw in context_lower for kw in tourism_context_keywords)
        
        # Check query type
        is_tourism_query = any(kw in query_lower for kw in ['wisata', 'makan', 'hotel', 'tempat', 
                                                             'pantai', 'kuliner', 'penginapan', 'toba'])
        
        # If both query and context are tourism-related, consider it relevant
        if has_tourism_context and is_tourism_query:
            return True
        
        # Extract main keywords from query for more specific matching
        query_words = set(query_lower.split())
        stopwords = {'di', 'ke', 'dari', 'yang', 'untuk', 'dan', 'atau', 'dengan', 'adalah', 
                     'ini', 'itu', 'ada', 'tidak', 'bisa', 'apa', 'mana', 'bagaimana', 'berapa',
                     'saya', 'kamu', 'kami', 'mereka', 'nya', 'ter', 'paling'}
        
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

        prompt = (
            "Kamu adalah asisten wisata Danau Toba yang ramah dan informatif.\n"
            f"Pengguna bertanya: \"{query}\"\n\n"
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
            if result and len(result.strip()) > 20:
                return result
        except Exception:
            pass
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
    
    def _get_available_api_key(self):
        """Get an available API key, skipping recently failed ones"""
        if not self.api_keys:
            return None
        
        current_time = time_module.time()
        
        # Clean up old failures
        self.failed_keys = {
            k: t for k, t in self.failed_keys.items() 
            if current_time - t < self.key_cooldown
        }
        
        # Try to find a working key
        for i in range(len(self.api_keys)):
            idx = (self.current_key_index + i) % len(self.api_keys)
            key = self.api_keys[idx]
            if key not in self.failed_keys:
                self.current_key_index = idx
                return key
        
        # All keys failed recently, return the oldest failed one
        if self.api_keys:
            return self.api_keys[self.current_key_index]
        return None
    
    def _mark_key_failed(self, key):
        """Mark an API key as temporarily failed"""
        self.failed_keys[key] = time_module.time()
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)

    def _build_models_to_try(self) -> list:
        """
        Bangun urutan model fallback berdasarkan self.model_name.
        Primary model selalu duluan, fallback menyesuaikan.
        """
        all_fallbacks = {
            "gemini-2.5-flash":    ["gemini-1.5-flash", "gemini-2.0-flash-exp"],
            "gemini-2.5-pro":      ["gemini-2.5-flash", "gemini-1.5-flash"],
            "gemini-1.5-flash":    ["gemini-2.5-flash"],
            "gemini-1.5-pro":      ["gemini-2.5-flash", "gemini-1.5-flash"],
            "gemini-2.0-flash-exp": ["gemini-2.5-flash", "gemini-1.5-flash"],
        }
        fallbacks = all_fallbacks.get(self.model_name, ["gemini-2.5-flash"])
        return [self.model_name] + [m for m in fallbacks if m != self.model_name]

    def _call_gemini_api(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        """Call Gemini API via REST — primary model first, fallback if needed."""

        api_key = self._get_available_api_key()
        if not api_key:
            print("⚠️ No API keys available")
            return None

        # Rate limiting: wait if needed
        current_time    = time_module.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            print(f"⏳ Rate limit protection: waiting {wait_time:.1f}s...")
            time_module.sleep(wait_time)

        self.last_request_time = time_module.time()

        models_to_try = self._build_models_to_try()
        headers       = {"Content-Type": "application/json"}
        last_error    = None

        for model in models_to_try:
            cfg = self.MODEL_CONFIG.get(model, {
                "max_output_tokens": 2048,
                "timeout":           30,
                "supports_thinking": False,
            })

            # Gunakan max antara caller vs minimum config model
            effective_max_tokens = max(max_tokens, cfg["max_output_tokens"])

            url = f"{self.base_url}/{model}:generateContent?key={api_key}"

            generation_config = {
                "temperature":     temperature,
                "maxOutputTokens": effective_max_tokens,
                "topP":            0.9,
                "topK":            40,
            }

            # thinkingConfig HANYA untuk model yang support (saat ini: gemini-2.5-flash)
            if cfg["supports_thinking"]:
                generation_config["thinkingConfig"] = {"thinkingBudget": 0}

            payload = {
                "contents":         [{"parts": [{"text": prompt}]}],
                "generationConfig": generation_config,
            }

            for attempt in range(3):
                try:
                    print(f"📡 {model} (maxTokens={effective_max_tokens}), attempt {attempt+1}...")
                    response = requests.post(
                        url, headers=headers, json=payload,
                        timeout=cfg["timeout"]
                    )

                    if response.status_code == 429:
                        print(f"⏳ Rate limited on {model}, attempt {attempt + 1}/3")
                        if attempt < 2:
                            time_module.sleep(5)
                            continue
                        else:
                            self._mark_key_failed(api_key)
                            break  # coba model berikutnya

                    if response.status_code in [400, 404]:
                        print(f"⚠️ {model} error {response.status_code}: {response.text[:100]}")
                        break  # skip ke model berikutnya

                    if response.status_code != 200:
                        print(f"⚠️ {model} unexpected {response.status_code}: {response.text[:100]}")
                        break

                    result = response.json()

                    if "candidates" in result and len(result["candidates"]) > 0:
                        candidate     = result["candidates"][0]
                        finish_reason = candidate.get("finishReason", "unknown")

                        if "content" in candidate and "parts" in candidate["content"]:
                            parts      = candidate["content"]["parts"]
                            text_parts = [p["text"] for p in parts if "text" in p]
                            if text_parts:
                                full_text = "\n".join(text_parts).strip()
                                if len(full_text) > 10:
                                    print(f"✅ Response from {model} ({len(full_text)} chars, reason: {finish_reason})")
                                    return full_text

                        if finish_reason == "MAX_TOKENS":
                            print(f"⚠️ {model} MAX_TOKENS — skip to next model")
                            break

                        print(f"⚠️ No content, finishReason: {finish_reason}")

                    break

                except requests.exceptions.RequestException as e:
                    last_error = e
                    error_str  = str(e)

                    if any(x in error_str for x in ["Name", "resolve", "connection"]):
                        print(f"🌐 Network error: {error_str[:50]}...")
                        return None

                    if "429" in error_str:
                        self._mark_key_failed(api_key)
                        break

                    if "404" in error_str or "400" in error_str:
                        break

                    print(f"⚠️ {model} attempt {attempt + 1} failed: {str(e)[:50]}")
                    if attempt < 2:
                        time_module.sleep(2)
                    continue

        print(f"❌ All models failed: {str(last_error)[:50] if last_error else 'unknown'}")
        return None
    
    def generate_response(
        self,
        query: str,
        context: str = "",
        chat_history: list = None,
        max_new_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        user_preferences: list = None,
        is_first_message: bool = True,
    ) -> str:
        """Generate response using Gemini API with intelligent fallback"""
        
        intent = self._classify_intent(query)
        print(f"🎯 Intent: {intent} | Query: {query[:50]}...")
        
        # Handle different intents
        if intent == 'greeting':
            return self._get_greeting_response()
        
        if intent == 'out_of_scope':
            return self._get_out_of_scope_response(query)
        
        has_context = context and len(context.strip()) > 100
        
        # For general queries without tourism context, be honest
        if intent == 'general' and not has_context:
            return self._get_out_of_scope_response(query)
        
        # Check if context is actually relevant
        if has_context and not self._is_query_relevant_to_context(query, context):
            print("⚠️ Retrieved context not relevant to query")
            if intent == 'tourism':
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
                'alam': 'Wisata Alam (gunung, danau, air terjun)',
                'budaya': 'Wisata Budaya (museum, desa adat, tradisi Batak)',
                'kuliner': 'Kuliner khas Batak',
                'sejarah': 'Wisata Sejarah (situs, monumen)',
                'religi': 'Wisata Religi',
                'air': 'Wisata Air (pantai, kolam, water sport)',
                'petualangan': 'Petualangan (hiking, camping, rafting)',
                'fotografi': 'Spot Foto Instagram',
            }
            if user_preferences:
                labels = [CATEGORY_LABELS.get(p, p) for p in user_preferences]
                pref_hint = f"\n\nCATATAN PREFERENSI PENGGUNA: Pengguna ini menyukai {', '.join(labels)}. Jika relevan, prioritaskan rekomendasi sesuai minat tersebut.\n"

            greeting_rule = (
                "10. Ini adalah pesan PERTAMA dalam percakapan — boleh membuka jawaban dengan sapaan singkat yang hangat."
                if is_first_message else
                "10. Ini adalah lanjutan percakapan — JANGAN memulai jawaban dengan sapaan (Halo, Horas, Selamat datang, dsb). Langsung jawab pertanyaan."
            )

            # Format chat history for context-aware multi-turn conversation
            history_section = ""
            if chat_history and len(chat_history) > 0:
                history_lines = []
                for msg in chat_history[-8:]:  # Last 8 messages (4 turns)
                    role = "Pengguna" if msg.get('role') == 'user' else "Asisten"
                    content = msg.get('content', '')[:300]
                    history_lines.append(f"  {role}: {content}")
                history_section = (
                    "\n\nKONTEKS PERCAKAPAN SEBELUMNYA:\n"
                    + "\n".join(history_lines)
                    + "\n\n(Gunakan konteks percakapan di atas untuk memahami maksud pengguna "
                    "jika pertanyaan baru merujuk ke topik sebelumnya, misalnya 'tempat itu', "
                    "'yang tadi', 'saingannya', 'alternatif lain', dll.)\n"
                )

            prompt = f"""Kamu adalah asisten wisata Danau Toba yang ramah, informatif, dan detail.

INSTRUKSI PENTING:
1. Jawab berdasarkan INFORMASI DOKUMEN di bawah dengan LENGKAP dan DETAIL
2. Untuk setiap tempat wisata/hotel/rumah makan, SELALU sebutkan NAMA LENGKAPNYA sebagaimana tertulis di dokumen
3. Gunakan format yang rapi dengan emoji dan bullet points
4. Berikan minimal 3-5 rekomendasi jika tersedia dalam dokumen
5. Jika informasi tidak ada dalam dokumen, katakan "Maaf, informasi tersebut belum tersedia"
6. JANGAN mengarang informasi yang tidak ada dalam dokumen
7. JANGAN menyebutkan nomor halaman, nomor chunk, atau referensi teknis dokumen
8. JANGAN pernah menulis teks placeholder seperti "(Tidak disebutkan namanya...)", "(Nama tidak tersedia)", atau sejenisnya — gunakan nama yang tertulis di dokumen apa adanya
9. Akhiri dengan ajakan untuk bertanya lebih lanjut
10. Jika pengguna menanyakan SATU tempat spesifik, fokus jawab tempat itu saja, bukan daftar rekomendasi umum.
11. Jika dokumen memuat field eksplisit seperti "Menu", "Harga", "Jam Operasional", atau "Alamat", salin fakta tersebut dengan setia dari dokumen.
12. Jika dokumen "Data Terstruktur: Lokasi Database" tersedia dalam konteks, WAJIB masukkan SEMUA tempat yang tercantum di sana ke dalam jawaban — jangan melewatkan satu pun.
13. Untuk pertanyaan "apa saja" atau "daftar", tampilkan SELURUH tempat yang ada dalam konteks, bukan hanya sebagian.
{greeting_rule}
{pref_hint}{history_section}
INFORMASI DOKUMEN:
{context[:6000]}

PERTANYAAN: {query}

JAWABAN (hanya berdasarkan dokumen di atas):"""
            
            # Call Gemini — fallback model otomatis via _build_models_to_try
            result = self._call_gemini_api(prompt, max_tokens=max_new_tokens, temperature=temperature)

            # Jika semua model gagal, fallback ke general knowledge (1x saja)
            if result is None or len(result) < 10:
                print("🔄 API failed — fallback general knowledge (1x only)...")
                answer = self._ask_gemini_general(query)
                return answer or "Maaf, saya sedang tidak bisa memproses pertanyaan Anda. Silakan coba lagi. 🙏"

            return result
        else:
            # No context available — keep tourism/business queries grounded to docs.
            if intent == 'tourism':
                return self._build_document_unavailable_response(query)

            # No context available — try LLM general knowledge
            general_answer = self._ask_gemini_general(query)
            if general_answer:
                return general_answer
            return "Maaf, saya sedang tidak bisa memproses pertanyaan Anda. Silakan coba lagi. 🙏"
    
    def __call__(self, prompt: str, max_new_tokens: int = 2048, **kwargs) -> str:
        return self.generate_response(query=prompt, max_new_tokens=max_new_tokens, **kwargs)
