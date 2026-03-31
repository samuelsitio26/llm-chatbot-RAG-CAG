"""
Location Service Module for Toba Tourism Chatbot
=================================================
Centralises ALL location-related logic:
  • Loading & caching locations.json
  • Fuzzy / partial name matching  (generic, not hardcoded to any place)
  • Area-based filtering
  • Haversine distance calculation  (lat/lng → km)
  • Transport & route estimation between two places
  • Coordinate extraction from PDF context
  • Query analysis helpers (single-place, count, destination, transport)
"""

import json
import math
import os
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple


# ════════════════════════════════════════════════════════════════════════════
# Constants
# ════════════════════════════════════════════════════════════════════════════

LOCATIONS_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'database', 'Locations', 'locations.json')
)

# Known area / city keywords around Danau Toba
KNOWN_AREAS = [
    'balige', 'samosir', 'parapat', 'prapat', 'tuktuk', 'tuk tuk',
    'tomok', 'ambarita', 'simanindo', 'pangururan', 'ajibata',
    'lumban julu', 'nainggolan', 'onan runggu', 'sianjur', 'baktiraja',
    'porsea', 'laguboti', 'sipiso-piso', 'sipiso piso', 'haranggaol',
    'tongging', 'merek', 'tampahan', 'siborong-borong', 'tarutung',
    'silalahi', 'muara', 'harian', 'doloksanggul',
]

# Generic type prefixes to strip when matching place names
_TYPE_PREFIX_RE = re.compile(
    r'^(?:tempat\s+)?(?:penginapan|hotel|resort|villa|homestay|cafe|restoran|'
    r'warung|rumah\s+makan|wisata|objek\s+wisata|pantai|air\s+terjun|'
    r'bukit|danau|desa\s+wisata|museum|taman)\s+',
    re.IGNORECASE,
)

# Stop-words to ignore when computing partial name overlap
_STOP_WORDS = frozenset([
    'di', 'ke', 'dari', 'dan', 'yang', 'ini', 'itu', 'ada', 'untuk',
    'atau', 'dengan', 'pada', 'oleh', 'juga', 'saya', 'kamu', 'kami',
    'nya', 'se', 'ber', 'ter', 'kec', 'kab', 'sumatera', 'utara',
])

# Transport mode thresholds (km)
_TRANSPORT_THRESHOLDS = [
    (1.0,  'jalan kaki',      '🚶', '10-15 menit/km'),
    (5.0,  'becak/sepeda',    '🚲', '~15-20 menit'),
    (15.0, 'ojek/grab',       '🏍️', '~15-30 menit'),
    (40.0, 'angkutan umum/travel',  '🚐', '~30-60 menit'),
    (80.0, 'travel/bus',      '🚌', '~1-2 jam'),
    (float('inf'), 'bus antar kota/sewa mobil', '🚗', '~2-4 jam'),
]


# ════════════════════════════════════════════════════════════════════════════
# Data Loading (cached in module-level variable)
# ════════════════════════════════════════════════════════════════════════════

_locations_cache: Optional[List[Dict]] = None


def _load_locations() -> List[Dict]:
    """Load and cache locations.json. Returns empty list on error."""
    global _locations_cache
    if _locations_cache is not None:
        return _locations_cache
    try:
        if not os.path.exists(LOCATIONS_FILE):
            _locations_cache = []
            return _locations_cache
        with open(LOCATIONS_FILE, 'r', encoding='utf-8') as f:
            _locations_cache = json.load(f)
    except Exception as e:
        print(f'⚠️ location_service: failed to load locations.json — {e}')
        _locations_cache = []
    return _locations_cache


def reload_locations() -> None:
    """Force-reload locations.json (call after data changes)."""
    global _locations_cache
    _locations_cache = None
    _load_locations()


def _loc_dict(loc: Dict) -> Dict:
    """Normalise a raw location record into the shape the frontend expects."""
    return {
        'name': loc.get('name'),
        'lat': loc.get('lat'),
        'lng': loc.get('lng'),
        'category': loc.get('category'),
        'rating': loc.get('rating'),
        'price': loc.get('price'),
        'description': loc.get('description', ''),
        'location': loc.get('location', ''),
        'address': loc.get('address', ''),
        'hours': loc.get('hours', ''),
    }


