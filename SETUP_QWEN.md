# 🚀 Setup Qwen2.5-7B-Instruct untuk HPC IT Del

## Copy-Paste Commands untuk Terminal Anda

### 1. Cek GPU VRAM yang tersedia
```bash
nvidia-smi
```
**Pastikan VRAM free >8GB untuk model quantized**

---

### 2. Aktivasi Environment dan Install Dependencies

```bash
# Aktivasi conda environment llm-rag (atau buat baru jika belum ada)
conda activate llm-rag

# Install/upgrade packages yang diperlukan
pip install bitsandbytes>=0.43.0 accelerate>=0.25.0 --upgrade

# Verifikasi instalasi
pip list | grep -E "bitsandbytes|accelerate|transformers|torch"
```

**Jika environment llm-rag belum ada, buat dulu:**
```bash
conda create -n llm-rag python=3.10 -y
conda activate llm-rag
pip install -r requirements.txt
```

---

### 3. Test Load Model Qwen (Quick Test)

Buat file test script:
```bash
cat > test_qwen_load.py << 'EOF'
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import os
from dotenv import load_dotenv

load_dotenv()

print("="*60)
print("🔍 Testing Qwen2.5-7B-Instruct Loading")
print("="*60)

# Check GPU
print(f"✅ CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"📊 GPU: {torch.cuda.get_device_name(0)}")
    print(f"💾 Total VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    print(f"💾 Free VRAM: {torch.cuda.memory_allocated(0) / 1024**3:.2f} GB used")
    print("-"*60)

model_id = "Qwen/Qwen2.5-7B-Instruct"
print(f"🔄 Loading model: {model_id}")

try:
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        token=os.getenv("ACCESS_TOKEN"),
        trust_remote_code=True
    )
    print("✅ Tokenizer loaded")
    
    # Load model with 4-bit quantization
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True
    )
    
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=quantization_config,
        device_map="auto",
        token=os.getenv("ACCESS_TOKEN"),
        trust_remote_code=True
    )
    print("✅ Model loaded with 4-bit quantization")
    
    # Check VRAM usage
    if torch.cuda.is_available():
        print(f"💾 VRAM Used: {torch.cuda.memory_allocated(0) / 1024**3:.2f} GB")
        print(f"💾 VRAM Cached: {torch.cuda.memory_reserved(0) / 1024**3:.2f} GB")
    
    print("-"*60)
    
    # Quick inference test
    print("🧪 Testing inference...")
    test_query = "Halo, tolong rekomendasikan pantai di Danau Toba untuk honeymoon"
    
    messages = [
        {"role": "system", "content": "Anda adalah asisten wisata Danau Toba yang ramah dan informatif."},
        {"role": "user", "content": test_query}
    ]
    
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=150,
        temperature=0.7,
        do_sample=True
    )
    
    response = tokenizer.batch_decode(
        generated_ids[:, model_inputs['input_ids'].shape[1]:],
        skip_special_tokens=True
    )[0]
    
    print(f"📝 Query: {test_query}")
    print(f"🤖 Response: {response[:200]}...")
    
    print("="*60)
    print("✅ SUCCESS! Model Qwen2.5-7B-Instruct siap digunakan!")
    print("💡 VRAM yang digunakan sudah efisien dengan 4-bit quantization")
    print("="*60)
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
EOF

# Jalankan test
python test_qwen_load.py
```

---

### 4. Jika Test Berhasil, Jalankan API

```bash
# Jalankan backend API
cd ~/test/llm-chatbot-rag
python src/api.py
```

**Expected Output:**
```
🔍 Loading model: Qwen/Qwen2.5-7B-Instruct
📍 Device: cuda
✅ Model loaded with 4-bit quantization
💾 Estimated VRAM usage: ~6-7GB
📚 Loading 9 PDF files from data/tourism/
✅ RAG system ready!
🚀 FastAPI server running on http://0.0.0.0:8000
```

---

### 5. Test API (Terminal Baru)

```bash
# Test di terminal lain
curl http://localhost:8000/api/status

# Test chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Rekomendasi pantai untuk honeymoon budget 10 juta",
    "use_cache": true,
    "k": 5
  }'
```

---

## 🔧 Troubleshooting

### Problem 1: CUDA Out of Memory
```bash
# Cek process yang menggunakan GPU
nvidia-smi

# Kill process yang tidak perlu
kill -9 <PID>

# Atau clear cache
python -c "import torch; torch.cuda.empty_cache()"
```

### Problem 2: bitsandbytes installation error
```bash
# Install dengan conda
conda install -c conda-forge bitsandbytes

# Atau build from source
pip install bitsandbytes --no-binary bitsandbytes
```

### Problem 3: Model download gagal
```bash
# Cek HuggingFace token
cat .env | grep ACCESS_TOKEN

# Download manual
huggingface-cli login --token YOUR_TOKEN
huggingface-cli download Qwen/Qwen2.5-7B-Instruct
```

### Problem 4: VRAM masih kurang
**Gunakan Llama-3.2-3B sebagai alternatif** (lebih ringan):

Edit `src/model.py` line 15:
```python
def __init__(self, model_id: str = "meta-llama/Llama-3.2-3B-Instruct", device: str = "cuda"):
```

Llama-3.2-3B hanya butuh ~6GB VRAM tanpa quantization.

---

## 📊 Perbandingan VRAM

| Model | Without Quantization | With 4-bit | With 8-bit |
|-------|---------------------|------------|------------|
| Gemma 2B (lama) | ~5GB | ~3GB | ~4GB |
| Llama-3.2-3B | ~6GB | ~4GB | ~5GB |
| **Qwen2.5-7B** (baru) | ~14GB | **~6-7GB** ✅ | ~8GB |
| Gemma-2-9B | ~18GB | ~8GB | ~10GB |

---

## ✅ Next Steps

Setelah model berhasil load:
1. Test dengan berbagai query wisata Toba
2. Monitor cache hit rate di `/api/stats`
3. Bandingkan response quality dengan Gemma 2B lama
4. Jika puas, deploy ke production

---

## 💡 Tips

1. **Gunakan tmux** untuk persistent session:
```bash
tmux new -s backend
python src/api.py
# Detach: Ctrl+B lalu D
```

2. **Monitor GPU real-time**:
```bash
watch -n 1 nvidia-smi
```

3. **Backup model lama** (jika mau rollback):
```bash
git checkout src/model.py  # untuk rollback ke Gemma 2B
```

---

## 📝 Notes

- Qwen2.5-7B excellent untuk Bahasa Indonesia
- Dengan 4-bit quantization, VRAM usage mirip dengan Gemma 2B
- Response quality jauh lebih baik (3.5x parameter lebih banyak)
- Cocok untuk sistem rekomendasi wisata karena ditraining dengan banyak data tourism

---

**Siap Copy-Paste Commands di Atas!** 🚀
