"""
Streamlit App with Cache-Augmented Generation (CAG)
Enhanced version with K-V caching for faster responses
"""

import os
import streamlit as st
from model import ChatModel
from cag_system import CAGSystem
from langchain_community.embeddings import HuggingFaceEmbeddings

# Paths
TOURISM_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "tourism")
)

FILES_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "files")
)

# Page config
st.set_page_config(
    page_title="CAG Chatbot", 
    page_icon="🚀", 
    layout="wide"
)

st.title("🚀 Cache-Augmented Generation (CAG) Chatbot")
st.caption("Powered by Google Gemma 2B + K-V Cache + Vector DB on HPC IT Del")


@st.cache_resource
def load_model():
    """Load LLM model (cached)"""
    return ChatModel(model_id="google/gemma-2b-it", device="cuda")


@st.cache_resource
def load_encoder():
    """Load embedding encoder (cached)"""
    return HuggingFaceEmbeddings(
        model_name='sentence-transformers/all-MiniLM-L12-v2',
        model_kwargs={'device': 'cpu'}
    )


@st.cache_resource
def load_cag_system(_model, _encoder):
    """Initialize CAG System and auto-load PDFs"""
    cag_system = CAGSystem(_model, _encoder)
    
    # Auto-load PDFs from tourism folder
    if os.path.exists(TOURISM_DIR):
        pdf_files = [
            os.path.join(TOURISM_DIR, f) 
            for f in os.listdir(TOURISM_DIR) 
            if f.lower().endswith('.pdf')
        ]
        
        if pdf_files:
            with st.spinner(f"🔄 Loading {len(pdf_files)} PDFs from data/tourism/..."):
                try:
                    result = cag_system.load_documents(pdf_files, use_summaries=False)
                    
                    if result and isinstance(result, dict):
                        st.success(f"✅ Loaded {result.get('num_chunks', 0)} chunks from {len(pdf_files)} PDFs in {result.get('processing_time', 0):.1f}s")
                    else:
                        st.success(f"✅ Loaded {len(pdf_files)} PDFs successfully")
                        
                except Exception as e:
                    st.error(f"❌ Error loading documents: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
        else:
            st.warning("⚠️ No PDFs found in data/tourism/")
    else:
        st.error(f"❌ Folder not found: {TOURISM_DIR}")
    
    return cag_system


# Load components with error handling
try:
    model = load_model()
    encoder = load_encoder()
    cag = load_cag_system(model, encoder)
except Exception as e:
    st.error(f"❌ Error loading system: {str(e)}")
    import traceback
    st.code(traceback.format_exc())
    st.stop()


def save_file(uploaded_file):
    """Helper function to save documents to disk"""
    os.makedirs(FILES_DIR, exist_ok=True)
    file_path = os.path.join(FILES_DIR, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path


# Sidebar
with st.sidebar:
    st.header("⚙️ CAG Settings")
    
    # Model parameters
    max_new_tokens = st.number_input("max_new_tokens", 128, 4096, 512)
    k = st.number_input("k (retrieval)", 1, 10, 5)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.7)
    
    st.divider()
    
    # Cache settings
    st.subheader("💾 Cache Settings")
    use_cache = st.checkbox("Enable K-V Cache", value=True)
    use_summaries = st.checkbox("Generate Summaries", value=False)
    
    st.divider()
    
    # File upload
    st.subheader("📤 Upload Documents")
    uploaded_files = st.file_uploader(
        "Upload PDFs for context", 
        type=["PDF", "pdf"], 
        accept_multiple_files=True
    )
    
    if uploaded_files and st.button("🔄 Process Documents"):
        with st.spinner("Processing..."):
            file_paths = [save_file(f) for f in uploaded_files]
            result = cag.load_documents(file_paths, use_summaries)
            st.success(f"✅ Processed {result['num_chunks']} chunks")
    
    st.divider()
    
    # Statistics
    st.subheader("📊 CAG Statistics")
    
    if st.button("📈 Show Stats"):
        stats = cag.get_stats()
        st.json(stats)
    
    # Cache management
    st.divider()
    st.subheader("🔧 Cache Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ Clear Cache"):
            cag.clear_cache()
            st.success("Cache cleared!")
    
    with col2:
        if st.button("⚡ Optimize"):
            result = cag.optimize_cache()
            st.info(f"Freed {result.get('freed_mb', 0):.1f} MB")


# Main chat interface
st.divider()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Show metadata for assistant messages
        if message["role"] == "assistant" and "metadata" in message:
            meta = message["metadata"]
            with st.expander("ℹ️ Response Details"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Source", meta.get("source", "N/A"))
                col2.metric("Time", f"{meta.get('response_time', 0):.2f}s")
                col3.metric("Chunks", meta.get("num_chunks", 0))
                
                if meta.get("cache_used"):
                    st.success(f"✅ Cache Hit (accessed {meta.get('access_count', 0)}x)")

# Chat input
if prompt := st.chat_input("Ask me anything about your documents!"):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = cag.get_response(
                query=prompt,
                k=k,
                max_new_tokens=max_new_tokens,
                use_cache=use_cache,
                temperature=temperature
            )
            
            answer = result["response"]
            st.markdown(answer)
            
            # Show metadata
            with st.expander("ℹ️ Response Details"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Source", result.get("source", "N/A"))
                col2.metric("Time", f"{result.get('response_time', 0):.2f}s")
                col3.metric("Chunks", result.get("num_chunks", 0))
                
                if result.get("cache_used"):
                    st.success(f"✅ Cache Hit!")
    
    st.session_state.messages.append({
        "role": "assistant", 
        "content": answer,
        "metadata": result
    })

# Footer
st.divider()
st.caption("💡 **Tip:** Same questions = Faster responses (cached)!")
st.caption("🏢 Running on HPC IT Del Infrastructure")