# ════════════════════════════════════════════════════════════════════════════
# Fuzzy / Partial Name Matching   (generic — NOT hardcoded to any name)
# ════════════════════════════════════════════════════════════════════════════

def _significant_words(text: str) -> List[str]:
    """Extract words ≥ 3 chars, lowercased, excluding stop-words."""
    return [
        w for w in re.findall(r'[a-z0-9]+', text.lower())
        if len(w) >= 3 and w not in _STOP_WORDS
    ]


def name_matches(loc_name: str, text: str) -> bool:
    """
    Check whether *text* (response / query) refers to the location *loc_name*.
    Works for exact substrings, partial name overlap, and reverse matching.
    """
    loc_lower = loc_name.lower()
    text_lower = text.lower()

    # 1. Exact substring (either direction)
    if loc_lower in text_lower or text_lower in loc_lower:
        return True

    # 1b. Stripped text (no type prefix) is a substring of the location name
    stripped_text = _TYPE_PREFIX_RE.sub('', text_lower).strip(' ?!.,')
    if stripped_text and len(stripped_text) >= 3 and stripped_text in loc_lower:
        return True

    loc_words = _significant_words(loc_lower)
    text_words = _significant_words(text_lower)

    # 2. All significant words of the location appear in the text
    if loc_words and all(w in text_lower for w in loc_words):
        return True

    # 3. Reverse: most significant words of the text appear in the location name
    #    (handles "pantai bulbul" matching "Pantai Lumban Bulbul")
    if text_words and len(text_words) <= 6:
        hits = sum(1 for w in text_words if w in loc_lower)
        if hits >= 2 and hits >= len(text_words) * 0.5:
            return True

    # 4. SequenceMatcher ratio — catches typos & close abbreviations
    #    Only when both strings are short (avoids false positives on long texts)
    if len(stripped_text) <= 40 and len(loc_lower) <= 60:
        ratio = SequenceMatcher(None, stripped_text, loc_lower).ratio()
        if ratio >= 0.55:
            return True

    return False


def find_location_by_name(query_text: str, threshold: float = 0.0) -> Optional[Dict]:
    """
    Find the single BEST matching location for *query_text*.
    Returns the location dict or None.
    """
    locations = _load_locations()
    if not locations:
        return None

    # Strip type prefixes from query for cleaner matching
    clean_query = _TYPE_PREFIX_RE.sub('', query_text.lower()).strip(' ?!.,')

    best, best_score = None, 0.0
    for loc in locations:
        loc_name = loc.get('name', '')
        if not loc_name:
            continue

        # Quick check for exact/partial match
        if name_matches(loc_name, clean_query):
            # Compute a ranking score
            ratio = SequenceMatcher(None, clean_query, loc_name.lower()).ratio()
            if ratio > best_score:
                best_score = ratio
                best = loc

    if best and best_score >= threshold:
        return _loc_dict(best)
    return None


def match_locations(text: str, count: int = 5) -> List[Dict]:
    """
    Find up to *count* locations whose names appear in *text* (response or query).
    Sorted by rating desc.
    """
    locations = _load_locations()
    matched = [loc for loc in locations if name_matches(loc.get('name', ''), text)]
    matched.sort(key=lambda x: x.get('rating', 0), reverse=True)
    return [_loc_dict(loc) for loc in matched[:count]]


# ════════════════════════════════════════════════════════════════════════════
# Area / Destination Filtering
# ════════════════════════════════════════════════════════════════════════════

def extract_destination(query: str) -> Optional[str]:
    """Return the known area name found in *query*, or None."""
    q = query.lower()
    for area in KNOWN_AREAS:
        if re.search(r'\b' + re.escape(area) + r'\b', q):
            return area
    return None


def get_locations_by_area(destination: str, count: int = 5) -> List[Dict]:
    """Filter locations by destination area. Sorted by rating desc."""
    locations = _load_locations()
    dest = destination.lower()
    matched = [
        loc for loc in locations
        if dest in loc.get('name', '').lower()
        or dest in loc.get('location', '').lower()
        or dest in loc.get('address', '').lower()
        or dest in loc.get('description', '').lower()
    ]
    matched.sort(key=lambda x: x.get('rating', 0), reverse=True)
    return [_loc_dict(loc) for loc in matched[:count]]


