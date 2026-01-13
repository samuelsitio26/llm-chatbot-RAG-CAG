"""
Performance Metrics and Evaluation System
Implements "Metrics Evaluation" and "Agent Performance Validation" from flowchart
Includes Quantitative and Qualitative Metrics for RAG/CAG Systems
"""

import time
import json
import os
import re
import nltk
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from collections import defaultdict

# Download NLTK data if not available
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)


@dataclass
class QueryMetrics:
    """Metrics for a single query"""
    query: str
    response_time: float
    cache_hit: bool
    source: str
    num_chunks_retrieved: int
    response_length: int
    timestamp: str
    score: float = 0.0
    # Additional fields for advanced metrics
    ground_truth: Optional[str] = None
    retrieved_chunks: Optional[List[str]] = None
    relevant_chunks: Optional[List[str]] = None


class QuantitativeMetrics:
    """
    Comprehensive quantitative metrics for RAG/CAG evaluation
    
    Metrics Categories:
    1. Efficiency Metrics: Response Time, Cache Hit Rate (CHR)
    2. Retrieval Metrics: RAG Recall, Effective Information Rate (EIR)
    3. Generation Metrics: BERTScore, Completeness, Hallucination Rate, Irrelevancy Score
    """
    
    def __init__(self):
        self.bert_scorer = None
        self._init_bert_scorer()
    
    def _init_bert_scorer(self):
        """Initialize BERTScore lazily"""
        try:
            from bert_score import BERTScorer
            self.bert_scorer = BERTScorer(lang="id", rescale_with_baseline=True)
        except ImportError:
            print("⚠️ bert-score not installed. BERTScore metrics will not be available.")
            print("   Install with: pip install bert-score")
    
    # ========== EFFICIENCY METRICS ==========
    
    def calculate_response_time(self, start_time: float, end_time: float) -> float:
        """
        Calculate response time in seconds
        
        Args:
            start_time: Start timestamp
            end_time: End timestamp
        
        Returns:
            Response time in seconds
        """
        return round(end_time - start_time, 4)
    
    def calculate_cache_hit_rate(self, query_history: List[QueryMetrics]) -> Dict:
        """
        Calculate Cache Hit Rate (CHR)
        
        CHR = (Number of Cache Hits / Total Queries) * 100%
        
        Args:
            query_history: List of query metrics
        
        Returns:
            Dictionary with CHR and related statistics
        """
        if not query_history:
            return {"chr": 0.0, "cache_hits": 0, "total_queries": 0}
        
        total = len(query_history)
        cache_hits = sum(1 for m in query_history if m.cache_hit)
        chr = (cache_hits / total) * 100
        
        return {
            "chr": round(chr, 2),
            "cache_hits": cache_hits,
            "cache_misses": total - cache_hits,
            "total_queries": total
        }
    
    # ========== RETRIEVAL METRICS ==========
    
    def calculate_rag_recall(self, retrieved_chunks: List[str], relevant_chunks: List[str]) -> float:
        """
        Calculate RAG Recall
        
        Recall = |Retrieved ∩ Relevant| / |Relevant|
        
        Args:
            retrieved_chunks: List of retrieved chunk IDs or content
            relevant_chunks: List of relevant (ground truth) chunk IDs or content
        
        Returns:
            Recall score (0-1)
        """
        if not relevant_chunks:
            return 0.0
        
        retrieved_set = set(retrieved_chunks)
        relevant_set = set(relevant_chunks)
        
        intersection = len(retrieved_set.intersection(relevant_set))
        recall = intersection / len(relevant_set)
        
        return round(recall, 4)
    
    def calculate_eir(self, retrieved_chunks: List[str], relevant_chunks: List[str], 
                     total_retrieved: int) -> float:
        """
        Calculate Effective Information Rate (EIR)
        
        EIR = |Retrieved ∩ Relevant| / Total Retrieved
        Measures the proportion of useful information in retrieval
        
        Args:
            retrieved_chunks: Retrieved chunks
            relevant_chunks: Relevant chunks
            total_retrieved: Total number of chunks retrieved
        
        Returns:
            EIR score (0-1)
        """
        if total_retrieved == 0:
            return 0.0
        
        retrieved_set = set(retrieved_chunks)
        relevant_set = set(relevant_chunks)
        
        useful_info = len(retrieved_set.intersection(relevant_set))
        eir = useful_info / total_retrieved
        
        return round(eir, 4)
    
    # ========== GENERATION METRICS ==========
    
    def calculate_bertscore(self, predictions: List[str], references: List[str]) -> Dict:
        """
        Calculate BERTScore (Precision, Recall, F1)
        
        Uses multilingual BERT to measure semantic similarity
        
        Args:
            predictions: Generated responses
            references: Ground truth responses
        
        Returns:
            Dictionary with precision, recall, and F1 scores
        """
        if not self.bert_scorer:
            return {
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "error": "BERTScore not available"
            }
        
        try:
            P, R, F1 = self.bert_scorer.score(predictions, references)
            
            return {
                "precision": round(float(P.mean()), 4),
                "recall": round(float(R.mean()), 4),
                "f1": round(float(F1.mean()), 4),
                "precision_list": P.tolist(),
                "recall_list": R.tolist(),
                "f1_list": F1.tolist()
            }
        except Exception as e:
            return {
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "error": str(e)
            }
    
    def calculate_completeness(self, response: str, required_elements: List[str]) -> Dict:
        """
        Calculate Completeness Score
        
        Measures if response covers all required elements/aspects
        
        Args:
            response: Generated response
            required_elements: List of required topics/keywords
        
        Returns:
            Completeness score and details
        """
        if not required_elements:
            return {"completeness": 1.0, "covered_elements": [], "missing_elements": []}
        
        response_lower = response.lower()
        covered = []
        missing = []
        
        for element in required_elements:
            if element.lower() in response_lower:
                covered.append(element)
            else:
                missing.append(element)
        
        completeness = len(covered) / len(required_elements)
        
        return {
            "completeness": round(completeness, 4),
            "covered_elements": covered,
            "missing_elements": missing,
            "coverage_count": f"{len(covered)}/{len(required_elements)}"
        }
    
    def calculate_hallucination_rate(self, response: str, source_chunks: List[str]) -> Dict:
        """
        Calculate Hallucination Rate
        
        Detects information in response not supported by source chunks
        Uses keyword overlap and factual consistency checks
        
        Args:
            response: Generated response
            source_chunks: Source chunks used for generation
        
        Returns:
            Hallucination rate and analysis
        """
        # Tokenize response into sentences
        from nltk.tokenize import sent_tokenize
        sentences = sent_tokenize(response)
        
        if not sentences or not source_chunks:
            return {
                "hallucination_rate": 0.0,
                "total_sentences": len(sentences),
                "hallucinated_sentences": 0
            }
        
        # Combine all source text
        source_text = " ".join(source_chunks).lower()
        
        hallucinated = 0
        unsupported_sentences = []
        
        for sentence in sentences:
            # Extract key terms from sentence (simple approach)
            words = set(re.findall(r'\w+', sentence.lower()))
            # Remove common stop words
            from nltk.corpus import stopwords
            try:
                stop_words = set(stopwords.words('indonesian'))
                stop_words.update(stopwords.words('english'))
            except:
                stop_words = set()
            
            key_words = words - stop_words
            
            # Check if key words appear in source
            if key_words:
                overlap = sum(1 for word in key_words if word in source_text)
                support_ratio = overlap / len(key_words)
                
                # If less than 30% of key words found, consider hallucination
                if support_ratio < 0.3:
                    hallucinated += 1
                    unsupported_sentences.append(sentence)
        
        hallucination_rate = hallucinated / len(sentences) if sentences else 0
        
        return {
            "hallucination_rate": round(hallucination_rate, 4),
            "total_sentences": len(sentences),
            "hallucinated_sentences": hallucinated,
            "unsupported_examples": unsupported_sentences[:3]  # Show first 3
        }
    
    def calculate_irrelevancy_score(self, response: str, query: str) -> Dict:
        """
        Calculate Irrelevancy Score
        
        Measures how much of the response is irrelevant to the query
        Uses keyword overlap and topic coherence
        
        Args:
            response: Generated response
            query: User query
        
        Returns:
            Irrelevancy score and analysis
        """
        from nltk.tokenize import word_tokenize
        from nltk.corpus import stopwords
        
        try:
            stop_words = set(stopwords.words('indonesian'))
            stop_words.update(stopwords.words('english'))
        except:
            stop_words = set()
        
        # Extract key terms from query
        query_words = set(word_tokenize(query.lower())) - stop_words
        query_words = {w for w in query_words if len(w) > 2}
        
        # Extract words from response
        response_words = set(word_tokenize(response.lower())) - stop_words
        response_words = {w for w in response_words if len(w) > 2}
        
        if not query_words or not response_words:
            return {
                "irrelevancy_score": 0.0,
                "relevance_score": 1.0,
                "query_coverage": 0.0
            }
        
        # Calculate query coverage in response
        query_coverage = len(query_words.intersection(response_words)) / len(query_words)
        
        # Irrelevancy is inverse of relevance
        # If query coverage is high, irrelevancy is low
        irrelevancy = 1.0 - query_coverage
        
        return {
            "irrelevancy_score": round(irrelevancy, 4),
            "relevance_score": round(query_coverage, 4),
            "query_coverage": round(query_coverage, 4),
            "matched_terms": list(query_words.intersection(response_words))[:10]
        }


