"""
Cache Lifecycle Manager – Toba Tourism Chatbot
===============================================

Policy (dijalankan setiap periode, default setiap 7 hari):

  HAPUS  : last_accessed > MAX_AGE_DAYS (21) DAN access_count < MIN_ACCESS (5)
             → "low access token" + "time 3 week" + "under 5 access token"

  PROMOSI: access_count >= MIN_ACCESS (5) DAN net_likes >= 1
             → tambah otomatis ke FAQ – sering ditanya DAN disukai pengguna

  HAPUS (populer tapi dibenci): access_count >= MIN_ACCESS DAN net_likes < 0
             → respons buruk yang populer – BAHAYA, harus dihapus

  TAHAN  : access_count >= MIN_ACCESS DAN net_likes == 0
             → populer tapi belum ada sinyal kualitas, tunggu feedback lebih lanjut

  SIMPAN : semua selain kondisi di atas (masih aktif & belum populer)

Staging eviction: entry staging dengan net_likes <= -3 dihapus langsung.

Cara pakai:
  python src/manage_cache.py                  # dry-run (lihat laporan, tidak ada perubahan)
  python src/manage_cache.py --execute        # terapkan perubahan
  python src/manage_cache.py --report         # laporan saja

Di-schedule via Windows Task Scheduler (weekly) atau cron VPS:
  0 2 * * 1  cd /var/www/toba-chatbot && .venv/bin/python src/manage_cache.py --execute
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List

# ── Path setup ──────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(BASE_DIR, "database", "kv_cache", "cache_index.json")
FAQ_FILE   = os.path.join(BASE_DIR, "database", "FAQ",      "faq_tourism.json")
LOG_DIR    = os.path.join(BASE_DIR, "logs")

# ── Policy defaults ────────────────────────────────────────────
# Semua nilai ini bisa di-override per-panggilan via parameter fungsi.
DEFAULT_MAX_AGE_DAYS           = 21   # hari tanpa akses → kandidat hapus
DEFAULT_MIN_ACCESS_FOR_KEEP    = 5    # access_count minimum agar tidak dihapus
DEFAULT_MIN_ACCESS_FOR_PROMOTE = 5    # access_count minimum untuk masuk FAQ
DEFAULT_MAX_ENTRIES            = 500  # maksimum entri di confirmed cache; 0 = tidak dibatasi
STAGING_DISLIKE_EVICT          = -3   # net_likes ≤ ini → staging entry langsung dihapus

# Alias tetap (legacy) — dipakai oleh kode lama
MAX_AGE_DAYS           = DEFAULT_MAX_AGE_DAYS
MIN_ACCESS_FOR_KEEP    = DEFAULT_MIN_ACCESS_FOR_KEEP
MIN_ACCESS_FOR_PROMOTE = DEFAULT_MIN_ACCESS_FOR_PROMOTE


# ════════════════════════════════════════════════════════════════════════════
# Helper I/O
# ════════════════════════════════════════════════════════════════════════════

def _load_cache() -> Dict:
    if not os.path.exists(CACHE_FILE):
        return {"cache": {}, "access_count": {}}
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_cache(data: Dict) -> None:
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_faq() -> List[Dict]:
    if not os.path.exists(FAQ_FILE):
        return []
    with open(FAQ_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_faq(faqs: List[Dict]) -> None:
    os.makedirs(os.path.dirname(FAQ_FILE), exist_ok=True)
    with open(FAQ_FILE, "w", encoding="utf-8") as f:
        json.dump(faqs, f, ensure_ascii=False, indent=2)


def _write_log(report: Dict) -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    ts         = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path   = os.path.join(LOG_DIR, f"cache_lifecycle_{ts}.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return log_path


# ════════════════════════════════════════════════════════════════════════════
# Utility: keyword extraction & category detection
# ════════════════════════════════════════════════════════════════════════════

_STOPWORDS = {
    'di', 'ke', 'dari', 'yang', 'untuk', 'dan', 'atau', 'dengan', 'ini',
    'itu', 'ada', 'tidak', 'bisa', 'apa', 'mana', 'bagaimana', 'saya',
    'kamu', 'tolong', 'cari', 'rekomendasi', 'terbaik', 'adalah', 'kan',
    'dong', 'ya', 'nih', 'juga', 'kami', 'mereka', 'tersebut',
}

_CATEGORY_MAP = [
    ('pantai',      ['pantai', 'snorkeling', 'diving', 'beach']),
    ('mountain',    ['gunung', 'hiking', 'trekking', 'bukit']),
    ('family',      ['keluarga', 'anak', 'family']),
    ('culture',     ['budaya', 'museum', 'sejarah', 'adat', 'batak', 'ulos']),
    ('culinary',    ['kuliner', 'makan', 'resto', 'warung', 'cafe', 'arsik', 'saksang']),
    ('accommodation', ['hotel', 'penginapan', 'homestay', 'villa', 'resort']),
    ('budget',      ['biaya', 'budget', 'harga', 'murah', 'hemat', 'tarif']),
    ('toba',        ['toba', 'samosir', 'parapat', 'balige', 'danau', 'tomok', 'tuktuk']),
    ('transport',   ['transportasi', 'ferry', 'angkot', 'bus', 'rental', 'kendaraan']),
]


def _extract_keywords(text: str, max_kw: int = 6) -> List[str]:
    words = [w.lower().strip("?!.,;\"'") for w in text.split()]
    seen, result = set(), []
    for w in words:
        if len(w) > 3 and w not in _STOPWORDS and w not in seen:
            seen.add(w)
            result.append(w)
    return result[:max_kw]


def _detect_category(query: str) -> str:
    q = query.lower()
    for category, keywords in _CATEGORY_MAP:
        if any(k in q for k in keywords):
            return category
    return 'general'


# ════════════════════════════════════════════════════════════════════════════
# Core lifecycle logic
# ════════════════════════════════════════════════════════════════════════════

def run_lifecycle(
    execute: bool = False,
    verbose: bool = True,
    max_age_days: int = None,
    max_entries: int = None,
    min_access: int = None,
) -> Dict:
    """
    Analisis semua entry cache dan terapkan policy lifecycle.

    Args:
        execute     : False = dry-run, True = terapkan perubahan
        verbose     : cetak laporan ke stdout
        max_age_days: hari tanpa akses sebelum jadi kandidat hapus  (default: 21)
        max_entries : batas maksimum entri confirmed cache; 0 = tidak dibatasi (default: 500)
        min_access  : threshold akses minimum agar tidak dihapus / untuk promosi (default: 5)

    Policy (confirmed cache):
      - access_count >= min_access DAN net_likes >= 1  → PROMOSI ke FAQ
      - access_count >= min_access DAN net_likes < 0   → HAPUS (populer tapi buruk)
      - access_count >= min_access DAN net_likes == 0  → TAHAN (belum ada sinyal)
      - age > max_age_days DAN count < min_access      → HAPUS
      - len(cache) > max_entries → evict oldest+least-accessed dulu
      - selainnya                                      → SIMPAN
    """
    # Gunakan default jika tidak diisi
    if max_age_days is None:
        max_age_days = DEFAULT_MAX_AGE_DAYS
    if max_entries is None:
        max_entries = DEFAULT_MAX_ENTRIES
    if min_access is None:
        min_access = DEFAULT_MIN_ACCESS_FOR_KEEP

    now  = datetime.now()

    data         = _load_cache()
    cache        = data.get("cache", {})
    access_count = data.get("access_count", {})
    staging      = data.get("staging", {})

    faqs               = _load_faq()
    existing_questions = {f["question"].lower().strip() for f in faqs}

    to_delete:  List[Dict] = []
    to_promote: List[Dict] = []
    to_keep:    List[Dict] = []
    to_evict_size: List[Dict] = []  # evicted purely because cache is too large
    staging_evict: List[str] = []

    # ── Klasifikasi setiap entry ─────────────────────────────────────────────
    for query_hash, item in cache.items():
        count = access_count.get(query_hash, item.get("access_count", 0))

        try:
            ts_str        = item.get("last_accessed") or item.get("created_at")
            last_accessed = datetime.fromisoformat(ts_str)
        except Exception:
            last_accessed = now - timedelta(days=999)

        age_days       = (now - last_accessed).days
        original_query = item.get("query", "")

        base = {
            "hash":         query_hash,
            "query":        original_query,
            "access_count": count,
            "age_days":     age_days,
        }

        net_likes = item.get("total_likes", 0) - item.get("total_dislikes", 0)

        if count >= min_access:
            if net_likes >= 1:
                # Populer DAN disukai → promosi ke FAQ
                if original_query.lower().strip() not in existing_questions:
                    to_promote.append({**base, "response": item.get("response", "")})
                else:
                    to_keep.append({**base, "reason": "popular (already in FAQ)"})
            elif net_likes < 0:
                # Populer tapi banyak dislike → HAPUS
                to_delete.append({**base, "reason": f"popular but disliked (net_likes={net_likes})"})
            else:
                # Populer tapi belum ada sinyal kualitas → tahan
                to_keep.append({**base, "reason": f"popular, awaiting quality signal (net_likes={net_likes})"})

        elif age_days > max_age_days and count < min_access:
            # Tua + jarang → hapus
            to_delete.append({**base, "reason": f"old+low-access (age={age_days}d, count={count})"})

        else:
            to_keep.append({**base, "reason": f"active (age={age_days}d, count={count})"})

    # ── Eviction karena cache terlalu besar (max_entries) ─────────────────
    delete_hashes = {item["hash"] for item in to_delete}
    remaining_count = len(cache) - len(delete_hashes)
    if max_entries > 0 and remaining_count > max_entries:
        overflow = remaining_count - max_entries
        # Urutkan yang akan di-keep berdasarkan (access_count ASC, age_days DESC)
        # → yang paling jarang dan paling tua di-evict lebih dulu
        keep_sorted = sorted(
            [i for i in to_keep if i["hash"] not in delete_hashes],
            key=lambda x: (x["access_count"], -x["age_days"])
        )
        for item in keep_sorted[:overflow]:
            to_keep.remove(item)
            to_evict_size.append({**item, "reason": f"cache over limit ({remaining_count}/{max_entries})"})
            delete_hashes.add(item["hash"])

    # ── Staging eviction ─────────────────────────────────────────────
    for s_hash, s_item in staging.items():
        net = s_item.get("total_likes", 0) - s_item.get("total_dislikes", 0)
        if net <= STAGING_DISLIKE_EVICT:
            staging_evict.append(s_hash)

    all_to_delete = to_delete + to_evict_size

    # ── Laporan ─────────────────────────────────────────────────────────────
    if verbose:
        _print_report(cache, staging, all_to_delete, to_promote, to_keep,
                      staging_evict, to_evict_size, execute,
                      max_age_days, max_entries, min_access)

    # ── Eksekusi ─────────────────────────────────────────────────────────
    promoted_count = 0
    if execute:
        # 1. Hapus entries lama + jarang diakses + overflow size
        for item in all_to_delete:
            h = item["hash"]
            cache.pop(h, None)
            access_count.pop(h, None)

        # 2. Evict staging entries yang banyak di-dislike
        for h in staging_evict:
            staging.pop(h, None)

        # 3. Promosi entries populer + disukai → FAQ
        for item in to_promote:
            query    = item["query"]
            response = item["response"]
            if not query or not response:
                continue

            new_faq = {
                "category":                  _detect_category(query),
                "question":                  query,
                "answer":                    response[:1000],
                "keywords":                  _extract_keywords(query),
                "priority":                  "high",
                "auto_promoted":             True,
                "promoted_at":               now.isoformat(),
                "promoted_from_cache_count": item["access_count"],
            }
            faqs.append(new_faq)
            existing_questions.add(query.lower().strip())
            promoted_count += 1

        # 4. Simpan
        data["cache"]        = cache
        data["access_count"] = access_count
        data["staging"]      = staging
        _save_cache(data)
        _save_faq(faqs)

        if verbose:
            print(f"\n✅ Perubahan diterapkan:")
            print(f"   🗑️  Dihapus  : {len(all_to_delete)} entries")
            print(f"   🗑️  Staging evicted: {len(staging_evict)} entries")
            print(f"   ⭐  Dipromosi: {promoted_count} entries → FAQ")
            print(f"   📋  FAQ total: {len(faqs)} entries")

    report = {
        "timestamp":         now.isoformat(),
        "policy": {
            "max_age_days":           max_age_days,
            "min_access_for_keep":    min_access,
            "min_access_for_promote": min_access,
            "max_entries":            max_entries,
            "staging_dislike_evict":  STAGING_DISLIKE_EVICT,
            "promotion_requires_net_likes_gte": 1,
        },
        "summary": {
            "total_cache_entries":   len(cache),
            "total_staging_entries": len(staging),
            "to_delete":             len(all_to_delete),
            "evicted_size":          len(to_evict_size),
            "staging_evict":         len(staging_evict),
            "to_promote":            len(to_promote),
            "to_keep":               len(to_keep),
            "executed":              execute,
        },
        "details": {
            "deleted":  all_to_delete,
            "promoted": [
                {"query": i["query"], "access_count": i["access_count"]}
                for i in to_promote
            ],
        }
    }
    return report


def _print_report(cache, staging, to_delete, to_promote, to_keep,
                  staging_evict, to_evict_size, execute,
                  max_age_days, max_entries, min_access):
    """Cetak laporan ke stdout."""
    print("")
    print("=" * 65)
    print("🔄  CACHE LIFECYCLE REPORT")
    print("=" * 65)
    print(f"   Policy  : hapus jika > {max_age_days} hari DAN akses < {min_access}")
    print(f"   Promosi : akses >= {min_access} DAN net_likes >= 1 → masuk FAQ")
    print(f"   Populer buruk: akses >= {min_access} DAN net_likes < 0 → HAPUS")
    print(f"   Max entries: {max_entries if max_entries > 0 else 'tidak dibatasi'}")
    print(f"   Staging evict: net_likes <= {STAGING_DISLIKE_EVICT} → hapus dari staging")
    print(f"   Cache   : {CACHE_FILE}")
    print(f"   FAQ     : {FAQ_FILE}")
    print("─" * 65)
    print(f"   Total confirmed : {len(cache)}")
    print(f"   Total staging   : {len(staging)}")
    print(f"   🗑️  Akan dihapus (tua/jarang)  : {len(to_delete) - len(to_evict_size)}")
    print(f"   🗑️  Akan di-evict (over limit) : {len(to_evict_size)}")
    print(f"   🗑️  Staging akan di-evict      : {len(staging_evict)}")
    print(f"   ⭐  Akan dipromosi ke FAQ       : {len(to_promote)}")
    print(f"   ✅  Tetap disimpan              : {len(to_keep)}")

    if to_delete:
        print(f"\n{'─'*40}")
        print("🗑️  ENTRIES YANG AKAN DIHAPUS  (tua + jarang diakses / populer tapi dibenci):")
        for item in to_delete[:20]:
            reason = item.get('reason', '')
            q = item['query'][:50] + ("…" if len(item['query']) > 50 else "")
            print(f"   [{item['age_days']:>3}d  {item['access_count']:>2}x]  {q}  ({reason})")
        if len(to_delete) > 20:
            print(f"   … dan {len(to_delete)-20} lainnya")

    if to_promote:
        print(f"\n{'─'*40}")
        print("⭐  ENTRIES YANG AKAN DIPROMOSI KE FAQ  (sering ditanya):")
        for item in to_promote[:20]:
            q = item['query'][:55] + ("…" if len(item['query']) > 55 else "")
            print(f"   [{item['access_count']:>3}x  {item['age_days']:>2}d]  {q}")
        if len(to_promote) > 20:
            print(f"   … dan {len(to_promote)-20} lainnya")

    if not execute:
        print(f"\n⚠️  DRY-RUN – tidak ada perubahan. Gunakan --execute untuk menerapkan.")
    print("=" * 65)


# ════════════════════════════════════════════════════════════════════════════
# API: bisa dipanggil dari kode lain (mis. api.py endpoint admin)
# ════════════════════════════════════════════════════════════════════════════

def get_lifecycle_report(
    max_age_days: int = None,
    max_entries: int = None,
    min_access: int = None,
) -> Dict:
    """Kembalikan laporan lifecycle tanpa mengeksekusi. Untuk endpoint admin."""
    return run_lifecycle(execute=False, verbose=False,
                        max_age_days=max_age_days,
                        max_entries=max_entries,
                        min_access=min_access)


def execute_lifecycle(
    max_age_days: int = None,
    max_entries: int = None,
    min_access: int = None,
) -> Dict:
    """Jalankan lifecycle dan terapkan semua perubahan. Untuk endpoint admin."""
    report = run_lifecycle(execute=True, verbose=False,
                          max_age_days=max_age_days,
                          max_entries=max_entries,
                          min_access=min_access)
    _write_log(report)
    return report


# ════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Cache Lifecycle Manager – hapus cache lama, promosi FAQ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  python src/manage_cache.py               # dry-run, lihat laporan
  python src/manage_cache.py --execute     # terapkan: hapus + promosi
  python src/manage_cache.py --report      # hanya laporan (sama dengan default)
        """
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Terapkan perubahan (default: dry-run)"
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Tampilkan laporan saja (dry-run)"
    )
    parser.add_argument(
        "--save-log", action="store_true",
        help="Simpan laporan ke logs/cache_lifecycle_<ts>.json"
    )
    args = parser.parse_args()

    do_execute = args.execute and not args.report
    report = run_lifecycle(execute=do_execute, verbose=True)

    if args.save_log or do_execute:
        log_path = _write_log(report)
        print(f"\n📝 Log disimpan: {log_path}")