def get_top_locations(count: int = 5, category: str = None) -> List[Dict]:
    """Top *count* locations by rating, optionally filtered by category."""
    locations = _load_locations()
    if category:
        locations = [loc for loc in locations if loc.get('category') == category]
    locations = sorted(locations, key=lambda x: x.get('rating', 0), reverse=True)
    return [_loc_dict(loc) for loc in locations[:count]]


# ════════════════════════════════════════════════════════════════════════════
# Haversine Distance
# ════════════════════════════════════════════════════════════════════════════

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Great-circle distance between two points on Earth (in kilometres).
    Uses the Haversine formula.
    """
    R = 6371.0  # Earth radius in km
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lng2 - lng1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def distance_between_locations(name_a: str, name_b: str) -> Optional[Dict]:
    """
    Calculate straight-line distance (km) between two locations found by name.
    Returns dict with distance, transport suggestions, etc. — or None if either
    location cannot be resolved.
    """
    loc_a = find_location_by_name(name_a)
    loc_b = find_location_by_name(name_b)
    if not loc_a or not loc_b:
        return None

    lat_a, lng_a = loc_a.get('lat'), loc_a.get('lng')
    lat_b, lng_b = loc_b.get('lat'), loc_b.get('lng')
    if None in (lat_a, lng_a, lat_b, lng_b):
        return None

    dist = haversine_km(lat_a, lng_a, lat_b, lng_b)
    transport = suggest_transport(dist)

    return {
        'from': loc_a,
        'to': loc_b,
        'distance_km': round(dist, 2),
        'transport': transport,
    }


# ════════════════════════════════════════════════════════════════════════════
# Transport Suggestions
# ════════════════════════════════════════════════════════════════════════════

def suggest_transport(distance_km: float) -> List[Dict]:
    """
    Given a straight-line distance, return appropriate transport modes.
    Actual road distance is typically 1.3-1.5× straight-line, and local roads
    around Toba average ~30-40 km/h, so estimates are *rough*.
    """
    road_factor = 1.4  # road distance ≈ 1.4× haversine
    road_km = distance_km * road_factor
    results = []
    for max_km, mode, icon, est_time in _TRANSPORT_THRESHOLDS:
        if distance_km <= max_km:
            # Estimate travel time based on average speed per mode
            if 'jalan kaki' in mode:
                minutes = road_km / 4.5 * 60  # ~4.5 km/h walking
            elif 'becak' in mode or 'sepeda' in mode:
                minutes = road_km / 12 * 60
            elif 'ojek' in mode:
                minutes = road_km / 30 * 60
            elif 'angkutan' in mode:
                minutes = road_km / 25 * 60
            elif 'bus' in mode and 'antar' not in mode:
                minutes = road_km / 35 * 60
            else:
                minutes = road_km / 40 * 60

            results.append({
                'mode': mode,
                'icon': icon,
                'estimated_time': f'~{int(minutes)} menit' if minutes < 120 else f'~{minutes / 60:.1f} jam',
                'estimated_road_km': round(road_km, 1),
            })
            break  # only the most appropriate mode

    # Always include "ojek/grab" and "sewa mobil" as secondary options
    if distance_km > 1.0 and not any('ojek' in r['mode'] for r in results):
        road_km_ojek = distance_km * road_factor
        min_ojek = road_km_ojek / 30 * 60
        results.append({
            'mode': 'ojek/grab',
            'icon': '🏍️',
            'estimated_time': f'~{int(min_ojek)} menit' if min_ojek < 120 else f'~{min_ojek / 60:.1f} jam',
            'estimated_road_km': round(road_km_ojek, 1),
        })
    if distance_km > 5.0:
        road_km_car = distance_km * road_factor
        min_car = road_km_car / 40 * 60
        results.append({
            'mode': 'sewa mobil / travel',
            'icon': '🚗',
            'estimated_time': f'~{int(min_car)} menit' if min_car < 120 else f'~{min_car / 60:.1f} jam',
            'estimated_road_km': round(road_km_car, 1),
        })

    return results


# ════════════════════════════════════════════════════════════════════════════
# Transport / Route Query Detection
# ════════════════════════════════════════════════════════════════════════════

def is_transport_query(query: str) -> bool:
    """Detect queries asking about transport/route between two places."""
    q = query.lower()
    transport_kw = [
        'dari', 'menuju', 'ke ', 'rute', 'jarak', 'akomodasi',
        'naik apa', 'kendaraan', 'transportasi', 'cara ke',
        'berkendara', 'perjalanan', 'tempuh', 'berapa jauh',
        'berapa km', 'berapa lama',
    ]
    return any(kw in q for kw in transport_kw)


def extract_route_places(query: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract origin and destination from a route / transport query.
    Patterns:
       "dari X ke Y …"
       "dari X menuju Y …"
       "X ke Y naik apa"
       "jarak X ke Y"
       "rute dari X ke Y"
    Returns (origin_name, destination_name) or (None, None).
    """
    q = re.sub(r'\s+', ' ', query).strip(' ?!.,')

    patterns = [
        # "dari X ke/menuju Y"
        r'(?:dari|dr)\s+(.+?)\s+(?:ke|menuju|sampai)\s+(.+?)(?:\s+(?:naik|pakai|menggunakan|berkendara|akomodasi|kendaraan|transport)|\s*[?.,!]?\s*$)',
        # "jarak X ke Y"
        r'(?:jarak|distance)\s+(.+?)\s+(?:ke|menuju|dan|dengan)\s+(.+?)(?:\s*[?.,!]?\s*$)',
        # "rute X ke Y"
        r'(?:rute|route)\s+(?:dari\s+)?(.+?)\s+(?:ke|menuju)\s+(.+?)(?:\s*[?.,!]?\s*$)',
        # "X ke Y naik apa" / "X ke Y berapa km"
        r'^(.+?)\s+(?:ke|menuju)\s+(.+?)\s+(?:naik|pakai|berapa|transport|akomodasi|kendaraan)',
    ]

    for pat in patterns:
        m = re.search(pat, q, re.IGNORECASE)
        if m:
            origin = _TYPE_PREFIX_RE.sub('', m.group(1).strip(' ?!.,')).strip()
            dest = _TYPE_PREFIX_RE.sub('', m.group(2).strip(' ?!.,')).strip()
            if len(origin) >= 3 and len(dest) >= 3:
                return origin, dest

    return None, None


