# Blueprint Struktur `Evaluate_Toba.ipynb` (Revisi)

Tujuan blueprint ini: setiap cell punya **satu tanggung jawab jelas**, setiap metrik
**traceable ke rumus Bab 2/3**, dan setiap aproksimasi/ad-hoc choice **ditulis eksplisit**
di markdown (bukan disembunyikan di komentar kode).

Urutan section di bawah = urutan cell di notebook. Tiap section berisi:
- Markdown cell: apa yang dijelaskan, termasuk rujukan rumus/sitasi
- Code cell: apa isinya (pseudocode/poin), termasuk catatan perbaikan dari revisi dosen

---

## SECTION 0 — Metodologi & Daftar Metrik (markdown only)

**Markdown:**
- Tabel metrik lengkap: nama metrik | rumus (nomor eq di Bab 2) | sitasi sumber |
  status implementasi (`exact` / `approximation`) | alasan jika approximation.
- Tabel ini jadi "kontrak" — setiap metrik di bawah harus merujuk balik ke baris ini.
- Tegaskan: dataset 200 query = 100 FAQ (punya GT + key points) + 100 questioner (tanpa GT).
  Sebutkan **N efektif per metrik** akan dilaporkan terpisah (lihat Section 9).

> Ini langsung menjawab catatan dosen "harus paham secara keseluruhan kode programnya"
> — karena semua keputusan implementasi sudah didaftar di satu tempat sebelum kode ditulis.

---

## SECTION 1 — Setup Environment

**Markdown:** daftar dependency + alasan (mis. kenapa `bert-score`, kenapa `nltk`).

**Code:**
- Install & import (sama seperti sekarang).
- Tambahan: import client untuk LLM-as-Judge (bisa reuse `GeminiChatModel`).
- Tambahan: set `RANDOM_SEED` global di satu tempat (jangan tersebar di banyak cell).

---

## SECTION 2 — Load Model & Encoder

**Markdown:**
- LLM generatif: Gemini 2.5 Flash — dipakai untuk (a) jawaban sistem, (b) ekstraksi
  key points, (c) LLM-as-Judge.
- Encoder embedding: `paraphrase-multilingual-MiniLM-L12-v2`.
- **BERTScore model: `lang="id"`** — jelaskan model apa yang dipakai untuk Bahasa
  Indonesia, sitasi (mis. paper BERTScore + catatan model multilingual yang dipakai).

**Code:**
- Load `gemini`, `encoder`.
- **Fix bug**: deklarasikan konstanta `BERTSCORE_LANG = "id"` di sini, dipakai global
  di Section 8 (jangan hardcode `"en"` lagi).

---

## SECTION 3 — Build Knowledge Base & CAG System

Sama seperti sekarang (load PDF, build FAISS, init `CAGSystem`). Tidak banyak perubahan
struktural — fokus ke korektnes path & cache state, bukan metrik.

---

## SECTION 4 — Dataset Construction

### 4a. FAQ dataset (100, dengan ground truth)

**Markdown:** sumber data (`dataset_faq.json`), validasi oleh Dinas Pariwisata + dosen
ahli (QWK) — sebutkan ini sebagai bukti kualitas GT.

**Code:** load `dataset_faq.json` apa adanya (tidak banyak berubah).

### 4b. Ekstraksi Key Points K (PENGGANTI `_extract_keywords`)

**Markdown — INI YANG PALING PENTING UNTUK REVISI "K":**
- Jelaskan ulang definisi K dari Bab 2 eq 2.6/2.25: K = {k₁,...,kₙ} dihasilkan oleh LLM
  dari ground truth, n **tidak dibatasi** (sesuai jumlah fakta yang memang ada).
- Tulis prompt yang dipakai untuk ekstraksi K (verbatim, supaya reproducible).
- Sitasi: rujukan [25] sebagai dasar metode "LLM-generated key points".

**Code:**
```
def extract_key_points(ground_truth: str) -> list[str]:
    """LLM-based extraction. n tidak fixed, ditentukan isi GT."""
    prompt = f"""
    Identifikasi seluruh poin fakta penting (key points) dari teks berikut.
    Setiap poin = satu fakta atomik, singkat, tidak overlap.
    Kembalikan sebagai JSON list of string.

    Teks:
    {ground_truth}
    """
    resp = gemini.generate(prompt)
    return json.loads(resp)  # list panjang n, n bervariasi per item
```
- Jalankan untuk 100 GT FAQ → simpan `kw` (rename jadi `key_points` biar jelas) ke file
  cache JSON (`database/FAQ/key_points_cache.json`) supaya **tidak perlu generate ulang**
  tiap kali notebook dijalankan (hemat biaya API + reproducible).
- Markdown tambahan: tampilkan 2–3 contoh GT vs K hasil ekstraksi, untuk QA manual cepat.

### 4c. Questioner dataset (100, tanpa ground truth)

