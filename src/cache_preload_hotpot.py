"""
Cache Preloader for HotpotQA Dataset
=====================================

Module ini menyediakan fungsi untuk:
1. Extract dan preload seluruh dokumen context HotpotQA ke KV-Cache LLM
2. Build FAISS vector store untuk Pure RAG evaluation
3. Menyimpan dan load cache state untuk consistency across experiments

Workflow:
- Fase 1: Load 200 queries dari HotpotQA dev dataset
- Fase 2: Extract semua context paragraphs dari supporting facts
- Fase 3: Preload ke KV-Cache untuk Pure CAG
- Fase 4: Build FAISS index untuk Pure RAG
"""

import os
import json
import pickle
import random
from typing import Dict, List, Tuple, Optional
from datetime import datetime

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document as LCDocument


class HotpotQACachePreloader:
    """Preloader untuk HotpotQA context documents"""

    def __init__(
        self,
        dataset_path: str = None,
        cache_dir: str = None,
        num_samples: int = 200,
        random_seed: int = 42,
    ):
        """
        Parameters:
        -----------
        dataset_path : str
            Path ke hotpot_dev_distractor_v1.json
        cache_dir : str
            Directory untuk menyimpan preloaded cache state
        num_samples : int
            Jumlah query untuk evaluasi (default 200)
        random_seed : int
            Random seed untuk reproducibility
        """
        self.dataset_path = dataset_path or os.path.abspath(
            '../datasets/hotpotqa/hotpot_dev_distractor_v1.json'
        )
        self.cache_dir = cache_dir or os.path.abspath('../database/kv_cache/hotpotqa')
        self.num_samples = num_samples
        self.random_seed = random_seed

        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)

        # Storage untuk loaded data
        self.queries: List[Dict] = []
        self.all_contexts: List[str] = []
        self.context_mapping: Dict[str, List[str]] = {}  # query_id -> context texts

    def load_dataset(self) -> List[Dict]:
        """
        Load HotpotQA dataset dan extract 200 queries dengan contexts
        
        Returns:
        --------
        List[Dict] : List of query dictionaries with fields:
            - id: unique identifier
            - question: query string
            - answer: ground truth answer
            - contexts: list of supporting context paragraphs
            - supporting_facts: list of (title, sentence_id) pairs
        """
        print(f"\n{'='*70}")
        print("📚 Loading HotpotQA Dataset")
        print(f"{'='*70}")
        print(f"  Path: {self.dataset_path}")
        print(f"  Samples: {self.num_samples}")
        print(f"  Seed: {self.random_seed}")

        if not os.path.exists(self.dataset_path):
            raise FileNotFoundError(f"HotpotQA dataset not found: {self.dataset_path}")

        with open(self.dataset_path, 'r', encoding='utf-8') as f:
            hotpot_data = json.load(f)

        # Filter valid entries
        valid_entries = [
            item for item in hotpot_data
            if item.get('question', '').strip()
            and item.get('answer', '').strip()
            and item.get('context')  # Must have context
        ]

        # Random sampling
        random.seed(self.random_seed)
        sampled = random.sample(
            valid_entries,
            min(self.num_samples, len(valid_entries))
        )

        # Extract queries with contexts
        self.queries = []
        seen_context_texts = set()

        for idx, item in enumerate(sampled):
            query_id = item.get('_id', f'hotpot_{idx}')
            
            # Extract all context paragraphs
            # HotpotQA context format: list of [title, [sentence1, sentence2, ...]]
            contexts = []
            context_mapping = []
            
            for ctx_idx, (title, sentences) in enumerate(item['context']):
                # Combine sentences into paragraph
                paragraph = ' '.join(sentences).strip()
                if paragraph and paragraph not in seen_context_texts:
                    context_id = f"{query_id}_ctx_{ctx_idx}"
                    contexts.append({
                        'id': context_id,
                        'title': title,
                        'text': paragraph,
                    })
                    context_mapping.append(context_id)
                    seen_context_texts.add(paragraph)

            # Supporting facts (gold evidence)
            supporting_facts = item.get('supporting_facts', [])

            self.context_mapping[query_id] = [
                ctx.get('text', '') for ctx in contexts if ctx.get('text')
            ]

            self.queries.append({
                'id': query_id,
                'question': item['question'].strip(),
                'answer': item['answer'].strip(),
                'type': item.get('type', 'unknown'),
                'level': item.get('level', 'unknown'),
                'contexts': contexts,
                'context_ids': context_mapping,
                'supporting_facts': supporting_facts,
            })

        # Build global context list
        all_ctx_dict = {}
        for query in self.queries:
            for ctx in query['contexts']:
                if ctx['id'] not in all_ctx_dict:
                    all_ctx_dict[ctx['id']] = ctx['text']

        self.all_contexts = list(all_ctx_dict.values())

        print(f"\n✅ Dataset Loaded Successfully")
        print(f"  Total queries: {len(self.queries)}")
        print(f"  Unique contexts: {len(self.all_contexts)}")
        print(f"  Avg contexts per query: {len(self.all_contexts) / len(self.queries):.1f}")
        print(f"{'='*70}\n")

        return self.queries

    def build_combined_context_document(self) -> str:
        """
        Gabungkan semua context menjadi satu dokumen besar untuk preload ke KV-Cache
        
        Returns:
        --------
        str : Combined context document
        """
        print(f"📄 Building combined context document...")
        
        combined = "\n\n".join([
            f"[Context {idx+1}]\n{ctx}"
            for idx, ctx in enumerate(self.all_contexts)
        ])

        print(f"  Total contexts: {len(self.all_contexts)}")
        print(f"  Combined length: {len(combined):,} characters")
        print(f"  Estimated tokens: ~{len(combined) // 4:,}")

        return combined

    def save_cache_state(self, identifier: str = None) -> str:
        """
        Save preloaded cache state untuk consistency across experiments
        
        Parameters:
        -----------
        identifier : str
            Optional identifier untuk cache version (default: timestamp)
        
        Returns:
        --------
        str : Path to saved cache file
        """
        if identifier is None:
            identifier = datetime.now().strftime("%Y%m%d_%H%M%S")

        cache_file = os.path.join(self.cache_dir, f"preload_state_{identifier}.pkl")

        cache_state = {
            'timestamp': datetime.now().isoformat(),
            'dataset_path': self.dataset_path,
            'num_samples': self.num_samples,
            'random_seed': self.random_seed,
            'queries': self.queries,
            'all_contexts': self.all_contexts,
            'context_mapping': self.context_mapping,
        }

        with open(cache_file, 'wb') as f:
            pickle.dump(cache_state, f)

        print(f"💾 Cache state saved: {cache_file}")
        return cache_file

    def load_cache_state(self, cache_file: str) -> Dict:
        """Load previously saved cache state"""
        with open(cache_file, 'rb') as f:
            cache_state = pickle.load(f)

        self.queries = cache_state['queries']
        self.all_contexts = cache_state['all_contexts']
        self.context_mapping = cache_state.get('context_mapping', {})

        print(f"📂 Cache state loaded: {cache_file}")
        print(f"  Queries: {len(self.queries)}")
        print(f"  Contexts: {len(self.all_contexts)}")

        return cache_state

    def build_faiss_vectorstore(
        self,
        encoder,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> FAISS:
        """
        Build FAISS vector store untuk Pure RAG evaluation
        
        Parameters:
        -----------
        encoder : Embeddings
            Embedding model (HuggingFaceEmbeddings)
        chunk_size : int
            Size of each text chunk
        chunk_overlap : int
            Overlap between chunks
        
        Returns:
        --------
        FAISS : Vector store ready for retrieval
        """
        print(f"\n{'='*70}")
        print("🔍 Building FAISS Vector Store for Pure RAG")
        print(f"{'='*70}")
        print(f"  Chunk size: {chunk_size}")
        print(f"  Chunk overlap: {chunk_overlap}")

        # Split contexts into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )

        # Create LangChain documents
        documents = []
        for idx, ctx in enumerate(self.all_contexts):
            doc = LCDocument(
                page_content=ctx,
                metadata={'source': 'hotpotqa', 'context_id': idx}
            )
            documents.append(doc)

        # Split into chunks
        chunks = text_splitter.split_documents(documents)

        print(f"\n  Original contexts: {len(documents)}")
        print(f"  Total chunks: {len(chunks)}")

        # Build FAISS index
        print(f"\n  Building FAISS index...")
        faiss_db = FAISS.from_documents(chunks, encoder)

        print(f"✅ FAISS Vector Store Ready")
        print(f"{'='*70}\n")

        return faiss_db

    def preload_to_kvcache(self, llm_model, batch_size: int = 10) -> Dict:
        """
        Preload semua contexts ke KV-Cache LLM
        
        Parameters:
        -----------
        llm_model : GeminiChatModel
            LLM model dengan KV-Cache support
        batch_size : int
            Number of contexts to process per batch
        
        Returns:
        --------
        Dict : Preload statistics
        """
        print(f"\n{'='*70}")
        print("⚡ Preloading Contexts to KV-Cache")
        print(f"{'='*70}")
        print(f"  Total contexts: {len(self.all_contexts)}")
        print(f"  Batch size: {batch_size}")

        combined_doc = self.build_combined_context_document()

        # Create preload prompt
        preload_prompt = f"""You are a knowledge base system. Store the following context documents in your cache for future queries.

{combined_doc}

Respond with: "Context loaded successfully" """

        print(f"\n  Sending preload request to LLM...")
        start_time = datetime.now()

        try:
            response = llm_model._call_gemini_api(
                preload_prompt,
                max_tokens=50
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            stats = {
                'success': True,
                'num_contexts': len(self.all_contexts),
                'total_chars': len(combined_doc),
                'estimated_tokens': len(combined_doc) // 4,
                'duration_sec': duration,
                'response': response[:100] if response else None,
            }

            print(f"\n✅ Preload Complete")
            print(f"  Duration: {duration:.2f}s")
            print(f"  Estimated tokens: ~{stats['estimated_tokens']:,}")
            print(f"{'='*70}\n")

            return stats

        except Exception as e:
            print(f"\n❌ Preload Failed: {e}")
            return {
                'success': False,
                'error': str(e),
            }


def quick_test():
    """Quick test function"""
    print("\n" + "="*70)
    print("HotpotQA Cache Preloader - Quick Test")
    print("="*70)

    preloader = HotpotQACachePreloader(num_samples=10)
    
    # Load dataset
    queries = preloader.load_dataset()
    
    print(f"\nSample Query:")
    print(f"  Q: {queries[0]['question']}")
    print(f"  A: {queries[0]['answer']}")
    print(f"  Contexts: {len(queries[0]['contexts'])}")

    # Build combined document
    combined = preloader.build_combined_context_document()
    print(f"\nCombined document preview:")
    print(f"  {combined[:200]}...")

    print("\n✅ Quick test passed")


if __name__ == "__main__":
    quick_test()