def build_transport_context(origin_name: str, dest_name: str) -> Optional[str]:
    """
    Build a text context block about the route between two places.
    This is injected into the LLM prompt so it can answer transport questions.
    Returns None if either location is unknown.
    """
    result = distance_between_locations(origin_name, dest_name)
    if not result:
        return None

    fr = result['from']
    to = result['to']
    dist = result['distance_km']
    transports = result['transport']

    lines = [
        f"[Data Rute & Transportasi]",
        f"Dari     : {fr['name']}",
        f"  Lokasi : {fr.get('location', '-')}",
        f"  Alamat : {fr.get('address', '-')}",
        f"  Lat/Lng: {fr.get('lat')}, {fr.get('lng')}",
        f"Ke       : {to['name']}",
        f"  Lokasi : {to.get('location', '-')}",
        f"  Alamat : {to.get('address', '-')}",
        f"  Lat/Lng: {to.get('lat')}, {to.get('lng')}",
        f"Jarak garis lurus  : {dist} km",
        f"Estimasi jarak jalan: {round(dist * 1.4, 1)} km",
        f"",
        f"Rekomendasi Transportasi:",
    ]
    for t in transports:
        lines.append(f"  {t['icon']} {t['mode']} — estimasi {t['estimated_time']} ({t['estimated_road_km']} km jalan)")

    return '\n'.join(lines)


# ════════════════════════════════════════════════════════════════════════════
# Query Analysis Helpers  (moved from api.py)
# ════════════════════════════════════════════════════════════════════════════

