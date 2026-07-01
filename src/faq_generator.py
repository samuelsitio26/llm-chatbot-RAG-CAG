"""
FAQ Generator for CAG System
Implements "FAQ for CAG" component from flowchart
Generates Frequently Asked Questions to pre-populate cache

FAQ Schema (per entry):
  question          : str        – pertanyaan
  answer            : str        – jawaban ground-truth (opsional, diisi saat ada)
  category          : str        – kategori wisata
  keywords          : List[str]  – kata kunci
  priority          : str        – "high" | "medium" | "low"
  auto_promoted     : bool       – True jika dipromosi dari cache
  promoted_at       : str        – ISO timestamp promosi
"""

import os
import json
from typing import List, Dict


class FAQGenerator:
    """
    Generate and manage FAQ dataset for CAG cache pre-population
    Based on flowchart: "FAQ for CAG"
    """
    
    def __init__(self, faq_file: str = None):
        if faq_file is None:
            faq_file = os.path.normpath(os.path.join(
                os.path.dirname(__file__),
                "..",
                "database",
                "FAQ",          # ← folder name yang benar
                "faq_tourism.json"
            ))
        
        self.faq_file = faq_file
        self.faqs = self.load_faqs()
    
    def load_faqs(self) -> List[Dict]:
        """Load existing FAQs from file"""
        if os.path.exists(self.faq_file):
            with open(self.faq_file, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        else:
            # Return default FAQs if file doesn't exist
            return self.get_default_faqs()
    
    def get_default_faqs(self) -> List[Dict]:
        """
        Default FAQs for tourism domain
        These are common questions that should be cached
        """
        return [
            {
                "category": "beach",
                "question": "Rekomendasi pantai untuk honeymoon budget 10 juta",
                "keywords": ["pantai", "honeymoon", "romantis", "10 juta"],
                "priority": "high"
            },
            {
                "category": "beach",
                "question": "Pantai terbaik untuk snorkeling di Indonesia",
                "keywords": ["pantai", "snorkeling", "diving"],
                "priority": "high"
            },
            {
                "category": "mountain",
                "question": "Tempat wisata gunung untuk hiking pemula",
                "keywords": ["gunung", "hiking", "pemula", "trekking"],
                "priority": "high"
            },
            {
                "category": "mountain",
                "question": "Destinasi gunung dengan pemandangan sunrise terbaik",
                "keywords": ["gunung", "sunrise", "pemandangan"],
                "priority": "medium"
            },
            {
                "category": "family",
                "question": "Destinasi wisata keluarga di Jawa Barat budget 5 juta",
                "keywords": ["keluarga", "jawa barat", "5 juta", "anak"],
                "priority": "high"
            },
            {
                "category": "family",
                "question": "Tempat wisata yang cocok untuk anak-anak",
                "keywords": ["anak", "keluarga", "playground", "kids"],
                "priority": "high"
            },
            {
                "category": "culture",
                "question": "Wisata budaya dan sejarah di Yogyakarta",
                "keywords": ["budaya", "sejarah", "yogyakarta", "candi"],
                "priority": "medium"
            },
            {
                "category": "culture",
                "question": "Museum dan heritage site yang wajib dikunjungi",
                "keywords": ["museum", "heritage", "sejarah"],
                "priority": "low"
            },
            {
                "category": "culinary",
                "question": "Kuliner khas yang wajib dicoba di Bali",
                "keywords": ["kuliner", "makanan", "bali", "restaurant"],
                "priority": "high"
            },
            {
                "category": "culinary",
                "question": "Rekomendasi rumah makan tradisional terbaik",
                "keywords": ["rumah makan", "tradisional", "authentic"],
                "priority": "medium"
            },
            {
                "category": "accommodation",
                "question": "Hotel budget friendly dekat pantai",
                "keywords": ["hotel", "budget", "pantai", "akomodasi"],
                "priority": "high"
            },
            {
                "category": "accommodation",
                "question": "Villa untuk liburan keluarga dengan kolam renang",
                "keywords": ["villa", "keluarga", "kolam renang", "private"],
                "priority": "medium"
            },
            {
                "category": "adventure",
                "question": "Destinasi wisata petualangan dan extreme sports",
                "keywords": ["adventure", "extreme", "rafting", "paragliding"],
                "priority": "medium"
            },
            {
                "category": "nature",
                "question": "Air terjun tersembunyi yang belum banyak dikunjungi",
                "keywords": ["air terjun", "hidden gem", "nature"],
                "priority": "low"
            },
            {
                "category": "urban",
                "question": "Tempat wisata menarik di Jakarta untuk weekend",
                "keywords": ["jakarta", "urban", "weekend", "kota"],
                "priority": "high"
            },
            {
                "category": "general",
                "question": "Kapan waktu terbaik untuk berkunjung?",
                "keywords": ["waktu terbaik", "musim", "cuaca"],
                "priority": "high"
            },
            {
                "category": "general",
                "question": "Bagaimana cara menuju lokasi wisata?",
                "keywords": ["transportasi", "cara menuju", "akses"],
                "priority": "high"
            },
            {
                "category": "general",
                "question": "Apa saja yang perlu dibawa saat berkunjung?",
                "keywords": ["perlengkapan", "barang bawaan", "checklist"],
                "priority": "medium"
            },
            {
                "category": "budget",
                "question": "Estimasi biaya liburan ke Bali untuk 4 orang",
                "keywords": ["biaya", "budget", "bali", "estimasi"],
                "priority": "high"
            },
            {
                "category": "budget",
                "question": "Tips hemat untuk liburan dengan budget terbatas",
                "keywords": ["hemat", "budget", "tips", "murah"],
                "priority": "medium"
            }
        ]
    
    def save_faqs(self):
        """Save FAQs to file"""
        os.makedirs(os.path.dirname(self.faq_file), exist_ok=True)
        with open(self.faq_file, 'w', encoding='utf-8') as f:
            json.dump(self.faqs, indent=2, ensure_ascii=False, fp=f)
        print(f"✅ Saved {len(self.faqs)} FAQs to {self.faq_file}")
    
    def get_high_priority_faqs(self) -> List[Dict]:
        """Get high priority FAQs for cache pre-population"""
        return [faq for faq in self.faqs if faq.get("priority") == "high"]
    
    def get_faqs_by_category(self, category: str) -> List[Dict]:
        """Get FAQs for specific category"""
        return [faq for faq in self.faqs if faq.get("category") == category]
    
    def add_faq(self, question: str, category: str, keywords: List[str], priority: str = "medium"):
        """Add new FAQ"""
        self.faqs.append({
            "category": category,
            "question": question,
            "keywords": keywords,
            "priority": priority
        })
        self.save_faqs()
    
    def get_all_questions(self) -> List[str]:
        """Get all FAQ questions as list"""
        return [faq["question"] for faq in self.faqs]

    # ============================================================
    # METHODS BARU: promosi dari cache & pre-populate dengan jawaban
    # ============================================================

    def add_promoted_entry(
        self,
        query: str,
        answer: str,
        category: str = "general",
        keywords: List[str] = None,
        access_count: int = 0,
    ) -> bool:
        """
        Tambahkan entry baru ke FAQ yang dipromosi secara otomatis dari cache
        (access_count >= 5 → sudah teruji sering ditanya).

        Returns:
            True  jika berhasil ditambahkan
            False jika pertanyaan sudah ada di FAQ
        """
        from datetime import datetime

        # Cek duplikat
        existing = {f["question"].lower().strip() for f in self.faqs}
        if query.lower().strip() in existing:
            return False

        self.faqs.append({
            "category":                  category,
            "question":                  query,
            "answer":                    answer[:1000],  # batas 1000 char
            "keywords":                  keywords or [],
            "priority":                  "high",         # populer → high priority
            "auto_promoted":             True,
            "promoted_at":               datetime.now().isoformat(),
            "promoted_from_cache_count": access_count,
        })
        self.save_faqs()
        return True

    def pre_populate_cache_from_answers(self, cache_manager) -> Dict:
        """
        Isi KV cache langsung dari pasangan Q+A di FAQ tanpa memanggil LLM.
        Hanya memproses FAQ yang sudah punya field 'answer'.

        Args:
            cache_manager: instance KVCacheManager

        Returns:
            {'added': int, 'skipped': int}
        """
        return cache_manager.pre_populate_from_faq(self.faqs)

    def get_faqs_with_answers(self) -> List[Dict]:
        """Kembalikan hanya FAQ yang sudah memiliki field 'answer'."""
        return [f for f in self.faqs if f.get("answer", "").strip()]

    def get_faqs_without_answers(self) -> List[Dict]:
        """Kembalikan FAQ yang belum memiliki jawaban (perlu diisi / di-generate)."""
        return [f for f in self.faqs if not f.get("answer", "").strip()]

    def export_as_eval_dataset(self, max_items: int = None) -> List[Dict]:
        """
        Export FAQ sebagai dataset evaluasi RAG/CAG.
        Hanya FAQ yang memiliki 'answer' yang bisa menjadi ground truth.

        Returns:
            List of { 'q': str, 'gt': str, 'kw': List[str] }
        """
        faqs_with_answers = self.get_faqs_with_answers()
        subset = faqs_with_answers[:max_items] if max_items else faqs_with_answers
        return [
            {
                "q":  f["question"],
                "gt": f["answer"],
                "kw": f.get("keywords", []),
            }
            for f in subset
        ]

    def populate_cag_cache(self, cag_system, verbose: bool = True):
        """
        Pre-populate CAG cache with FAQ answers
        This implements the "FAQ for CAG" → "CAG Cache Generation" flow
        
        Args:
            cag_system: HybridSystem instance
            verbose: Print progress
        """
        if verbose:
            print("=" * 60)
            print("🔥 Pre-populating CAG Cache with FAQs")
            print("=" * 60)
        
        # Get high priority FAQs first
        high_priority = self.get_high_priority_faqs()
        
        if verbose:
            print(f"📝 Processing {len(high_priority)} high-priority FAQs...\n")
        
        success_count = 0
        for i, faq in enumerate(high_priority, 1):
            question = faq["question"]
            
            if verbose:
                print(f"{i}. {question}")
            
            try:
                # Get response (this will cache it)
                result = cag_system.get_response(
                    query=question,
                    k=5,
                    use_cache=True,
                    max_new_tokens=512
                )
                
                if result["source"] != "error":
                    success_count += 1
                    if verbose:
                        print(f"   ✅ Cached (Source: {result['source']})")
                else:
                    if verbose:
                        print(f"   ❌ Failed")
                
            except Exception as e:
                if verbose:
                    print(f"   ❌ Error: {e}")
            
            if verbose:
                print()
        
        if verbose:
            print("=" * 60)
            print(f"✅ Cache pre-population complete!")
            print(f"   Success: {success_count}/{len(high_priority)}")
            print("=" * 60)


if __name__ == "__main__":
    # Generate default FAQ file
    faq_gen = FAQGenerator()
    faq_gen.save_faqs()
    
    print(f"Generated {len(faq_gen.faqs)} default FAQs")
    print(f"High priority: {len(faq_gen.get_high_priority_faqs())}")
    print(f"\nSaved to: {faq_gen.faq_file}")
