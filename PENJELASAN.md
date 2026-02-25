# Penjelasan Project CAG vs RAG

---

## 1. Konsep CAG vs RAG

### RAG (`rag.py`) — Alur kerja:
```
Pertanyaan masuk
      ↓
Retriever cari dokumen relevan (BM25/OpenAI/Gemini)
      ↓
Dokumen relevan dimasukkan ke prompt
      ↓
LLM generate jawaban dari prompt itu
```
Setiap pertanyaan = 1 proses retrieval + 1 proses generate. **Retrieval terjadi di runtime.**

### CAG (`kvcache1.py`) — Alur kerja:
```
Semua dokumen diload SEKALI ke KV Cache (preprocess)
      ↓
KV Cache disimpan ke file (.pt)
      ↓
Pertanyaan masuk → langsung generate pakai cached context
```
Tidak ada retrieval. **Semua konteks sudah ada di memory (KV Cache) sebelum pertanyaan datang.**

### Bukti di code — perbandingan langsung:

**RAG** (`rag.py`):
```python
# Setiap pertanyaan: retrieve dulu
nodes = retriever.retrieve(question)          # ← retrieval per pertanyaan
knowledge = "\n---\n".join([node.text for node in nodes])
prompt = f"Context: {knowledge}\nQuestion: {question}"
output = model.generate(input_ids, ...)       # ← baru generate
```

**CAG** (`kvcache1.py`):
```python
# SEKALI di awal: preprocessing semua dokumen jadi KV cache
kv = preprocess_knowledge(model, tokenizer, semua_dokumen)

# Setiap pertanyaan: langsung generate, tidak ada retrieval
output = generate(model, input_ids, knowledge_cache)  # ← pakai cache
```

### Apa itu KV Cache?
Ketika LLM memproses teks, setiap token menghasilkan **Key** dan **Value** (dari attention mechanism).
Biasanya ini dihitung ulang setiap inference. Di CAG, Key-Value dari dokumen konteks
**disimpan dulu** → pertanyaan baru tinggal "dilanjutkan" dari cache itu.

---

## 2. Cara Kerja Detail `kvcache1.py`

### Urutan eksekusi:
```
main()
  ├── load model + tokenizer
  ├── kvcache_test(args)
  │     ├── ambil dataset (text_list + questions)
  │     ├── prepare_kvcache()          ← TAHAP 1: preprocessing
  │     │     └── preprocess_knowledge()
  │     └── loop tiap pertanyaan       ← TAHAP 2: generate
  │           └── generate()
  └── simpan hasil ke .txt
```

### Fungsi-fungsi utama:

**`preprocess_knowledge()`** — jantung dari CAG:
```python
# Semua dokumen dienkode jadi token
input_ids = tokenizer.encode(prompt, return_tensors="pt").to(embed_device)

# Dijalankan SEKALI melalui model → hasilkan KV cache
past_key_values = DynamicCache()
outputs = model(input_ids=input_ids, past_key_values=past_key_values, use_cache=True)

return outputs.past_key_values  # ← ini yang disimpan
```
Model memproses semua dokumen, semua attention Key & Value tiap layer tersimpan di `DynamicCache`.

**`generate()`** — inferensi per pertanyaan:
```python
# Input hanya pertanyaan (bukan konteks lagi)
input_ids = tokenizer.encode("Question: ...\nAnswer:", ...)

# KV cache dokumen sudah ada → model "melanjutkan" dari sana
outputs = model(
    input_ids=next_token,
    past_key_values=knowledge_cache,  # ← cache dokumen dari tadi
    use_cache=True
)
# Generate token satu per satu (greedy decoding) sampai EOS
```

**`clean_up()`** — penting untuk pertanyaan ke-2, ke-3, dst.:
```python
# Setelah generate pertanyaan 1, KV cache bertambah panjang
# (karena token pertanyaan + jawaban ikut masuk ke cache)
# → harus dipotong kembali ke panjang awal sebelum pertanyaan berikutnya

for i in range(len(kv.key_cache)):
    kv.key_cache[i] = kv.key_cache[i][:, :, :origin_len, :]
    kv.value_cache[i] = kv.value_cache[i][:, :, :origin_len, :]
```
Ini seperti **"reset" cache** ke kondisi setelah dokumen dimuat, sebelum pertanyaan.