def is_location_query(query: str) -> bool:
    """Should a map be shown for this query?"""
    q = query.lower()

    location_keywords = [
        'dimana', 'di mana', 'lokasi', 'keberadaan', 'alamat',
        'tempat wisata', 'letak', 'posisi', 'koordinat',
        'cara menuju', 'cara ke', 'rute ke', 'jalan menuju', 'arah ke',
        'peta', 'map', 'titik lokasi', 'terletak', 'berada di', 'ada di mana',
        'kendaraan', 'transportasi', 'bus', 'travel', 'angkutan', 'ferry', 'kapal',
        'naik apa', 'pakai apa', 'pergi ke', 'menuju ke',
        'dari', 'jarak', 'berapa km', 'berapa jauh',
    ]

    recommendation_patterns = [
        r'\d+\s*(tempat|wisata|destinasi|lokasi|pantai|air terjun|danau|bukit|pulau)',
        r'rekomendasi\s*(tempat|wisata|destinasi|pantai|air terjun)',
        r'tempat.*(terbaik|terindah|populer|favorit|bagus)',
        r'wisata.*(terbaik|terindah|populer|favorit|bagus)',
        r'daftar.*(tempat|wisata|destinasi|pantai)',
        r'list.*(tempat|wisata|destinasi|pantai)',
    ]

    if any(kw in q for kw in location_keywords):
        return True
    for pat in recommendation_patterns:
        if re.search(pat, q):
            return True
    if extract_destination(query):
        return True
    return False


def is_single_place_query(query: str) -> bool:
    """Is the user asking about exactly ONE specific place?"""
    q = query.lower().strip()
    single_patterns = [
        r'^(?:dimana|di\s+mana)\s+(?:letak\s+|lokasi\s+|alamat\s+)?\S+',
        r'^(?:lokasi|alamat|letak)\s+\S+',
        r'\S+\s+(?:berada|terletak|ada)\s+(?:di\s+)?(?:mana|dimana)',
        r'^(?:tempat\s+)?(?:penginapan|hotel|restoran|cafe|wisata|rumah\s+makan)\s+\S+\s+(?:berada|dimana|di\s+mana)',
    ]
    list_indicators = [
        r'\d+\s*(?:tempat|lokasi|rekomendasi)',
        r'\bbeberapa\b', r'\bsemua\b', r'\bdaftar\b',
        r'\bapa\s+saja\b', r'\btop\b', r'\bterbaik\b',
    ]
    if any(re.search(p, q) for p in list_indicators):
        return False
    return any(re.search(p, q) for p in single_patterns)


def extract_requested_count(query: str) -> int:
    """How many items does the user want?"""
    q = query.lower()

    if is_single_place_query(query):
        return 1

    # "5 tempat", "3 lokasi", …
    m = re.search(r'(\d+)\s*(tempat|lokasi|rekomendasi|hotel|restoran|wisata)', q)
    if m:
        return int(m.group(1))

    # Indonesian number words
    number_words = {
        'satu': 1, 'dua': 2, 'tiga': 3, 'empat': 4, 'lima': 5,
        'enam': 6, 'tujuh': 7, 'delapan': 8, 'sembilan': 9, 'sepuluh': 10,
    }
    for word, num in number_words.items():
        if word in q:
            return num

    m3 = re.search(r'top\s*(\d+)', q)
    if m3:
        return int(m3.group(1))

    if 'terbaik' in q or 'top' in q:
        return 5
    if 'beberapa' in q:
        return 3
    return 5


# ════════════════════════════════════════════════════════════════════════════
# Coordinate Extraction from RAG Context
# ════════════════════════════════════════════════════════════════════════════

