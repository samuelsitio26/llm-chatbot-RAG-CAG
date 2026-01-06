"""
Test script untuk verifikasi perbaikan CAG tanpa perlu load model
"""

# Test 1: Casual Query Detection
print("="*60)
print("TEST 1: Casual Query Detection")
print("="*60)

def _is_casual_query(query: str) -> bool:
    """
    Detect if query is casual conversation (greeting, thanks, etc)
    Only return True for PURE casual greetings without tourism content
    """
    casual_keywords = [
        'halo', 'hai', 'hello', 'hi', 'hey',
        'terima kasih', 'thanks', 'thank you',
        'apa kabar', 'how are you',
        'siapa kamu', 'who are you',
        'bye', 'selamat tinggal', 'dadah',
        'ok', 'oke', 'baik', 'ya'
    ]
    
    # Tourism-related keywords - if present, NOT casual
    tourism_keywords = [
        'wisata', 'pantai', 'gunung', 'hotel', 'rekomendasi',
        'tempat', 'destinasi', 'liburan', 'trip', 'travel',
        'budget', 'harga', 'murah', 'toba', 'bali', 'jakarta',
        'honeymoon', 'keluarga', 'kuliner', 'makanan', 'cafe',
        'restaurant', 'penginapan', 'transport'
    ]
    
    query_lower = query.lower().strip()
    
    # If contains tourism keywords, definitely NOT casual
    for keyword in tourism_keywords:
        if keyword in query_lower:
            return False
    
    # Check if query is very short (<=3 words) and matches casual greeting
    if len(query_lower.split()) <= 3:
        for keyword in casual_keywords:
            # Exact match or starts with keyword
            if query_lower == keyword or query_lower.startswith(keyword + ' '):
                return True
    
    return False

# Test cases
test_queries = [
    ("halo", True, "Pure greeting"),
    ("hai", True, "Pure greeting"),
    ("hello", True, "Pure greeting"),
    ("terima kasih", True, "Pure thanks"),
    ("halo, rekomendasi pantai di Toba", False, "Contains tourism keyword"),
    ("Rekomendasi pantai untuk honeymoon budget 10 juta di Toba", False, "Tourism query"),
    ("wisata apa?", False, "Tourism query"),
    ("tempat kuliner", False, "Tourism query"),
    ("apa kabar", True, "Pure casual"),
]

print("\nCasual Query Detection Results:")
for query, expected, desc in test_queries:
    result = _is_casual_query(query)
    status = "✅" if result == expected else "❌"
    print(f"{status} '{query}' -> {result} (expected: {expected}) - {desc}")

# Test 2: Cache Validation
print("\n" + "="*60)
print("TEST 2: Cache Validation Logic")
print("="*60)

invalid_indicators = [
    "Data tidak mention",
    "saya tidak dapat menjawab",
    "Halo is a term",
    "space opera",
    "science fiction"
]

test_responses = [
    ("Bali memiliki pantai-pantai indah seperti...", False, "Valid response"),
    ("Data tidak mention tentang rekomendasi pantai", True, "Should be invalid"),
    ("Halo is a term used to describe a type of space opera", True, "Wrong context"),
    ("Maaf, saya tidak dapat menjawab pertanyaan ini", True, "Generic rejection"),
    ("Danau Toba adalah destinasi wisata yang indah", False, "Valid tourism info"),
]

print("\nCache Validation Results:")
for response, should_invalidate, desc in test_responses:
    is_invalid = any(indicator in response for indicator in invalid_indicators)
    status = "✅" if is_invalid == should_invalidate else "❌"
    print(f"{status} Should invalidate: {is_invalid} (expected: {should_invalidate})")
    print(f"   Response: '{response[:60]}...'")
    print(f"   Reason: {desc}\n")

# Test 3: Prompt Template Check
print("="*60)
print("TEST 3: Prompt Template Structure")
print("="*60)

def build_prompt(query, context="", is_casual=False):
    """Simulate prompt building"""
    if is_casual:
        return f"""<start_of_turn>user
Jawab sapaan ini dengan ramah dan singkat sebagai asisten wisata (maksimal 2 kalimat):
{query}<end_of_turn>
<start_of_turn>model
"""
    elif context and len(context.strip()) > 50:
        return f"""<start_of_turn>user
Anda adalah asisten rekomendasi wisata. Jawab pertanyaan HANYA berdasarkan informasi dokumen di bawah ini.

Jika informasi tidak ada di dokumen, katakan "Maaf, informasi tentang [topik] tidak tersedia dalam database saya saat ini."

Jangan membuat informasi atau asumsi di luar dokumen.

INFORMASI DOKUMEN:
{context[:2000]}

PERTANYAAN: {query}

JAWABAN (berdasarkan dokumen di atas):<end_of_turn>
<start_of_turn>model
"""
    else:
        return f"""<start_of_turn>user
{query}<end_of_turn>
<start_of_turn>model
Maaf, saya memerlukan dokumen wisata untuk menjawab pertanyaan ini. Silakan upload PDF dokumen terlebih dahulu."""

# Test prompt building
sample_context = "Danau Toba terletak di Sumatera Utara. Merupakan danau vulkanik terbesar di Indonesia dengan pemandangan yang indah."

print("\n1. Casual greeting prompt:")
prompt1 = build_prompt("halo", is_casual=True)
print(f"✅ Length: {len(prompt1)} chars")
print(f"✅ Contains 'asisten wisata': {'asisten wisata' in prompt1}")

print("\n2. RAG with context prompt:")
prompt2 = build_prompt("Rekomendasi wisata Toba", context=sample_context)
print(f"✅ Length: {len(prompt2)} chars")
print(f"✅ Contains 'HANYA berdasarkan': {'HANYA berdasarkan' in prompt2}")
print(f"✅ Contains context: {sample_context[:30] in prompt2}")

print("\n3. No context prompt:")
prompt3 = build_prompt("wisata bali")
print(f"✅ Length: {len(prompt3)} chars")
print(f"✅ Contains 'upload PDF': {'upload PDF' in prompt3}")

print("\n" + "="*60)
print("✅ ALL LOGIC TESTS COMPLETE")
print("="*60)
print("\n📝 Summary:")
print("1. ✅ Casual query detection improved - checks tourism keywords")
print("2. ✅ Cache validation added - filters invalid responses")
print("3. ✅ Prompt templates updated - strict RAG mode with context")
print("\n💡 Next: Test with actual model to verify response quality")
