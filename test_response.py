"""Quick test script for response generation"""
from src.cag_system import CAGSystem
from src.model import GeminiChatModel
from langchain_huggingface import HuggingFaceEmbeddings
import glob

# Init
print("Initializing...")
model = GeminiChatModel()
encoder = HuggingFaceEmbeddings(
    model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
)
cag = CAGSystem(model=model, encoder=encoder)

# Load PDFs
pdf_files = glob.glob('database/vectordatabase/*.pdf')
if pdf_files:
    print(f"Loading {len(pdf_files)} PDFs...")
    cag.load_documents(pdf_files)

# Test — 1 pertanyaan saja
query = "apa saja tempat wisata menarik di Danau Toba?"
print("\n" + "="*60)
print(f"Testing: {query}")
print("="*60)
result = cag.get_response(query, k=8, max_new_tokens=1024)
print(f"\nResponse length: {len(result['response'])} chars")
print(f"Source     : {result['source']}")
print(f"Cache used : {result.get('cache_used', False)}")
print(f"Chunks     : {result.get('num_chunks', 0)}")
print("\n" + "-"*60)
print(result['response'])
