"""
Utility to clear ALL invalid cache entries
Run this to clean up wrong cached responses
"""

import json
import os

def clear_invalid_cache():
    """Remove invalid cached responses"""
    cache_file = "../database/kv_cache/cache_index.json"
    cache_file = os.path.normpath(
        os.path.join(os.path.dirname(__file__), cache_file)
    )
    
    if not os.path.exists(cache_file):
        print("❌ Cache file not found")
        return
    
    # Load cache
    with open(cache_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cache = data.get('cache', {})
    access_count = data.get('access_count', {})
    
    original_count = len(cache)
    
    # Invalid response indicators
    invalid_indicators = [
        "homestay tidak tersedia",
        "tidak tersedia dalam database",
        "Data tidak mention",
        "saya tidak dapat menjawab",
        "saya memerlukan dokumen",
        "tidak dapat memberikan",
        "Halo is a term",
        "space opera",
        "science fiction",
        "video game",
        "Halo (1995)",
        "Guardians of the Galaxy",
        "Master Chief",
        "Xbox",
        "Locak Hotel Safari",
        "bisa di tambah sesinya",
        "longweekend",
        "informasi tentang kategori",
        "I cannot",
        "I don't have",
        # API Error responses - should never be cached
        "gemini api sedang sibuk",
        "rate limit",
        "silakan tunggu",
        "silakan coba lagi",
        "terjadi kesalahan",
        "429 client error",
        "too many requests",
        "name resolution error",
        "failed to resolve",
        "rate limit exceeded",
    ]
    
    # Find invalid entries
    to_remove = []
    for query_hash, item in cache.items():
        response = item.get('response', '')
        query = item.get('query', '')
        
        # Check if response is too short
        if len(response.strip()) < 20:
            to_remove.append((query_hash, query, "Response too short"))
            continue
        
        # Check if response contains invalid indicators
        response_lower = response.lower()
        for indicator in invalid_indicators:
            if indicator.lower() in response_lower:
                to_remove.append((query_hash, query, f"Contains: {indicator}"))
                break
    
    if not to_remove:
        print("✅ No invalid cache entries found")
        print(f"📊 Total cache entries: {len(cache)}")
        return
    
    # Remove invalid entries
    print(f"\n🗑️  Found {len(to_remove)} invalid cache entries:\n")
    for query_hash, query, reason in to_remove:
        print(f"   ❌ Query: {query[:60]}...")
        print(f"      Reason: {reason}\n")
        del cache[query_hash]
        if query_hash in access_count:
            del access_count[query_hash]
    
    # Save cleaned cache
    data['cache'] = cache
    data['access_count'] = access_count
    
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Removed {len(to_remove)} invalid cache entries")
    print(f"📊 Original: {original_count} | Remaining: {len(cache)}")

if __name__ == "__main__":
    print("=" * 60)
    print("🧹 CAG Cache Cleanup Utility")
    print("=" * 60)
    clear_invalid_cache()
    print("\n💡 Tip: Restart the API server after cleaning cache")
