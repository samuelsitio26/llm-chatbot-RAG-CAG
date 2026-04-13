"""
Decision-Making Agent for Tourism Recommendation
Implements the agent logic from flowchart to provide ranked recommendations
Includes Content-Based Filtering algorithm for structured location scoring.
"""

import re
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class TourismRecommendation:
    """Structured recommendation output"""
    destination: str
    category: str  # Beach, Mountain, Culture, etc.
    budget_range: str
    score: float
    reason: str
    facilities: List[str]
    best_time: str


class DecisionMakingAgent:
    """
    Decision-making agent that analyzes user query and provides ranked recommendations
    Based on flowchart: "Building the Decision Making Agent"
    """
    
    def __init__(self):
        # Budget ranges in IDR
        self.budget_ranges = {
            "low": (0, 5_000_000),
            "medium": (5_000_000, 15_000_000),
            "high": (15_000_000, float('inf'))
        }
        
        # Category keywords
        self.category_keywords = {
            "beach": ["pantai", "beach", "laut", "sea", "diving", "snorkeling"],
            "mountain": ["gunung", "mountain", "hiking", "mendaki", "trekking"],
            "culture": ["budaya", "culture", "heritage", "sejarah", "history", "museum"],
            "urban": ["kota", "city", "urban", "shopping", "mall"],
            "nature": ["alam", "nature", "forest", "hutan", "air terjun", "waterfall"],
            "culinary": ["kuliner", "culinary", "makanan", "food", "restaurant", "rumah makan"]
        }
        
        # Activity types
        self.activity_keywords = {
            "family": ["keluarga", "family", "anak", "children", "kids"],
            "honeymoon": ["honeymoon", "romantic", "romantis", "couple"],
            "adventure": ["adventure", "petualangan", "extreme", "adrenalin"],
            "relaxation": ["relaxation", "santai", "relax", "spa"]
        }
    
    def extract_user_preferences(self, query: str) -> Dict:
        """
        Extract user preferences from query
        Part of: "Developing the Decision-Making Agent"
        """
        query_lower = query.lower()
        
        preferences = {
            "budget": None,
            "categories": [],
            "activities": [],
            "group_type": None
        }
        
        # Extract budget
        budget_match = re.search(r'(\d+)\s*(juta|million|ribu|thousand)', query_lower)
        if budget_match:
            amount = int(budget_match.group(1))
            unit = budget_match.group(2)
            
            if 'juta' in unit or 'million' in unit:
                budget_idr = amount * 1_000_000
            else:
                budget_idr = amount * 1_000
            
            # Classify budget range
            if budget_idr < 5_000_000:
                preferences["budget"] = "low"
            elif budget_idr < 15_000_000:
                preferences["budget"] = "medium"
            else:
                preferences["budget"] = "high"
        
        # Extract categories
        for category, keywords in self.category_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                preferences["categories"].append(category)
        
        # Extract activities
        for activity, keywords in self.activity_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                preferences["activities"].append(activity)
        
        # Determine group type
        if any(kw in query_lower for kw in ["keluarga", "family", "anak"]):
            preferences["group_type"] = "family"
        elif any(kw in query_lower for kw in ["honeymoon", "romantic", "couple"]):
            preferences["group_type"] = "couple"
        elif any(kw in query_lower for kw in ["solo", "sendiri", "alone"]):
            preferences["group_type"] = "solo"
        
        return preferences
    
    def score_recommendation(
        self, 
        destination_text: str, 
        preferences: Dict
    ) -> float:
        """
        Score a destination based on user preferences
        Part of: "Evaluate Recommendation Result"
        
        Returns: Score between 0-100
        """
        score = 0.0
        max_score = 100.0
        text_lower = destination_text.lower()
        
        # Budget match (30 points)
        if preferences["budget"]:
            budget_keywords = {
                "low": ["murah", "budget", "hemat", "ekonomis"],
                "medium": ["menengah", "moderate", "standard"],
                "high": ["mewah", "luxury", "premium", "exclusive"]
            }
            
            if any(kw in text_lower for kw in budget_keywords.get(preferences["budget"], [])):
                score += 30
        
        # Category match (40 points)
        if preferences["categories"]:
            category_matches = 0
            for category in preferences["categories"]:
                if any(kw in text_lower for kw in self.category_keywords[category]):
                    category_matches += 1
            
            score += (category_matches / len(preferences["categories"])) * 40
        
        # Activity match (20 points)
        if preferences["activities"]:
            activity_matches = 0
            for activity in preferences["activities"]:
                if any(kw in text_lower for kw in self.activity_keywords[activity]):
                    activity_matches += 1
            
            score += (activity_matches / len(preferences["activities"])) * 20
        
        # Group type match (10 points)
        if preferences["group_type"]:
            group_keywords = {
                "family": ["keluarga", "family", "anak", "playground"],
                "couple": ["romantic", "privat", "couple", "honeymoon"],
                "solo": ["solo", "backpacker", "hostel"]
            }
            
            if any(kw in text_lower for kw in group_keywords.get(preferences["group_type"], [])):
                score += 10
        
        return round(score, 2)
    
    def parse_llm_response(self, llm_response: str) -> List[Dict]:
        """
        Parse LLM response to extract structured recommendations
        """
        recommendations = []
        
        # Try to split by numbered list or bullet points
        lines = llm_response.split('\n')
        
        current_dest = {
            "name": "",
            "description": "",
            "budget": "",
            "facilities": [],
            "best_time": ""
        }
        
        for line in lines:
            line = line.strip()
            
            # Detect destination name (numbered or bolded)
            if re.match(r'^\d+\.', line) or line.startswith('**'):
                if current_dest["name"]:
                    recommendations.append(current_dest.copy())
                
                # Extract destination name
                current_dest = {
                    "name": re.sub(r'^\d+\.\s*|\*\*', '', line).strip(),
                    "description": "",
                    "budget": "",
                    "facilities": [],
                    "best_time": ""
                }
            
            # Extract budget info
            elif "budget" in line.lower() or "biaya" in line.lower():
                current_dest["budget"] = line
            
            # Extract facilities
            elif "fasilitas" in line.lower() or "facilities" in line.lower():
                facilities = re.findall(r'[-•]\s*(.+)', line)
                current_dest["facilities"].extend(facilities)
            
            # Extract best time
            elif "waktu terbaik" in line.lower() or "best time" in line.lower():
                current_dest["best_time"] = line
            
            # Add to description
            elif line and not line.startswith('#'):
                current_dest["description"] += " " + line
        
        # Add last destination
        if current_dest["name"]:
            recommendations.append(current_dest)
        
        return recommendations
    
    def rank_recommendations(
        self,
        llm_response: str,
        user_query: str,
        retrieved_context: str
    ) -> List[TourismRecommendation]:
        """
        Rank and structure recommendations
        Implementation of: "Experiment Provides Recommendation"
        
        Returns: List of ranked TourismRecommendation objects
        """
        # Extract user preferences
        preferences = self.extract_user_preferences(user_query)
        
        # Parse LLM response
        parsed_recs = self.parse_llm_response(llm_response)
        
        # Score each recommendation
        ranked = []
        for rec in parsed_recs:
            # Combine destination description with context for scoring
            full_text = f"{rec['name']} {rec['description']} {retrieved_context}"
            
            score = self.score_recommendation(full_text, preferences)
            
            # Determine category
            category = "general"
            for cat, keywords in self.category_keywords.items():
                if any(kw in full_text.lower() for kw in keywords):
                    category = cat
                    break
            
            ranked.append(TourismRecommendation(
                destination=rec["name"],
                category=category,
                budget_range=rec.get("budget", "Not specified"),
                score=score,
                reason=rec.get("description", "").strip()[:200],
                facilities=rec.get("facilities", []),
                best_time=rec.get("best_time", "Year-round")
            ))
        
        # Sort by score (highest first)
        ranked.sort(key=lambda x: x.score, reverse=True)
        
        return ranked
    
    def generate_explanation(self, recommendation: TourismRecommendation) -> str:
        """
        Generate explanation for why this recommendation was made
        Part of: "Agent Performance Validation"
        """
        explanation = f"""
**Why this recommendation (Score: {recommendation.score}/100):**

- **Category:** {recommendation.category.title()}
- **Budget:** {recommendation.budget_range}
- **Match Reason:** {recommendation.reason[:150]}...

This destination scored {recommendation.score}/100 based on your preferences.
"""
        return explanation

    # =========================================================================
    # CONTENT-BASED FILTERING ALGORITHM
    # =========================================================================
    #
    # Rumus gabungan (0.0 – 1.0):
    #
    #   score = w1 × CategoryMatch
    #         + w2 × BudgetMatch
    #         + w3 × RatingNorm
    #         + w4 × ActivityMatch
    #
    # Bobot default: w1=0.40, w2=0.25, w3=0.20, w4=0.15
    #
    # CategoryMatch  = |kategori_item ∩ preferensi_user| / |preferensi_user|
    # BudgetMatch    = 1.0 | 0.5 | 0.0  (sesuai / tidak ada info / tidak sesuai)
    # RatingNorm     = rating_item / 5.0
    # ActivityMatch  = |aktivitas_item ∩ aktivitas_user| / |aktivitas_user|
    # =========================================================================

    # Pemetaan kategori JSON locations.json → kategori DecisionAgent
    _JSON_TO_AGENT_CATEGORY = {
        'pantai':      'beach',
        'bukit':       'mountain',
        'budaya':      'culture',
        'alam':        'nature',
        'air_terjun':  'nature',
        'danau':       'nature',
        'geowisata':   'nature',
        'rekreasi':    'urban',
        'desa_wisata': 'culture',
        'tour':        'nature',
        'kuliner':     'culinary',
        'hotel':       'urban',
        'penginapan':  'urban',
    }

    # Aktivitas yang diasosiasikan dengan tiap kategori JSON
    _CATEGORY_ACTIVITY_MAP = {
        'pantai':      ['honeymoon', 'relaxation', 'adventure'],
        'bukit':       ['adventure', 'relaxation'],
        'alam':        ['adventure', 'family', 'relaxation'],
        'air_terjun':  ['adventure', 'family'],
        'danau':       ['family', 'relaxation', 'honeymoon'],
        'budaya':      ['family'],
        'rekreasi':    ['family'],
        'desa_wisata': ['family'],
        'geowisata':   ['adventure', 'family'],
        'tour':        ['family', 'adventure'],
        'kuliner':     ['family'],
        'hotel':       ['family', 'honeymoon', 'relaxation'],
        'penginapan':  ['family', 'honeymoon', 'relaxation'],
    }

    # Range harga per kategori budget (IDR / orang / malam atau tiket masuk)
    _BUDGET_PRICE_RANGES = {
        'low':    (0,          75_000),
        'medium': (75_000,     300_000),
        'high':   (300_000,    float('inf')),
    }

    def _parse_price_idr(self, price_str: str) -> float:
        """
        Ekstrak angka dari string harga seperti 'Rp 50.000', '50k', '1 juta', dsb.
        Kembalikan None jika tidak dapat di-parse.
        """
        if not price_str or price_str in ('N/A', '-', ''):
            return None
        s = price_str.lower().replace('.', '').replace(',', '').strip()
        # Bentuk 'gratis' / 'free'
        if any(w in s for w in ['gratis', 'free', 'tidak dipungut']):
            return 0.0
        # Variasi ribuan / jutaan
        m = re.search(r'(\d+(?:\.\d+)?)\s*(juta|ribu|rb|k\b)', s)
        if m:
            val = float(m.group(1))
            unit = m.group(2)
            if unit in ('juta',):
                return val * 1_000_000
            return val * 1_000
        # Angka biasa (sudah bersih dari titik)
        m = re.search(r'(\d+)', s)
        if m:
            return float(m.group(1))
        return None

    def content_based_score(
        self,
        location: Dict,
        preferences: Dict,
        *,
        w_category: float = 0.40,
        w_budget:   float = 0.25,
        w_rating:   float = 0.20,
        w_activity: float = 0.15,
    ) -> float:
        """
        Hitung Content-Based Filtering score untuk satu item lokasi
        berdasarkan preferensi pengguna yang diekstrak dari query.

        Parameter
        ---------
        location    : dict dari locations.json  (name, category, price, rating, …)
        preferences : dict dari extract_user_preferences()
                      keys: budget, categories, activities, group_type

        Return
        ------
        float dalam rentang [0.0, 1.0]
        """
        # ── 1. CategoryMatch ──────────────────────────────────────────────
        loc_category_json = location.get('category', '')
        loc_category_agent = self._JSON_TO_AGENT_CATEGORY.get(loc_category_json, '')

        user_cats = preferences.get('categories', [])
        if user_cats:
            category_match = 1.0 if loc_category_agent in user_cats else 0.0
        else:
            # Tidak ada preferensi kategori → skor netral
            category_match = 0.5

        # ── 2. BudgetMatch ────────────────────────────────────────────────
        user_budget = preferences.get('budget')  # 'low' | 'medium' | 'high' | None
        price_val   = self._parse_price_idr(location.get('price', ''))

        if user_budget is None or price_val is None:
            budget_match = 0.5   # tidak ada info → netral
        else:
            lo, hi = self._BUDGET_PRICE_RANGES[user_budget]
            if lo <= price_val <= hi:
                budget_match = 1.0
            else:
                # Seberapa jauh? → hukuman proporsional tapi tidak terlalu keras
                midpoint = (lo + hi) / 2 if hi != float('inf') else lo * 2
                if midpoint == 0:
                    budget_match = 0.0
                else:
                    distance_ratio = abs(price_val - midpoint) / midpoint
                    budget_match = max(0.0, 1.0 - distance_ratio * 0.5)

        # ── 3. RatingNorm ─────────────────────────────────────────────────
        raw_rating  = location.get('rating', 0) or 0
        rating_norm = min(float(raw_rating), 5.0) / 5.0

        # ── 4. ActivityMatch ──────────────────────────────────────────────
        user_activities = list(preferences.get('activities', []))
        # group_type juga diperlakukan sebagai aktivitas implisit
        group_type = preferences.get('group_type')
        if group_type and group_type not in user_activities:
            user_activities.append(group_type)

        if user_activities:
            loc_activities = self._CATEGORY_ACTIVITY_MAP.get(loc_category_json, [])
            matches = sum(1 for a in user_activities if a in loc_activities)
            activity_match = matches / len(user_activities)
        else:
            activity_match = 0.5   # tidak ada preferensi → netral

        # ── Gabungkan dengan bobot ────────────────────────────────────────
        score = (
            w_category * category_match
            + w_budget   * budget_match
            + w_rating   * rating_norm
            + w_activity * activity_match
        )
        return round(score, 4)

    def rank_locations_cb(
        self,
        locations: List[Dict],
        query: str,
    ) -> List[Dict]:
        """
        Urutkan daftar lokasi dari locations.json menggunakan Content-Based
        Filtering berdasarkan preferensi yang diekstrak dari query.

        Return: list lokasi yang sama dengan tambahan key 'cb_score' (float),
                diurutkan dari skor tertinggi ke terendah.
        """
        preferences = self.extract_user_preferences(query)
        scored = []
        for loc in locations:
            cb = self.content_based_score(loc, preferences)
            scored.append({**loc, 'cb_score': cb})
        scored.sort(key=lambda x: x['cb_score'], reverse=True)
        return scored
