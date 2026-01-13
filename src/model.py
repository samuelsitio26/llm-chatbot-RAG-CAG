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
    
    def __init__(self, model_name: str = "gemini-2.0-flash"):
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
        self.min_request_interval = 4  # Minimum 4 seconds between requests (15 RPM = 1 per 4 sec)
        
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
        
        # Strong tourism keywords that definitely indicate Toba tourism query
        strong_tourism_keywords = [
            'wisata', 'pantai', 'danau', 'hotel', 'penginapan', 'homestay',
            'villa', 'resort', 'toba', 'samosir', 'balige', 'parapat', 'tomok', 
            'tuktuk', 'sipiso', 'kuliner', 'batak', 'ulos', 'air terjun'
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
            'jalan-jalan', 'view', 'pemandangan', 'gunung'
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
        """Answer general questions then redirect to tourism"""
        import re
        query_lower = query.lower().strip()
        
        # Math calculations
        calc_match = re.search(r'(\d+)\s*([\+\-\*\/x])\s*(\d+)', query)
        if calc_match:
            try:
                num1 = int(calc_match.group(1))
                op = calc_match.group(2)
                num2 = int(calc_match.group(3))
                
                if op == '+':
                    result = num1 + num2
                    answer = f"**{num1} + {num2} = {result}** ✓"
                elif op == '-':
                    result = num1 - num2
                    answer = f"**{num1} - {num2} = {result}** ✓"
                elif op in ['*', 'x']:
                    result = num1 * num2
                    answer = f"**{num1} × {num2} = {result}** ✓"
                elif op == '/':
                    if num2 != 0:
                        result = num1 / num2
                        if result == int(result):
                            answer = f"**{num1} ÷ {num2} = {int(result)}** ✓"
                        else:
                            answer = f"**{num1} ÷ {num2} = {result:.2f}** ✓"
                    else:
                        answer = "Tidak bisa membagi dengan nol! 🚫"
                
                return f"""{answer}

---
🏔️ *Saya juga adalah asisten **Wisata Danau Toba**!*

Ada yang ingin ditanyakan tentang wisata Danau Toba? 😊"""
            except:
                pass
        
        # Questions about the bot
        if any(kw in query_lower for kw in ['siapa kamu', 'siapa anda', 'kamu siapa']):
            return """Halo! 👋 Saya adalah **Asisten Wisata Danau Toba**!

Saya bisa membantu Anda dengan:
• 🏖️ Tempat wisata di Danau Toba
• 🏨 Hotel & penginapan
• 🍽️ Kuliner khas Batak
• 🎭 Budaya & tradisi Batak

Ada yang ingin ditanyakan? 😊"""
        
        # Thank you
        if any(kw in query_lower for kw in ['terima kasih', 'makasih', 'thanks', 'thank you']):
            return "Sama-sama! 😊 Senang bisa membantu. Jika ada pertanyaan lain tentang Danau Toba, silakan tanyakan!"
        
        # How are you
        if any(kw in query_lower for kw in ['apa kabar', 'kabar']):
            return "Saya baik-baik saja! 😊 Terima kasih sudah bertanya. Ada yang bisa saya bantu tentang wisata Danau Toba?"
        
        # Date/time
        if any(kw in query_lower for kw in ['tanggal', 'hari ini', 'jam']):
            from datetime import datetime
            now = datetime.now()
            return f"""Sekarang tanggal **{now.strftime('%d %B %Y')}**, pukul **{now.strftime('%H:%M')}** WIB.

---
🏔️ *Ngomong-ngomong, mau tanya tentang wisata Danau Toba?* 😊"""
        
        # Default: Try Gemini API
        try:
            gemini_answer = self._ask_gemini_simple(query)
            if gemini_answer:
                return f"""{gemini_answer}

---
🏔️ *Saya juga adalah asisten **Wisata Danau Toba**!*

Ada yang ingin ditanyakan tentang wisata Danau Toba? 😊"""
        except:
            pass
        
        # Fallback
        return f"""Saya kurang yakin dengan jawaban untuk pertanyaan itu 😊

Saya adalah asisten khusus **Wisata Danau Toba** 🏔️

💡 **Saya bisa membantu Anda dengan:**
• 🏖️ Tempat wisata di Toba
• 🏨 Hotel & penginapan
• 🍽️ Kuliner khas Batak
• 🎭 Budaya Batak

Mau tanya tentang Danau Toba? 😊"""
    
    def _ask_gemini_simple(self, query: str) -> str:
        """Ask Gemini for simple questions"""
        api_key = self._get_available_api_key()
        if not api_key:
            return None
        
        # Rate limiting
        current_time = time_module.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            time_module.sleep(wait_time)
        self.last_request_time = time_module.time()
        
        prompt = f"Jawab singkat dalam 1-2 kalimat: {query}"
        
        try:
            url = f"{self.base_url}/{self.model_name}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 100}
            }
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "candidates" in data and len(data["candidates"]) > 0:
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except:
            pass
        return None
    
    def _get_out_of_scope_response(self, query: str) -> str:
        """Response for questions outside our knowledge domain"""
        return f"""Maaf, saya adalah asisten khusus **Wisata Danau Toba** 🏔️

Pertanyaan Anda tentang **"{query[:50]}..."** berada di luar cakupan pengetahuan saya.

🎯 **Saya dapat membantu Anda dengan:**
• Rekomendasi tempat wisata di Danau Toba
• Informasi penginapan (hotel, homestay, villa)
• Kuliner khas Batak
• Budaya dan adat istiadat Batak
• Tips perjalanan ke Toba

Silakan ajukan pertanyaan seputar wisata Danau Toba! 😊"""
    
    def _get_greeting_response(self) -> str:
        """Return a friendly greeting response"""
        import random
        greetings = [
            "Horas! 👋 Selamat datang di Sistem Rekomendasi Wisata Danau Toba!\n\nSaya siap membantu Anda menemukan destinasi wisata terbaik. Silakan tanyakan tentang:\n\n🏖️ **Tempat Wisata** - Pantai, air terjun, pemandangan\n🏨 **Penginapan** - Hotel, homestay, villa\n🍽️ **Kuliner** - Makanan khas Batak\n🎭 **Budaya** - Adat istiadat, museum\n\nApa yang ingin Anda ketahui?",
            "Halo! 😊 Selamat datang di Asisten Wisata Danau Toba!\n\nSaya di sini untuk membantu Anda merencanakan perjalanan wisata ke Danau Toba. Mau tanya tentang apa?\n\n• Rekomendasi tempat wisata\n• Penginapan sesuai budget\n• Kuliner khas Batak\n• Tips perjalanan",
            "Hai! Horas! 🏔️\n\nSelamat datang di Sistem Rekomendasi Wisata Danau Toba. Saya siap membantu Anda menjelajahi keindahan Tanah Batak!"
        ]
        return random.choice(greetings)
    
    def _get_fallback_response(self, query: str) -> str:
        """Return fallback response when no context available"""
        query_lower = query.lower()
        
        if any(kw in query_lower for kw in ['homestay', 'penginapan', 'hotel', 'villa']):
            topic = "penginapan"
        elif any(kw in query_lower for kw in ['kuliner', 'makanan', 'makan', 'resto']):
            topic = "kuliner"
        elif any(kw in query_lower for kw in ['pantai', 'beach', 'perairan', 'air']):
            topic = "pantai"
        elif any(kw in query_lower for kw in ['gunung', 'bukit', 'hiking']):
            topic = "wisata alam"
        else:
            topic = "wisata"
        
        return f"""Maaf, informasi spesifik tentang **{topic}** yang Anda tanyakan belum tersedia dalam database saya.

🔍 **Coba tanyakan:**
• Tempat wisata di Samosir
• Kuliner khas Batak
• Penginapan di Parapat
• Air terjun Sipiso-piso

Silakan ajukan pertanyaan lain! 😊"""
    
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
        # Move to next key
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
    
    def _extract_info_from_context(self, query: str, context: str) -> str:
        """
        Extract relevant information from context without using LLM.
        This is the fallback when API fails.
        Now includes relevance checking to avoid hallucination.
        """
        if not context or len(context.strip()) < 50:
            return None
        
        # First check if context is actually relevant to query
        if not self._is_query_relevant_to_context(query, context):
            print("⚠️ Context not relevant to query, skipping fallback extraction")
            return None
        
        query_lower = query.lower()
        
        # Determine what type of info user wants
        is_asking_location = any(kw in query_lower for kw in ['dimana', 'alamat', 'lokasi'])
        is_asking_price = any(kw in query_lower for kw in ['harga', 'biaya', 'budget', 'murah', 'mahal', 'tarif'])
        is_asking_food = any(kw in query_lower for kw in ['kuliner', 'makanan', 'makan', 'resto', 'warung', 'cafe', 'enak'])
        is_asking_stay = any(kw in query_lower for kw in ['hotel', 'penginapan', 'homestay', 'villa', 'resort', 'menginap'])
        is_asking_tourism = any(kw in query_lower for kw in ['wisata', 'pantai', 'air', 'perairan', 'danau', 'gunung', 'terjun', 'tempat'])
        
        # Extract specific keywords from query to match
        query_keywords = self._extract_query_keywords(query)
        
        # Parse context into structured entries
        entries = self._parse_context_entries(context)
        
        # Filter entries by relevance to query
        relevant_entries = []
        for entry in entries:
            if self._entry_matches_query(entry, query_keywords, query_lower):
                relevant_entries.append(entry)
        
        # If no relevant entries found, return None
        if not relevant_entries:
            print("⚠️ No relevant entries found in context")
            return None
        
        # Build response
        response_parts = []
        
        # Header based on query type
        if is_asking_food:
            response_parts.append("🍽️ **Rekomendasi Kuliner:**\n")
        elif is_asking_stay:
            response_parts.append("🏨 **Rekomendasi Penginapan:**\n")
        elif is_asking_tourism:
            response_parts.append("🏖️ **Rekomendasi Wisata:**\n")
        else:
            response_parts.append("📍 **Informasi yang ditemukan:**\n")
        
        # Add relevant entries
        for i, entry in enumerate(relevant_entries[:5], 1):
            entry_text = []
            
            if entry.get('name'):
                entry_text.append(f"\n**{i}. {entry['name']}**")
            elif entry.get('description'):
                entry_text.append(f"\n**{i}.** {entry['description'][:150]}")
            
            if entry.get('description') and entry.get('name'):
                entry_text.append(f"\n   {entry['description'][:200]}")
            
            if entry.get('location'):
                entry_text.append(f"\n   📍 Lokasi: {entry['location']}")
            if entry.get('address'):
                entry_text.append(f"\n   📍 Alamat: {entry['address'][:100]}")
            if entry.get('price') and is_asking_price:
                entry_text.append(f"\n   💰 Harga: {entry['price']}")
            if entry.get('rating'):
                entry_text.append(f"\n   ⭐ {entry['rating']}")
            if entry.get('category'):
                entry_text.append(f"\n   🏷️ Kategori: {entry['category']}")
            
            if entry_text:
                response_parts.extend(entry_text)
        
        if len(response_parts) <= 1:
            return None
        
        response_parts.append("\n\n💡 *Informasi dari dokumen wisata Danau Toba*")
        return ''.join(response_parts)
    
    def _extract_query_keywords(self, query: str) -> set:
        """Extract meaningful keywords from query"""
        query_lower = query.lower()
        words = re.findall(r'\b\w+\b', query_lower)
        
        stopwords = {'di', 'ke', 'dari', 'yang', 'untuk', 'dan', 'atau', 'dengan', 
                     'ini', 'itu', 'ada', 'tidak', 'bisa', 'apa', 'mana', 'ter', 'paling',
                     'saya', 'kamu', 'tolong', 'cari', 'kan', 'dong', 'ya', 'nih'}
        
        keywords = set()
        for word in words:
            if len(word) > 2 and word not in stopwords:
                keywords.add(word)
        
        return keywords
    
    def _parse_context_entries(self, context: str) -> list:
        """Parse context into structured entries"""
        entries = []
        current_entry = {}
        
        lines = context.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_entry:
                    entries.append(current_entry)
                    current_entry = {}
                continue
            
            # Start new entry on [Sumber X]
            if line.startswith('[Sumber'):
                if current_entry:
                    entries.append(current_entry)
                current_entry = {'raw': ''}
                continue
            
            # Parse structured fields
            if ':' in line:
                key_part = line.split(':')[0].strip().lower()
                value_part = line.split(':', 1)[1].strip()
                
                if 'deskripsi' in key_part:
                    current_entry['description'] = value_part
                elif 'alamat' in key_part:
                    current_entry['address'] = value_part
                elif 'lokasi' in key_part:
                    current_entry['location'] = value_part
                elif 'harga' in key_part or 'biaya' in key_part:
                    current_entry['price'] = value_part
                elif 'kategori' in key_part:
                    current_entry['category'] = value_part
                elif 'rating' in key_part or 'ulasan' in key_part:
                    current_entry['rating'] = value_part
            
            # Try to extract name from first meaningful line
            if not current_entry.get('name') and len(line) > 3 and len(line) < 100:
                if not any(skip in line.lower() for skip in ['long', 'lat', 'longitude', 'kategori:', 'deskripsi:', 'alamat:']):
                    # Check if it looks like a name (capitalized, not too long)
                    if line[0].isupper() or any(kw in line.lower() for kw in ['pantai', 'air terjun', 'hotel', 'restoran', 'cafe']):
                        current_entry['name'] = line
            
            if 'raw' in current_entry:
                current_entry['raw'] += line + '\n'
        
        if current_entry:
            entries.append(current_entry)
        
        return entries
    
    def _entry_matches_query(self, entry: dict, query_keywords: set, query_lower: str) -> bool:
        """Check if an entry is relevant to the query"""
        if not entry:
            return False
        
        # Combine all entry text
        entry_text = ' '.join([
            str(entry.get('name', '')),
            str(entry.get('description', '')),
            str(entry.get('category', '')),
            str(entry.get('raw', ''))
        ]).lower()
        
        # Check if entry matches query intent
        # Food query should match food-related entries
        food_keywords = ['resto', 'restoran', 'warung', 'cafe', 'kuliner', 'makanan', 'makan', 'masakan']
        stay_keywords = ['hotel', 'homestay', 'penginapan', 'villa', 'resort', 'kamar']
        tourism_keywords = ['pantai', 'wisata', 'air terjun', 'danau', 'gunung', 'museum', 'taman']
        health_keywords = ['rumah sakit', 'puskesmas', 'apotek', 'klinik', 'dokter']
        
        is_food_query = any(kw in query_lower for kw in ['makan', 'kuliner', 'resto', 'enak', 'makanan'])
        is_stay_query = any(kw in query_lower for kw in ['hotel', 'penginapan', 'menginap', 'homestay'])
        is_tourism_query = any(kw in query_lower for kw in ['wisata', 'pantai', 'tempat', 'air', 'jalan'])
        
        is_food_entry = any(kw in entry_text for kw in food_keywords)
        is_stay_entry = any(kw in entry_text for kw in stay_keywords)
        is_tourism_entry = any(kw in entry_text for kw in tourism_keywords)
        is_health_entry = any(kw in entry_text for kw in health_keywords)
        
        # Don't show health facilities for tourism/food queries
        if is_health_entry and (is_food_query or is_tourism_query or is_stay_query):
            return False
        
        # Match query type with entry type
        if is_food_query and not is_food_entry:
            return False
        if is_stay_query and not is_stay_entry:
            return False
        
        # Check keyword overlap
        keyword_matches = sum(1 for kw in query_keywords if kw in entry_text)
        
        return keyword_matches >= 1 or (is_tourism_query and is_tourism_entry)
    
    def _format_raw_context(self, query: str, context: str) -> str:
        """Format raw context into a readable response"""
        # Clean up the context
        lines = [l.strip() for l in context.split('\n') if l.strip() and len(l.strip()) > 10]
        
        # Remove metadata lines
        clean_lines = []
        for line in lines:
            if any(skip in line for skip in ['Long & Lat', 'Longitude', 'Lattitude', '[Sumber']):
                continue
            clean_lines.append(line)
        
        if not clean_lines:
            return None
        
        # Build response
        response = "📍 **Informasi dari Dokumen Wisata Toba:**\n\n"
        
        # Take first few meaningful lines
        added = 0
        for line in clean_lines[:10]:
            if added >= 5:
                break
            if len(line) > 20:
                response += f"• {line[:300]}\n\n"
                added += 1
        
        if added > 0:
            response += "\n💡 *Untuk informasi lebih detail, silakan tanyakan spesifik tentang tempat tertentu.*"
            return response
        
        return None

    def _call_gemini_api(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        """Call Gemini API via REST with retry logic for rate limits"""
        
        api_key = self._get_available_api_key()
        if not api_key:
            print("⚠️ No API keys available")
            return None  # Return None to trigger fallback
        
        # Rate limiting: wait if needed
        current_time = time_module.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            print(f"⏳ Rate limit protection: waiting {wait_time:.1f}s...")
            time_module.sleep(wait_time)
        
        self.last_request_time = time_module.time()
        
        # Models to try (correct names for v1beta API)
        models_to_try = [
            self.model_name,
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest", 
            "gemini-pro"
        ]
        
        headers = {"Content-Type": "application/json"}
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": 0.9,
                "topK": 40
            }
        }
        
        last_error = None
        
        for model in models_to_try:
            url = f"{self.base_url}/{model}:generateContent?key={api_key}"
            
            for attempt in range(3):  # Reduced attempts to fail faster
                try:
                    response = requests.post(url, headers=headers, json=payload, timeout=30)
                    
                    # Handle rate limit (429) - mark key failed and return None for fallback
                    if response.status_code == 429:
                        print(f"⏳ Rate limited on {model}, attempt {attempt + 1}/3")
                        if attempt < 2:
                            time_module.sleep(5)
                            continue
                        else:
                            self._mark_key_failed(api_key)
                            return None  # Trigger fallback
                    
                    # Handle 404 - try next model immediately
                    if response.status_code == 404:
                        print(f"⚠️ Model {model} not found, trying next...")
                        break
                    
                    response.raise_for_status()
                    result = response.json()
                    
                    if "candidates" in result and len(result["candidates"]) > 0:
                        candidate = result["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            parts = candidate["content"]["parts"]
                            if len(parts) > 0 and "text" in parts[0]:
                                print(f"✅ Response from {model}")
                                return parts[0]["text"].strip()
                    
                    return None  # Trigger fallback
                    
                except requests.exceptions.RequestException as e:
                    last_error = e
                    error_str = str(e)
                    
                    # Network/DNS error - return None for fallback immediately
                    if "Name" in error_str or "resolve" in error_str or "connection" in error_str.lower():
                        print(f"🌐 Network error: {error_str[:50]}...")
                        return None
                    
                    # If 429, mark key failed
                    if "429" in error_str:
                        self._mark_key_failed(api_key)
                        return None
                    
                    # If 404, skip to next model
                    if "404" in error_str:
                        break
                    
                    print(f"⚠️ {model} attempt {attempt + 1} failed: {str(e)[:50]}")
                    if attempt < 2:
                        time_module.sleep(2)
                    continue
        
        print(f"❌ All Gemini models failed: {str(last_error)[:50] if last_error else 'unknown'}")
        return None  # Return None to trigger fallback
    
    def generate_response(
        self,
        query: str,
        context: str = "",
        chat_history: list = None,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50
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
            return self._get_fallback_response(query)
        
        if has_context:
            prompt = f"""Kamu adalah asisten wisata Danau Toba yang ramah dan informatif.

INSTRUKSI PENTING:
1. Jawab HANYA berdasarkan INFORMASI DOKUMEN di bawah
2. Jika pertanyaan TIDAK RELEVAN dengan wisata Toba, katakan "Maaf, pertanyaan tersebut di luar cakupan pengetahuan saya tentang wisata Danau Toba"
3. Jika informasi tidak ada dalam dokumen, katakan "Maaf, informasi tersebut belum tersedia dalam database wisata Toba"
4. JANGAN mengarang atau membuat informasi yang tidak ada dalam dokumen
5. Gunakan bahasa Indonesia yang baik dan sopan
6. Berikan jawaban terstruktur dengan bullet points

INFORMASI DOKUMEN:
{context[:4000]}

PERTANYAAN: {query}

JAWABAN (hanya berdasarkan dokumen di atas):"""
            
            # Try Gemini API first
            result = self._call_gemini_api(prompt, max_tokens=max_new_tokens, temperature=temperature)
            
            # If API failed (returned None), use context-based fallback
            if result is None:
                print("🔄 Using context-based fallback...")
                fallback_result = self._extract_info_from_context(query, context)
                if fallback_result:
                    return fallback_result
                # If no relevant info found
                return self._get_fallback_response(query)
            
            # If result is too short, try fallback
            if len(result) < 10:
                fallback_result = self._extract_info_from_context(query, context)
                if fallback_result:
                    return fallback_result
                return self._get_fallback_response(query)
            
            return result
        else:
            return self._get_fallback_response(query)
    
    def __call__(self, prompt: str, max_new_tokens: int = 512, **kwargs) -> str:
        return self.generate_response(query=prompt, max_new_tokens=max_new_tokens, **kwargs)
