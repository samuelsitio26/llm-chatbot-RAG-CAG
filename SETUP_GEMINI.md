# Setup Gemini API untuk Sistem Rekomendasi Wisata

## ✅ Konfigurasi Sudah Selesai!

Sistem sekarang menggunakan **Google Gemini API** (tidak perlu GPU lokal).

### API Key di `.env`:
```
GEMINI_API_KEY=AIzaSyAAYxSTbxDQWL1RANJwxwHh0O4Z2zf0Sxo
```

## Cara Menjalankan di Server HPC (172.22.222.118):

### Step 1: SSH ke server
```bash
ssh tasi2425112@172.22.222.118 -p 8822
```

### Step 2: Install package google-generativeai
```bash
conda activate llm-rag
pip install google-generativeai
```

### Step 3: Jalankan Backend
```bash
cd ~/test/llm-chatbot-rag
python src/api.py
```

### Step 4: Jalankan Frontend (terminal baru)
```bash
conda activate base
cd ~/test/llm-chatbot-rag/frontend
npm run dev
```

## Keuntungan Gemini API:
- ✅ Tidak butuh GPU lokal
- ✅ Model lebih besar dan pintar (Gemini 2.0 Flash)
- ✅ Response lebih cepat
- ✅ Tidak perlu download model ~5GB
- ✅ Setup lebih mudah

## Model Gemini yang tersedia:
- `gemini-2.0-flash` (default, cepat & efisien)
- `gemini-1.5-pro` (lebih pintar, lebih lambat)
- `gemini-1.5-flash` (balance)

Untuk ganti model, edit `model_name` di `src/model.py`.
