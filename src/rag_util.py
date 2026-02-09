import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter  # ✅ Changed
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from typing import List

load_dotenv()

CACHE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models")
)


class Encoder:
    def __init__(
        self, model_name: str = "sentence-transformers/all-MiniLM-L12-v2", device="cpu"
    ):
        self.embedding_function = HuggingFaceEmbeddings(
            model_name=model_name,
            cache_folder=CACHE_DIR,
            model_kwargs={"device": device},
        )


class FaissDb:
    def __init__(self, docs, embedding_function):
        self.db = FAISS.from_documents(
            docs, embedding_function, distance_strategy=DistanceStrategy.COSINE
        )

    def similarity_search(self, question: str, k: int = 3):
        retrieved_docs = self.db.similarity_search(question, k=k)
        context = "".join(doc.page_content + "\n" for doc in retrieved_docs)
        return context


def load_and_split_pdfs(file_paths: list, chunk_size: int = 256):
    loaders = [PyPDFLoader(file_path) for file_path in file_paths]
    pages = []
    for loader in loaders:
        pages.extend(loader.load())

    text_splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
        tokenizer=AutoTokenizer.from_pretrained(
            "sentence-transformers/all-MiniLM-L12-v2"
        ),
        chunk_size=chunk_size,
        chunk_overlap=int(chunk_size / 10),
        strip_whitespace=True,
    )
    docs = text_splitter.split_documents(pages)
    return docs


class ChatModel:
    def __init__(self, model_id: str, device: str = "cuda"):
        cuda_available = torch.cuda.is_available()
        print(f"🔍 CUDA available: {cuda_available}")

        if not cuda_available:
            device = "cpu"
            print("⚠️ Using CPU mode")

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            cache_dir=CACHE_DIR,
            token=os.getenv("ACCESS_TOKEN"),
        )

        # Load tanpa quantization untuk menghindari error bitsandbytes
        print("📦 Loading model without quantization...")
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            cache_dir=CACHE_DIR,
            token=os.getenv("ACCESS_TOKEN"),
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map="auto" if device == "cuda" else None,
        )

        if device == "cpu":
            self.model = self.model.to("cpu")

        print(f"✅ Model loaded on {device}")

    def get_response(
        self,
        message: str,
        chat_history: list = [],
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.95,
    ):
        chat = chat_history + [{"role": "user", "content": message}]
        prompt = self.tokenizer.apply_chat_template(
            chat, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer.encode(prompt, return_tensors="pt").to(
            self.model.device
        )
        outputs = self.model.generate(
            input_ids=inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=True,
        )
        response = self.tokenizer.decode(outputs[0])
        assistant_response_start = response.rfind("<start_of_turn>model\n") + len(
            "<start_of_turn>model\n"
        )
        assistant_response = response[assistant_response_start:].split("<end_of_turn>")[
            0
        ]
        return assistant_response.strip()


class RAGSystem:
    """
    Retrieval-Augmented Generation System
    Handles document loading, chunking, embedding, and retrieval
    """

    def __init__(self, model, encoder):
        self.model = model
        self.encoder = encoder
        self.database = None

    def build_database(
        self, pdf_paths: List[str], chunk_size: int = 512, chunk_overlap: int = 50
    ):
        """Build vector database from PDFs"""
        # Load documents
        pages = []
        for pdf_path in pdf_paths:
            if not os.path.exists(pdf_path):
                print(f"⚠️ File not found: {pdf_path}")
                continue

            try:
                loader = PyPDFLoader(pdf_path)
                pages.extend(loader.load())
            except Exception as e:
                print(f"❌ Error loading {pdf_path}: {str(e)}")

        if not pages:
            print("❌ No documents loaded!")
            return

        # Split into chunks - ✅ Using RecursiveCharacterTextSplitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        docs = text_splitter.split_documents(pages)

        print(f"📄 Loaded {len(pages)} pages, split into {len(docs)} chunks")

        # Build vector database
        self.database = FAISS.from_documents(
            docs, 
            self.encoder, 
            distance_strategy=DistanceStrategy.DOT_PRODUCT
        )

        print(f"✅ Vector database built with {len(docs)} chunks")

    def retrieve(self, query: str, k: int = 5):
        """Retrieve relevant chunks"""
        if not self.database:
            return []

        return self.database.similarity_search(query, k=k)

    def get_context(self, query: str, k: int = 5) -> str:
        """Get context string from retrieved chunks"""
        docs = self.retrieve(query, k)

        context = "\n\n".join(
            [
                doc.page_content if hasattr(doc, "page_content") else str(doc)
                for doc in docs
            ]
        )

        return context