class QualitativeMetrics:
    """
    Qualitative Metrics - User Judgment Framework
    
    Provides structure for human evaluation of responses
    """
    
    def __init__(self, judgments_file: str = None):
        if judgments_file is None:
            judgments_file = os.path.join(
                os.path.dirname(__file__),
                "..",
                "database",
                "user_judgments.json"
            )
        self.judgments_file = judgments_file
        self.judgments = []
        self.load_judgments()
    
    def load_judgments(self):
        """Load existing judgments"""
        if os.path.exists(self.judgments_file):
            with open(self.judgments_file, 'r', encoding='utf-8') as f:
                self.judgments = json.load(f)
    
    def save_judgments(self):
        """Save judgments to file"""
        os.makedirs(os.path.dirname(self.judgments_file), exist_ok=True)
        with open(self.judgments_file, 'w', encoding='utf-8') as f:
            json.dump(self.judgments, f, indent=2, ensure_ascii=False)
    
    def create_judgment_template(self, query: str, response: str, 
                                system_type: str = "RAG") -> Dict:
        """
        Create a judgment template for user evaluation
        
        Args:
            query: User query
            response: System response
            system_type: "RAG" or "CAG"
        
        Returns:
            Judgment template
        """
        return {
            "id": len(self.judgments) + 1,
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "response": response,
            "system_type": system_type,
            "ratings": {
                "relevance": None,  # 1-5: How relevant is the response?
                "accuracy": None,   # 1-5: Is the information accurate?
                "completeness": None,  # 1-5: Does it cover all aspects?
                "clarity": None,    # 1-5: Is it clear and understandable?
                "usefulness": None, # 1-5: How useful is this response?
                "overall": None     # 1-5: Overall satisfaction
            },
            "feedback": {
                "strengths": "",    # What was good?
                "weaknesses": "",   # What needs improvement?
                "missing_info": "", # What information is missing?
                "comments": ""      # General comments
            },
            "evaluated": False
        }
    
    def submit_judgment(self, judgment: Dict):
        """Submit a user judgment"""
        judgment["evaluated"] = True
        judgment["submission_time"] = datetime.now().isoformat()
        self.judgments.append(judgment)
        self.save_judgments()
    
    def get_average_ratings(self, system_type: Optional[str] = None) -> Dict:
        """
        Calculate average ratings across judgments
        
        Args:
            system_type: Filter by system type ("RAG" or "CAG")
        
        Returns:
            Average ratings
        """
        filtered = [j for j in self.judgments if j.get("evaluated")]
        
        if system_type:
            filtered = [j for j in filtered if j.get("system_type") == system_type]
        
        if not filtered:
            return {"error": "No judgments available"}
        
        ratings_sum = defaultdict(float)
        count = len(filtered)
        
        for judgment in filtered:
            for key, value in judgment["ratings"].items():
                if value is not None:
                    ratings_sum[key] += value
        
        return {
            key: round(total / count, 2)
            for key, total in ratings_sum.items()
        }
    
    def export_judgments_for_analysis(self) -> List[Dict]:
        """Export judgments in analysis-friendly format"""
        return [
            {
                "id": j["id"],
                "system_type": j.get("system_type"),
                "relevance": j["ratings"].get("relevance"),
                "accuracy": j["ratings"].get("accuracy"),
                "completeness": j["ratings"].get("completeness"),
                "clarity": j["ratings"].get("clarity"),
                "usefulness": j["ratings"].get("usefulness"),
                "overall": j["ratings"].get("overall"),
                "evaluated": j.get("evaluated", False)
            }
            for j in self.judgments
        ]