**`_infer_embedding_device()`** — kenapa perlu ini?  
Dengan `device_map="auto"`, layer-layer model bisa tersebar di GPU dan CPU.
Fungsi ini mencari di mana embedding layer berada agar input dikirim ke device yang benar.
Berbeda per arsitektur model:
- LLaMA/TinyLlama → `model.model.embed_tokens`
- BERT/RoBERTa    → `model.roberta.embeddings.word_embeddings`
- GPT-2           → `model.transformer.wte`

---

## 3. Cara Kerja `rag.py`

### Urutan eksekusi:
```
main()
  ├── load model + tokenizer (sama seperti kvcache)
  ├── rag_test(args)
  │     ├── ambil dataset
  │     ├── buat retriever SEKALI (BM25/OpenAI/Gemini/Jina)
  │     └── loop tiap pertanyaan
  │           ├── retriever.retrieve(question)   ← TIAP pertanyaan
  │           ├── susun prompt + konteks hasil retrieve
  │           └── model.generate(prompt)
  └── simpan hasil ke .txt
```

### Retriever yang tersedia (`--index`):

| `--index` | Cara kerja                         | Butuh API key    |
|-----------|------------------------------------|------------------|
| `bm25`    | Keyword matching berbasis statistik | Tidak            |
| `openai`  | Embedding vektor via OpenAI         | `OPENAI_API_KEY` |
| `gemini`  | Embedding vektor via Google Gemini  | `GOOGLE_API_KEY` |
| `jina`    | Embedding vektor via Jina AI        | `JINA_API_KEY`   |

### BM25 — yang paling sering dipakai:
```python
def getBM25Retriever(documents, similarity_top_k=1):
    splitter = SentenceSplitter(chunk_size=512)   # potong dokumen jadi chunks
    nodes = splitter.get_nodes_from_documents(documents)

    bm25_retriever = BM25Retriever.from_defaults(
        nodes=nodes,
        similarity_top_k=similarity_top_k,        # ambil top-K chunk paling relevan
        stemmer=Stemmer.Stemmer("english"),        # kata → bentuk dasar (running→run)
        language="english",
    )
    return bm25_retriever, waktu_build
```

### Loop per pertanyaan di RAG:
```python
for question, ground_truth in dataset:
    # 1. Retrieve → cari chunk relevan dari dokumen
    nodes = retriever.retrieve(question)
    knowledge = "\n---\n".join([node.text for node in nodes])

    # 2. Susun prompt lengkap dengan konteks hasil retrieve
    prompt = f"Context: {knowledge}\nQuestion: {question}"

    # 3. Generate jawaban
    output = model.generate(input_ids, max_new_tokens=300, ...)

    # 4. Post-process: potong bagian sebelum jawaban
    generated_text = generated_text[generated_text.find('assistant') + len('assistant'):]
```
Setiap pertanyaan melakukan **retrieve baru** → ini yang membuat RAG lebih lambat dibanding CAG.

### Perbedaan metrik yang diukur:

|               | RAG                              | CAG                                      |
|---------------|----------------------------------|------------------------------------------|
| Yang diukur   | `retrieve_time` (per pertanyaan) | `cache_time` (selalu ~0, cache sudah siap) |
| `generate_time` | ada                            | ada                                      |
| `prepare_time`  | waktu build index              | waktu preprocess KV cache                |

---

## 4. Dataset — `cag/dataset.py`

### Fungsi utama `get()`:
```python
cagds.get(args.dataset, max_knowledge=1, max_paragraph=50, max_questions=20)
# mengembalikan:
#   text_list → list dokumen/artikel (dimasukkan ke KV cache atau retriever)
#   dataset   → iterator pasangan (question, ground_truth_answer)
```

