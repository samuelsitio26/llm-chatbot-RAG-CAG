"""
Gemini API Model Wrapper for CAG System
Uses Google Gemini API via REST API (no SDK dependency issues)
"""
import os
import requests
import json
import time as time_module
from dotenv import load_dotenv

load_dotenv()


class GeminiChatModel:
    """
    Wrapper for Google Gemini API using REST API
    No SDK required - uses direct HTTP requests
    """
    
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        self.model_name = model_name
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        print(f"🔍 Initializing Gemini API: {model_name}")
        print(f"✅ Gemini API initialized successfully!")
        print(f"💡 Using model: {model_name}")
    
    def _classify_intent(self, query: str) -> str:
        """Classify user intent: greeting, tourism, or general"""
        query_lower = query.lower().strip()
        
        greeting_words = ['halo', 'hai', 'hello', 'hi', 'hey', 'hei', 'horas', 'selamat']
        greeting_phrases = ['selamat pagi', 'selamat siang', 'selamat sore', 'selamat malam', 'apa kabar']
        
        tourism_keywords = [
            'wisata', 'pantai', 'gunung', 'danau', 'hotel', 'penginapan', 'homestay',
            'villa', 'resort', 'rekomendasi', 'tempat', 'destinasi', 'liburan', 'trip',
            'travel', 'budget', 'harga', 'murah', 'mahal', 'toba', 'samosir', 'balige',
            'parapat', 'tomok', 'tuktuk', 'sipiso', 'honeymoon', 'keluarga', 'kuliner',
            'makanan', 'cafe', 'resto', 'air terjun', 'museum', 'budaya', 'adat', 'ulos'
        ]
        
        for kw in tourism_keywords:
            if kw in query_lower:
                return 'tourism'
        
        words = query_lower.split()
        if len(words) <= 3:
            if any(word in greeting_words for word in words):
                return 'greeting'
            for phrase in greeting_phrases:
                if query_lower.startswith(phrase):
                    return 'greeting'
        
        return 'general'
    
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
        elif any(kw in query_lower for kw in ['pantai', 'beach']):
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
    
    def _call_gemini_api(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        """Call Gemini API via REST with retry logic for rate limits"""
        
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
            url = f"{self.base_url}/{model}:generateContent?key={self.api_key}"
            
            for attempt in range(3):
                try:
                    response = requests.post(url, headers=headers, json=payload, timeout=60)
                    
                    # Handle rate limit (429) - wait and retry
                    if response.status_code == 429:
                        wait_time = (2 ** attempt) * 2
                        print(f"⏳ Rate limited on {model}, waiting {wait_time}s (attempt {attempt + 1}/3)...")
                        time_module.sleep(wait_time)
                        continue
                    
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
                    
                    return self._get_fallback_response("")
                    
                except requests.exceptions.RequestException as e:
                    last_error = e
                    error_str = str(e)
                    
                    # If 404, skip to next model
                    if "404" in error_str:
                        break
                    
                    print(f"⚠️ {model} attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        time_module.sleep(2)
                    continue
        
        print(f"❌ All Gemini models failed: {last_error}")
        return "Maaf, Gemini API sedang sibuk. Silakan coba lagi dalam beberapa detik."
    
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
        """Generate response using Gemini API"""
        
        intent = self._classify_intent(query)
        print(f"🎯 Intent: {intent} | Query: {query[:50]}...")
        
        if intent == 'greeting':
            return self._get_greeting_response()
        
        has_context = context and len(context.strip()) > 100
        
        if has_context:
            prompt = f"""Kamu adalah asisten wisata Danau Toba yang ramah dan informatif.

INSTRUKSI:
1. Jawab berdasarkan INFORMASI DOKUMEN di bawah
2. Jika informasi tidak ada, katakan "Maaf, informasi tersebut belum tersedia"
3. Gunakan bahasa Indonesia yang baik dan sopan
4. Berikan jawaban terstruktur dengan bullet points

INFORMASI DOKUMEN:
{context[:4000]}

PERTANYAAN: {query}

JAWABAN:"""
        else:
            return self._get_fallback_response(query)
        
        result = self._call_gemini_api(prompt, max_tokens=max_new_tokens, temperature=temperature)
        
        if len(result) < 10:
            return self._get_fallback_response(query)
        
        return result
    
    def __call__(self, prompt: str, max_new_tokens: int = 512, **kwargs) -> str:
        return self.generate_response(query=prompt, max_new_tokens=max_new_tokens, **kwargs)