def extract_coordinates_from_context(context: str) -> List[Dict]:
    """Extract lat/lng coordinates from RAG context (PDF content)."""
    coordinates: List[Dict] = []

    # Pattern 1: Lat/Longitude explicit labels
    for m in re.finditer(
        r'(?:Lat(?:itude)?|lat)[\s:]*(-?\d+\.?\d*)[,\s]*(?:Long?(?:itude)?|lng?)[\s:]*(-?\d+\.?\d*)',
        context, re.IGNORECASE,
    ):
        try:
            lat, lng = float(m.group(1)), float(m.group(2))
            if 1.5 <= lat <= 4.0 and 97.0 <= lng <= 100.0:
                start = max(0, m.start() - 100)
                nearby = context[start:m.end() + 100]
                nm = re.search(r'([A-Z][A-Za-z\s]{2,50})[\s\n]*(?:Lat|lat)', nearby)
                name = nm.group(1).strip() if nm else f'Lokasi ({lat:.3f}, {lng:.3f})'
                coordinates.append({'name': name, 'lat': lat, 'lng': lng,
                                    'source': 'pdf_extraction', 'category': 'from_document'})
        except (ValueError, AttributeError):
            continue

    # Pattern 2: Bare coordinate pairs (2.xxxx, 99.xxxx)
    for m in re.finditer(r'(\d+\.\d{4,})\s*[,;]\s*(\d+\.\d{4,})', context):
        try:
            lat, lng = float(m.group(1)), float(m.group(2))
            if 1.5 <= lat <= 4.0 and 97.0 <= lng <= 100.0:
                if not any(abs(c['lat'] - lat) < 0.001 and abs(c['lng'] - lng) < 0.001 for c in coordinates):
                    coordinates.append({'name': f'Lokasi ({lat:.4f}, {lng:.4f})', 'lat': lat, 'lng': lng,
                                        'source': 'pdf_extraction', 'category': 'from_document'})
        except ValueError:
            continue

    return coordinates


# ════════════════════════════════════════════════════════════════════════════
# Resolve Locations for a Chat Response  (main orchestrator used by api.py)
# ════════════════════════════════════════════════════════════════════════════

def resolve_locations(
    query: str,
    response_text: str,
    context: str,
    query_type: str,
    requested_count: int,
) -> List[Dict]:
    """
    Master function: given the chat query, LLM response, RAG context, and
    query classification, return the list of locations for the frontend map.
    """
    destination = extract_destination(query)

    # ── Transport / route queries ────────────────────────────────────────
    if is_transport_query(query):
        origin_name, dest_name = extract_route_places(query)
        if origin_name and dest_name:
            locs = []
            loc_a = find_location_by_name(origin_name)
            loc_b = find_location_by_name(dest_name)
            if loc_a:
                locs.append(loc_a)
            if loc_b:
                locs.append(loc_b)
            if locs:
                print(f"📍 Transport query — {len(locs)} route points")
                return locs

    # ── Tourism queries ──────────────────────────────────────────────────
    if query_type == 'tourism':
        # Step 1: area-based
        if destination:
            area_locs = get_locations_by_area(destination, count=requested_count)
            if area_locs:
                mentioned = [l for l in area_locs if name_matches(l['name'], response_text)]
                result = mentioned if mentioned else area_locs
                print(f"📍 Area '{destination}': {len(result)} locations")
                return result

        # Step 2: match response text
        locs = match_locations(response_text, count=requested_count)
        if locs:
            print(f"📍 Response-match: {len(locs)} locations")
            return locs

        # Step 3: match query text
        locs = match_locations(query, count=requested_count)
        if locs:
            print(f"📍 Query-match: {len(locs)} locations")
            return locs

        # Step 4: top-N fallback
        locs = get_top_locations(count=requested_count)
        print(f"📍 Top-N fallback: {len(locs)} locations")
        return locs

    # ── Non-tourism (hotel / restaurant / transport) ─────────────────────
    if query_type == 'non_tourism':
        # Step 1: match response text against locations.json
        locs = match_locations(response_text, count=requested_count)
        if locs:
            print(f"📍 Non-tourism response-match: {len(locs)} locations")
            return locs

        # Step 2: match query text
        locs = match_locations(query, count=requested_count)
        if locs:
            print(f"📍 Non-tourism query-match: {len(locs)} locations")
            return locs

        # Step 3: PDF coordinate extraction (fallback)
        pdf_locs = extract_coordinates_from_context(context)
        if pdf_locs:
            print(f"📍 PDF extraction: {len(pdf_locs[:requested_count])} locations")
            return pdf_locs[:requested_count]

        if destination:
            area_locs = get_locations_by_area(destination, count=requested_count)
            if area_locs:
                print(f"📍 Dest area fallback '{destination}': {len(area_locs)} locations")
                return area_locs

    # ── General ──────────────────────────────────────────────────────────
    locs = match_locations(response_text, count=requested_count)
    if not locs and destination:
        locs = get_locations_by_area(destination, count=requested_count)
    print(f"💬 General: {len(locs)} locations")
    return locs