### Dataset `squad-train`:
Struktur JSON aslinya:
```
data[]
  └── title: "Beyoncé"
      paragraphs[]
        └── context: "Beyoncé Giselle Knowles-Carter..."   ← teks dokumen
            qas[]
              └── question: "In what city..."              ← pertanyaan
                  answers[0].text: "Houston"               ← jawaban benar
```

**Parameter penting:**
- `--maxKnowledge 3` → ambil 3 artikel saja
- `--maxParagraph 50` → tiap artikel max 50 paragraf (hanya berlaku kalau `maxKnowledge=1`)
- `--maxQuestion 20` → evaluasi 20 pertanyaan saja
- `--randomSeed 0` → shuffle artikel & pertanyaan secara deterministik (reproducible)

### Dataset `hotpotqa` — berbeda strukturnya:
- Setiap QA punya **multi-hop context** (butuh gabungan beberapa artikel untuk jawab)
- 1 artikel = 1 pertanyaan (berbeda dengan squad yang 1 artikel bisa ratusan pertanyaan)
- `--maxParagraph` **tidak berlaku** di hotpotqa

### Perbandingan `squad` vs `hotpotqa`:

| | `squad-train` | `hotpotqa-train` |
|---|---|---|
| Tipe pertanyaan | Single-hop (1 artikel cukup) | Multi-hop (butuh beberapa artikel) |
| Jumlah pertanyaan per artikel | ~150 | 1 |
| `--maxParagraph` berlaku | Ya (hanya jika `maxKnowledge=1`) | Tidak |
| Cocok untuk CAG | Ya, konteks kecil | Butuh banyak artikel → token besar |

---

## 5. Metrik Evaluasi — `cag/similarity.py`

Menggunakan **cosine similarity antar sentence embedding** (bukan BERTScore asli):

```python
bert_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def bert(response, ground_truth):
    # Encode jawaban model & ground truth jadi vector
    emb_response = bert_model.encode(response)
    emb_truth    = bert_model.encode(ground_truth)

    # Ukur kemiripan arah vector (range: -1 sampai 1)
    return cosine_similarity(emb_response, emb_truth)
```

**Cara membaca nilai:** `Semantic Similarity: 0.85` = vektor embedding jawaban model
dan ground truth punya kemiripan 85%. Nilai > 0.7 umumnya dianggap jawaban yang relevan.

---

## Ringkasan Keseluruhan Alur Eksperimen

```
downloads.sh      → download dataset squad + hotpotqa ke ./datasets/
      ↓
.env              → isi HF_TOKEN (wajib), API key lain opsional
      ↓
kvcache1.py       → CAG: preprocess semua dok → KV Cache → generate per Q
rag.py            → RAG: build index → retrieve per Q → generate per Q
      ↓
result_*.txt      → per pertanyaan : similarity, cache_time, generate_time
                  → akhir file     : rata-rata semua metrik
```

### Yang dibandingkan antara CAG dan RAG:

| Metrik | Keterangan |
|---|---|
| `Semantic Similarity` | Kualitas jawaban vs ground truth (semakin tinggi semakin baik) |
| `prepare_time` | Waktu setup sebelum pertanyaan dimulai |
| `generate_time` | Waktu generate jawaban per pertanyaan |
| `retrieve_time` (RAG) | Waktu retrieve dokumen per pertanyaan (tidak ada di CAG) |

### Command untuk menjalankan eksperimen:

**CAG (TinyLlama):**
```bash
conda activate cag-env310
python ./kvcache1.py \
  --kvcache file \
  --dataset "squad-train" \
  --similarity bertscore \
  --maxKnowledge 3 \
  --maxParagraph 50 \
  --maxQuestion 20 \
  --modelname "TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  --output "./result_kvcache_tinyllama.txt"
```

**RAG (TinyLlama + BM25):**
```bash
conda activate cag-env310
python ./rag.py \
  --index "bm25" \
  --dataset "squad-train" \
  --similarity bertscore \
  --maxKnowledge 3 \
  --maxParagraph 50 \
  --maxQuestion 20 \
  --topk 3 \
  --modelname "TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  --output "./result_rag_tinyllama.txt"
```