class PerformanceEvaluator:
    """
    Evaluate system performance and quality
    Implements: "Metrics Evaluation" + "Agent Performance Validation"
    Integrates both Quantitative and Qualitative Metrics
    """
    
    def __init__(self, metrics_file: str = None):
        if metrics_file is None:
            metrics_file = os.path.join(
                os.path.dirname(__file__),
                "..",
                "database",
                "metrics.json"
            )
        
        self.metrics_file = metrics_file
        self.query_history: List[QueryMetrics] = []
        self.quantitative = QuantitativeMetrics()
        self.qualitative = QualitativeMetrics()
        self.load_history()
    
    def load_history(self):
        """Load metrics history from file"""
        if os.path.exists(self.metrics_file):
            with open(self.metrics_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.query_history = [
                    QueryMetrics(**item) for item in data
                ]
    
    def save_history(self):
        """Save metrics history to file"""
        os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)
        with open(self.metrics_file, 'w', encoding='utf-8') as f:
            json.dump(
                [asdict(m) for m in self.query_history],
                f,
                indent=2,
                ensure_ascii=False
            )
    
    def record_query(
        self,
        query: str,
        response: str,
        response_time: float,
        cache_hit: bool,
        source: str,
        num_chunks: int = 0,
        score: float = 0.0,
        ground_truth: Optional[str] = None,
        retrieved_chunks: Optional[List[str]] = None,
        relevant_chunks: Optional[List[str]] = None
    ):
        """Record a query execution with optional ground truth for evaluation"""
        metrics = QueryMetrics(
            query=query,
            response_time=response_time,
            cache_hit=cache_hit,
            source=source,
            num_chunks_retrieved=num_chunks,
            response_length=len(response),
            timestamp=datetime.now().isoformat(),
            score=score,
            ground_truth=ground_truth,
            retrieved_chunks=retrieved_chunks,
            relevant_chunks=relevant_chunks
        )
        
        self.query_history.append(metrics)
        
        # Save every 10 queries
        if len(self.query_history) % 10 == 0:
            self.save_history()
    
    def get_performance_summary(self) -> Dict:
        """
        Get comprehensive performance summary
        Part of: "Metrics Evaluation"
        """
        if not self.query_history:
            return {
                "total_queries": 0,
                "message": "No queries recorded yet"
            }
        
        total = len(self.query_history)
        cache_hits = sum(1 for m in self.query_history if m.cache_hit)
        
        # Response times
        response_times = [m.response_time for m in self.query_history]
        avg_response_time = sum(response_times) / len(response_times)
        
        # Cache hit times vs miss times
        cache_hit_times = [m.response_time for m in self.query_history if m.cache_hit]
        cache_miss_times = [m.response_time for m in self.query_history if not m.cache_hit]
        
        avg_cache_hit_time = sum(cache_hit_times) / len(cache_hit_times) if cache_hit_times else 0
        avg_cache_miss_time = sum(cache_miss_times) / len(cache_miss_times) if cache_miss_times else 0
        
        # Quality scores
        scores = [m.score for m in self.query_history if m.score > 0]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # Source distribution
        sources = {}
        for m in self.query_history:
            sources[m.source] = sources.get(m.source, 0) + 1
        
        return {
            "total_queries": total,
            "cache_hit_rate": round((cache_hits / total) * 100, 2),
            "performance": {
                "avg_response_time": round(avg_response_time, 3),
                "avg_cache_hit_time": round(avg_cache_hit_time, 3),
                "avg_cache_miss_time": round(avg_cache_miss_time, 3),
                "speedup_factor": round(avg_cache_miss_time / avg_cache_hit_time, 2) if avg_cache_hit_time > 0 else 0
            },
            "quality": {
                "avg_recommendation_score": round(avg_score, 2),
                "total_scored": len(scores)
            },
            "sources": sources,
            "retrieval": {
                "avg_chunks_retrieved": round(
                    sum(m.num_chunks_retrieved for m in self.query_history) / total, 2
                )
            }
        }
    
    def get_top_queries(self, n: int = 10) -> List[Dict]:
        """Get top N slowest/fastest queries for analysis"""
        sorted_by_time = sorted(
            self.query_history,
            key=lambda x: x.response_time,
            reverse=True
        )
        
        return [
            {
                "query": m.query[:50] + "...",
                "response_time": round(m.response_time, 3),
                "cache_hit": m.cache_hit,
                "source": m.source
            }
            for m in sorted_by_time[:n]
        ]
    
    def evaluate_cache_effectiveness(self) -> Dict:
        """
        Evaluate cache effectiveness
        Part of: "Agent Performance Validation"
        """
        if not self.query_history:
            return {"error": "No data"}
        
        cache_hits = [m for m in self.query_history if m.cache_hit]
        cache_misses = [m for m in self.query_history if not m.cache_hit]
        
        # Time saved by cache
        if cache_hits and cache_misses:
            avg_miss_time = sum(m.response_time for m in cache_misses) / len(cache_misses)
            time_saved = sum(avg_miss_time - m.response_time for m in cache_hits)
        else:
            time_saved = 0
        
        return {
            "total_cache_hits": len(cache_hits),
            "total_cache_misses": len(cache_misses),
            "hit_rate": round(len(cache_hits) / len(self.query_history) * 100, 2),
            "time_saved_seconds": round(time_saved, 2),
            "time_saved_minutes": round(time_saved / 60, 2)
        }
    
    def evaluate_comprehensive(self, 
                              predictions: List[str],
                              references: List[str],
                              queries: List[str],
                              source_chunks_list: List[List[str]],
                              required_elements_list: List[List[str]] = None) -> Dict:
        """
        Comprehensive evaluation with all quantitative metrics
        
        Args:
            predictions: Generated responses
            references: Ground truth responses
            queries: Original queries
            source_chunks_list: Source chunks for each response
            required_elements_list: Required elements for completeness check
        
        Returns:
            Complete evaluation results
        """
        results = {
            "generation_metrics": {},
            "retrieval_metrics": {},
            "per_query_metrics": []
        }
        
        # Generation Metrics
        if self.quantitative.bert_scorer:
            results["generation_metrics"]["bertscore"] = self.quantitative.calculate_bertscore(
                predictions, references
            )
        
        # Per-query metrics
        for i, (pred, ref, query, sources) in enumerate(zip(
            predictions, references, queries, source_chunks_list
        )):
            query_metrics = {
                "query_id": i + 1,
                "query": query[:100] + "..." if len(query) > 100 else query
            }
            
            # Completeness
            if required_elements_list and i < len(required_elements_list):
                query_metrics["completeness"] = self.quantitative.calculate_completeness(
                    pred, required_elements_list[i]
                )
            
            # Hallucination
            query_metrics["hallucination"] = self.quantitative.calculate_hallucination_rate(
                pred, sources
            )
            
            # Irrelevancy
            query_metrics["irrelevancy"] = self.quantitative.calculate_irrelevancy_score(
                pred, query
            )
            
            results["per_query_metrics"].append(query_metrics)
        
        # Aggregate statistics
        if results["per_query_metrics"]:
            avg_hallucination = sum(
                m["hallucination"]["hallucination_rate"] 
                for m in results["per_query_metrics"]
            ) / len(results["per_query_metrics"])
            
            avg_irrelevancy = sum(
                m["irrelevancy"]["irrelevancy_score"]
                for m in results["per_query_metrics"]
            ) / len(results["per_query_metrics"])
            
            results["generation_metrics"]["avg_hallucination_rate"] = round(avg_hallucination, 4)
            results["generation_metrics"]["avg_irrelevancy_score"] = round(avg_irrelevancy, 4)
        
        return results
    
    def generate_report(self) -> str:
        """
        Generate comprehensive evaluation report
        Output for: "Metrics Evaluation"
        """
        summary = self.get_performance_summary()
        cache_eval = self.evaluate_cache_effectiveness()
        top_slow = self.get_top_queries(5)
        
        report = f"""
{'='*80}
📊 SYSTEM PERFORMANCE EVALUATION REPORT
{'='*80}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

1. OVERALL STATISTICS
   - Total Queries Processed: {summary['total_queries']}
   - Cache Hit Rate (CHR): {summary['cache_hit_rate']}%
   
2. EFFICIENCY METRICS
   a) Response Time
      - Average Response Time: {summary['performance']['avg_response_time']}s
      - Cache Hit Avg: {summary['performance']['avg_cache_hit_time']}s
      - Cache Miss Avg: {summary['performance']['avg_cache_miss_time']}s
      - Speedup Factor: {summary['performance']['speedup_factor']}x faster with cache
   
   b) Cache Performance
      - Total Cache Hits: {cache_eval['total_cache_hits']}
      - Total Cache Misses: {cache_eval['total_cache_misses']}
      - Time Saved: {cache_eval['time_saved_minutes']} minutes
   
3. QUALITY METRICS
   - Avg Recommendation Score: {summary['quality']['avg_recommendation_score']}/100
   - Scored Queries: {summary['quality']['total_scored']}
   
4. RETRIEVAL METRICS
   - Avg Chunks Retrieved: {summary['retrieval']['avg_chunks_retrieved']}
   
5. SOURCE DISTRIBUTION
"""
        for source, count in summary['sources'].items():
            report += f"   - {source}: {count} queries\n"
        
        report += f"""
6. TOP 5 SLOWEST QUERIES (for optimization)
"""
        for i, query_info in enumerate(top_slow, 1):
            report += f"   {i}. {query_info['query']}\n"
            report += f"      Time: {query_info['response_time']}s | Cache: {query_info['cache_hit']}\n"
        
        # Add qualitative metrics summary if available
        qual_ratings = self.qualitative.get_average_ratings()
        if "error" not in qual_ratings:
            report += f"""
7. USER JUDGMENT (Qualitative Metrics)
   Average Ratings (1-5 scale):
   - Relevance: {qual_ratings.get('relevance', 'N/A')}
   - Accuracy: {qual_ratings.get('accuracy', 'N/A')}
   - Completeness: {qual_ratings.get('completeness', 'N/A')}
   - Clarity: {qual_ratings.get('clarity', 'N/A')}
   - Usefulness: {qual_ratings.get('usefulness', 'N/A')}
   - Overall Satisfaction: {qual_ratings.get('overall', 'N/A')}
"""
        
        report += f"""
{'='*80}
✅ Evaluation Complete
{'='*80}
"""
        return report
    
    def export_metrics_csv(self, output_file: str = None):
        """Export metrics to CSV for further analysis"""
        if output_file is None:
            output_file = self.metrics_file.replace('.json', '.csv')
        
        import csv
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            if not self.query_history:
                return
            
            writer = csv.DictWriter(f, fieldnames=asdict(self.query_history[0]).keys())
            writer.writeheader()
            
            for metrics in self.query_history:
                writer.writerow(asdict(metrics))
        
        print(f"✅ Exported metrics to {output_file}")


if __name__ == "__main__":
    # Test evaluation system
    evaluator = PerformanceEvaluator()
    
    # Simulate some queries
    evaluator.record_query(
        query="Rekomendasi pantai untuk honeymoon",
        response="Bali memiliki pantai-pantai indah...",
        response_time=0.15,
        cache_hit=True,
        source="cag_cache",
        num_chunks=5,
        score=85.5
    )
    
    evaluator.record_query(
        query="Tempat wisata gunung untuk hiking",
        response="Gunung Bromo adalah destinasi populer...",
        response_time=3.2,
        cache_hit=False,
        source="rag_generation",
        num_chunks=5,
        score=78.0
    )
    
    print(evaluator.generate_report())
