"""Quick test script for response generation"""
from src.cag_system import CAGSystem
from src.model import GeminiChatModel
from langchain_huggingface import HuggingFaceEmbeddings
import glob

# Init
print("Initializing...")
model = GeminiChatModel()
encoder = HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L12-v2', model_kwargs={'device': 'cpu'})
cag = CAGSystem(model=model, encoder=encoder)

# Load PDFs
pdf_files = glob.glob('database/vectordatabase/*.pdf')
if pdf_files:
    print(f"Loading {len(pdf_files)} PDFs...")
    cag.load_documents(pdf_files)

# Test
print("\n" + "="*60)
print("Testing: rekomendasi hotel di toba")
print("="*60)
result = cag.get_response('rekomendasi hotel di toba', max_new_tokens=2048)
print(f"\nResponse length: {len(result['response'])} chars")
print(f"Source: {result['source']}")
print(f"Cache used: {result['cache_used']}")
print("\n" + "-"*60)
print(result['response'])