**Markdown:** jelaskan kenapa subset ini tidak punya `gt`/`K`, dan bahwa metrik untuk
subset ini akan ditangani via jalur **terpisah** (Section 8b — LLM-as-Judge / RAGAS),
bukan dipaksa NaN tanpa penjelasan.

**Code:** sama seperti sekarang (sampling 100 dari `dataset_questioner.json`).

### 4d. Gabungan dataset + ringkasan

Sama seperti sekarang, tapi tambahkan print eksplisit:
`"Metrik berbasis K (Completeness/Recall/EM/BERTScore) → N=100 (FAQ only)"`
`"Metrik berbasis LLM-Judge/RAGAS → N=100 (Questioner only)"`
`"Metrik latency/relevance/hallucination-context → N=200 (semua)"`

---

## SECTION 5 — Inference Functions

Sama seperti sekarang (`pure_cag_infer`, `rag_infer`, `cag_infer`). Tidak ada
perubahan logika, hanya pastikan tiap hasil menyimpan `ctx` mentah (untuk dipakai
LLM-as-Judge nanti).

---

## SECTION 6 — Definisi Metrik (1 markdown + 1 code per metrik)

Pertahankan pola "1 markdown rumus, 1 code implementasi" yang sudah ada — itu bagus.
Yang berubah hanya **isi** beberapa fungsi + markdown-nya menyebut status approx/exact.

| # | Metrik | Markdown tambahan | Perubahan code |
|---|--------|--------------------|----------------|
| 1 | Response Time Avg | - | tidak berubah |
| 2 | Cache Hit Rate | - | tidak berubah |
| 3 | Speedup Factor | - | tidak berubah |
| 4 | **Answer Relevance** | Tulis ulang: rumus asli butuh LLM generate n pertanyaan dari jawaban → cosine ke query asli. Sebutkan implementasi saat ini = **approximation** (cosine langsung resp-vs-query) + alasan (biaya API), atau **implementasikan penuh** (lihat kode di bawah) | Pilih salah satu: (a) beri label jelas "Relevance Score (cosine approx)" di semua tabel/plot, ATAU (b) implementasikan generate-question-then-compare seperti rumus asli |
| 5 | Exact Match | - | tidak berubah |
| 6 | **EIR** | Jelaskan unit pencocokan yang dipakai (kata vs kalimat) + kenapa | Jika tetap word-level, beri nama metrik "EIR (word-overlap approx)" di output |
| 7 | **RAG Recall** | sama seperti EIR | sama seperti EIR |
| 8 | **BERTScore F1** | sebutkan `lang=BERTSCORE_LANG` (dari Section 2) | **fix bug**: gunakan `lang=BERTSCORE_LANG`, bukan hardcode `"en"` |
| 9 | **Completeness** | Tulis ulang sesuai eq 2.6/2.25: per key point kᵢ, cek "covers" via LLM-judge | Implementasi baru (lihat 6.9 di bawah) |
| 10 | **Hallucination** | Tulis ulang sesuai eq 2.7: per kᵢ, cek "contradicts" via LLM-judge — **bukan** `1 - cosine` | Implementasi baru (lihat 6.10), atau jika tetap pakai cosine, ganti nama jadi "Semantic Distance (proxy)" dan jangan sebut "Hallucination/contradiction" |

### 6.9 — Completeness (LLM-Judge per key point)

```python
def completeness_llm(answer: str, key_points: list[str]) -> float:
    """Comp(A,K) sesuai eq 2.6 — LLM judge per key point."""
    if not key_points or not answer:
        return float('nan')
    covered = 0
    for kp in key_points:
        prompt = f"""
        Jawaban: "{answer}"
        Key point: "{kp}"
        Apakah jawaban di atas mencakup (covers) key point ini secara akurat
        dan tanpa kesalahan fakta? Jawab hanya: YA atau TIDAK.
        """
        verdict = gemini.generate(prompt).strip().upper()
        if verdict.startswith("YA"):
            covered += 1
    return covered / len(key_points)
```
- Catatan biaya: 100 query × rata-rata n key points → bisa banyak panggilan LLM.
  Mitigasi: batch beberapa key point dalam satu prompt (kembalikan JSON list YA/TIDAK).

### 6.10 — Hallucination (LLM-Judge per key point, eq 2.7)

```python
def hallucination_llm(answer: str, key_points: list[str]) -> float:
    if not key_points or not answer:
        return float('nan')
    contradicted = 0
    for kp in key_points:
        prompt = f"""
        Jawaban: "{answer}"
        Fakta referensi: "{kp}"
        Apakah jawaban di atas BERTENTANGAN (contradicts) langsung dengan fakta ini?
        Jawab hanya: YA atau TIDAK.
        """
        verdict = gemini.generate(prompt).strip().upper()
        if verdict.startswith("YA"):
            contradicted += 1
    return contradicted / len(key_points)
```

**Catatan Irrelevancy (opsional, eq 2.8):** kalau mau lengkapi tabel sesuai Bab 2,
`Irr = 1 - Comp - Hallu` tinggal dihitung dari dua fungsi di atas — tidak butuh
fungsi/LLM call tambahan.

