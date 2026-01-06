"""
Performance Metrics and Evaluation System
Implements "Metrics Evaluation" and "Agent Performance Validation" from flowchart
"""

import time
import json
import os
from typing import Dict, List
from datetime import datetime
from dataclasses import dataclass, asdict


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


class PerformanceEvaluator:
    """
    Evaluate system performance and quality
    Implements: "Metrics Evaluation" + "Agent Performance Validation"
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
        score: float = 0.0
    ):
        """Record a query execution"""
        metrics = QueryMetrics(
            query=query,
            response_time=response_time,
            cache_hit=cache_hit,
            source=source,
            num_chunks_retrieved=num_chunks,
            response_length=len(response),
            timestamp=datetime.now().isoformat(),
            score=score
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
   - Cache Hit Rate: {summary['cache_hit_rate']}%
   
2. RESPONSE TIME PERFORMANCE
   - Average Response Time: {summary['performance']['avg_response_time']}s
   - Cache Hit Avg: {summary['performance']['avg_cache_hit_time']}s
   - Cache Miss Avg: {summary['performance']['avg_cache_miss_time']}s
   - Speedup Factor: {summary['performance']['speedup_factor']}x faster with cache
   
3. CACHE EFFECTIVENESS
   - Total Cache Hits: {cache_eval['total_cache_hits']}
   - Total Cache Misses: {cache_eval['total_cache_misses']}
   - Time Saved: {cache_eval['time_saved_minutes']} minutes
   
4. QUALITY METRICS
   - Avg Recommendation Score: {summary['quality']['avg_recommendation_score']}/100
   - Scored Queries: {summary['quality']['total_scored']}
   
5. RETRIEVAL PERFORMANCE
   - Avg Chunks Retrieved: {summary['retrieval']['avg_chunks_retrieved']}
   
6. SOURCE DISTRIBUTION
"""
        for source, count in summary['sources'].items():
            report += f"   - {source}: {count} queries\n"
        
        report += f"""
7. TOP 5 SLOWEST QUERIES (for optimization)
"""
        for i, query_info in enumerate(top_slow, 1):
            report += f"   {i}. {query_info['query']}\n"
            report += f"      Time: {query_info['response_time']}s | Cache: {query_info['cache_hit']}\n"
        
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
