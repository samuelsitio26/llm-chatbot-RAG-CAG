"""
Decision-Making Agent for Tourism Recommendation
Implements the agent logic from flowchart to provide ranked recommendations
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