---

## SECTION 7 — LLM-as-Judge & RAGAS untuk Subset Questioner (BARU)

**Markdown:**
- Jelaskan kenapa subset ini perlu jalur evaluasi sendiri (tidak ada GT/K).
- Pilih salah satu (atau keduanya, dibandingkan):
  1. **LLM-as-Judge rubrik manual** — skor 1–5 untuk: relevansi jawaban thd pertanyaan,
     kelengkapan jawaban thd konteks retrieval, ada/tidaknya klaim di luar konteks.
  2. **RAGAS** — `faithfulness` (klaim jawaban vs konteks) dan `answer_relevancy`
     (generate-question-then-compare, ini adalah implementasi resmi dari rumus
     Answer Relevance Bab 2.4.5.5 — sehingga sekaligus bisa dipakai untuk memperbaiki
     poin 6.4 di atas untuk SEMUA 200 query, bukan cuma questioner).

**Code (contoh pakai RAGAS):**
```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy
from datasets import Dataset

ragas_data = Dataset.from_dict({
    "question":  [r['query'] for r in cag_res],
    "answer":    [r['resp'] for r in cag_res],
    "contexts":  [[r['ctx']] for r in cag_res],
})
ragas_result = evaluate(ragas_data, metrics=[faithfulness, answer_relevancy], llm=...)
```

> Catatan: RAGAS butuh konfigurasi LLM/embedding wrapper-nya sendiri (LangChain-compatible).
> Karena `gemini` sudah dipakai via Vertex/REST custom, perlu wrapper tipis ke
> interface LangChain LLM agar kompatibel — ini satu cell tambahan tersendiri.

---

## SECTION 8 — Evaluation Loop (200 query)

Struktur loop tetap sama (per-query: Pure CAG → Pure RAG → Hybrid), tapi:
- `_compute_metrics()` sekarang memanggil `completeness_llm` / `hallucination_llm`
  HANYA untuk item dengan `key_points` (FAQ subset) — tidak berubah secara struktur,
  hanya isi fungsi.
- Tambahkan pemanggilan RAGAS/LLM-Judge (Section 7) sebagai **batch step terpisah
  setelah loop**, sama seperti pola BERTScore batch yang sudah ada sekarang
  (cell 39) — supaya tidak memperlambat loop utama dan mudah di-retry kalau gagal.

---

## SECTION 9 — Aggregation & Pelaporan N per Metrik

**Markdown:**
- Tabel ringkasan: untuk setiap metrik, tampilkan **N (jumlah query yang dipakai)**
  selain nilai rata-ratanya. Ini langsung menjawab potensi pertanyaan dosen
  "completeness dihitung dari berapa data, kok bisa dapat angka segini".

**Code:**
```python
def calc_metrics(results, key_for_n=None):
    ...
    # tambahkan di output:
    summary['comp_n']   = len(_collect('comp'))
    summary['recall_n'] = len(_collect('recall'))
    summary['bert_n']   = len(_collect('bert'))
    summary['em_n']     = len(_collect('em'))
```

---

## SECTION 10 — Visualisasi (tetap, tambah anotasi N)

Sama seperti sekarang, tapi setiap bar chart untuk metrik berbasis K (Completeness,
EM, Recall, BERTScore) diberi anotasi kecil "N=100 (FAQ subset)" di judul/caption —
supaya pembaca skripsi tidak salah kira ini dari 200 query.

---

## SECTION 11 — Statistical Significance Testing

Tidak berubah secara struktural. Pastikan `paired_ttest`/`cohens_d` hanya jalan pada
pasangan yang N-nya match (sudah NaN-aware di kode sekarang — pertahankan).

---

## SECTION 12 — Save & Export

Tidak berubah, tapi tambahkan field `bertscore_lang`, `key_points_method`,
`completeness_method`, `hallucination_method` ke `summary_export` JSON — supaya
metadata metodologi ikut tersimpan bersama angka hasil (memudahkan audit ulang).

---

## Prioritas Eksekusi (kalau mau dikerjakan bertahap)

1. **Section 2 (fix `lang="id"`)** — paling murah, paling kritikal, ulangi BERTScore.
2. **Section 4b (key points via LLM)** — fondasi untuk Completeness & Hallucination baru.
3. **Section 6.9 & 6.10 (Completeness/Hallucination LLM-judge)** — pakai key points dari (2).
4. **Section 9 (laporkan N per metrik)** — murah, langsung menjawab pertanyaan dosen soal "completeness prosesnya seperti apa".
5. **Section 7 (RAGAS/LLM-Judge untuk questioner)** — paling mahal waktu/biaya, kerjakan terakhir.
6. **Section 6.4, 6.6, 6.7 (Relevance/EIR/Recall)** — boleh dibiarkan sebagai *approximation* asal diberi label jujur di markdown & output, kecuali dosen secara eksplisit minta diimplementasi penuh.
