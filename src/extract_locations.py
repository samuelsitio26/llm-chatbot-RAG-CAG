"""
Extract location coordinates (lat/long) from PDF tourism documents
For use with interactive map in asktoba.com
"""

import json
import re
from pathlib import Path
from pypdf import PdfReader
from typing import List, Dict

def extract_coordinates_from_pdf(pdf_path: str) -> List[Dict]:
    """
    Extract location names and coordinates from PDF
    Supports formats:
    - 2.6569, 98.8756
    - 2.6569° N, 98.8756° E
    - Lat: 2.6569, Long: 98.8756
    - Koordinat: 2.6569, 98.8756
    """
    locations = []
    
    try:
        reader = PdfReader(pdf_path)
        full_text = ""
        
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
        
        # Pattern 1: Simple decimal coordinates (most common)
        # Match: 2.6569, 98.8756 or 2.6569,98.8756
        pattern1 = r'(\d+\.\d{3,6})\s*[,;]\s*(\d+\.\d{3,6})'
        
        # Pattern 2: With degree symbol
        # Match: 2.6569° N, 98.8756° E or 2°39'N 98°52'E
        pattern2 = r'(\d+(?:\.\d+)?)[°]\s*(?:\d+[\'′])?\s*[NS][,\s]+(\d+(?:\.\d+)?)[°]\s*(?:\d+[\'′])?\s*[EW]'
        
        # Pattern 3: With labels (Lat/Long, Latitude/Longitude)
        pattern3 = r'(?:Lat(?:itude)?|lat)[:\s]+(-?\d+\.\d+)[,\s]+(?:Long(?:itude)?|Lng|long)[:\s]+(-?\d+\.\d+)'
        
        # Pattern 4: Koordinat label (Indonesian)
        pattern4 = r'[Kk]oordinat[^:]*[:\s]+(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)'
        
        # Pattern 5: GPS coordinates
        pattern5 = r'GPS[:\s]+(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)'
        
        all_patterns = [
            (pattern1, "decimal"),
            (pattern2, "degree"),
            (pattern3, "labeled"),
            (pattern4, "koordinat"),
            (pattern5, "gps")
        ]
        
        for pattern, pattern_type in all_patterns:
            matches = re.finditer(pattern, full_text, re.IGNORECASE)
            
            for match in matches:
                try:
                    lat = float(match.group(1))
                    lng = float(match.group(2))
                    
                    # Validate coordinates are in Toba region
                    # Danau Toba area: roughly 2.0-3.0° N, 98.0-100.0° E
                    if 1.5 < lat < 3.5 and 97.5 < lng < 100.5:
                        # Try to extract location name (text before coordinates)
                        start_pos = max(0, match.start() - 150)
                        end_pos = match.start()
                        context = full_text[start_pos:end_pos]
                        
                        # Extract potential location name
                        # Look for capitalized words or common location patterns
                        name_patterns = [
                            r'([A-Z][a-zA-Z\s]{2,30}(?:Beach|Pantai|Island|Pulau|Lake|Danau|Village|Desa|Town|Kota|Resort|Hotel|Waterfall|Air\s*Terjun)?)',
                            r'(?:Pantai|Pulau|Danau|Desa|Air Terjun|Bukit|Gunung)\s+([A-Za-z\s]+)',
                            r'\"([^\"]+)\"',
                            r'\'([^\']+)\''
                        ]
                        
                        location_name = None
                        for name_pattern in name_patterns:
                            name_matches = re.findall(name_pattern, context)
                            if name_matches:
                                location_name = name_matches[-1].strip()
                                break
                        
                        if not location_name:
                            location_name = f"Location ({lat:.4f}, {lng:.4f})"
                        
                        # Clean up name
                        location_name = re.sub(r'\s+', ' ', location_name).strip()
                        
                        # Avoid duplicates (within 0.001 degree ~ 100m)
                        is_duplicate = False
                        for existing in locations:
                            if abs(existing['lat'] - lat) < 0.001 and abs(existing['lng'] - lng) < 0.001:
                                is_duplicate = True
                                break
                        
                        if not is_duplicate:
                            locations.append({
                                'name': location_name,
                                'lat': lat,
                                'lng': lng,
                                'source': Path(pdf_path).name,
                                'pattern_type': pattern_type
                            })
                            
                except (ValueError, IndexError) as e:
                    continue
        
    except Exception as e:
        print(f"❌ Error processing {pdf_path}: {e}")
    
    return locations


def extract_all_locations(tourism_dir: str = None) -> List[Dict]:
    """Extract coordinates from all PDFs in tourism directory"""
    
    if tourism_dir is None:
        # Auto-detect path
        script_dir = Path(__file__).parent
        tourism_dir = script_dir.parent / "data" / "tourism"
    
    pdf_dir = Path(tourism_dir)
    
    if not pdf_dir.exists():
        print(f"❌ Directory {tourism_dir} not found")
        return []
    
    all_locations = []
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    print(f"📚 Found {len(pdf_files)} PDF files in {pdf_dir}")
    
    for pdf_file in pdf_files:
        print(f"📖 Processing: {pdf_file.name}")
        locations = extract_coordinates_from_pdf(str(pdf_file))
        all_locations.extend(locations)
        print(f"   ✅ Found {len(locations)} locations")
    
    # Remove duplicates based on coordinates
    unique_locations = []
    seen_coords = set()
    
    for loc in all_locations:
        coord_key = f"{loc['lat']:.4f},{loc['lng']:.4f}"
        if coord_key not in seen_coords:
            unique_locations.append(loc)
            seen_coords.add(coord_key)
    
    print(f"\n✅ Total unique locations: {len(unique_locations)}")
    return unique_locations


def get_default_toba_locations() -> List[Dict]:
    """
    Return default Danau Toba landmarks if PDF extraction fails
    Based on well-known tourism destinations
    """
    return [
        {
            "name": "Parapat",
            "lat": 2.6625,
            "lng": 98.9333,
            "source": "default",
            "description": "Kota wisata utama di tepi Danau Toba"
        },
        {
            "name": "Pulau Samosir",
            "lat": 2.6225,
            "lng": 98.8214,
            "source": "default",
            "description": "Pulau vulkanik di tengah Danau Toba"
        },
        {
            "name": "Tuktuk Siadong",
            "lat": 2.6667,
            "lng": 98.8667,
            "source": "default",
            "description": "Kawasan wisata populer dengan hotel dan resto"
        },
        {
            "name": "Tomok",
            "lat": 2.6500,
            "lng": 98.8500,
            "source": "default",
            "description": "Desa wisata dengan makam Raja Sidabutar"
        },
        {
            "name": "Ambarita",
            "lat": 2.6833,
            "lng": 98.8167,
            "source": "default",
            "description": "Situs Batu Kursi Raja dan rumah adat Batak"
        },
        {
            "name": "Simanindo",
            "lat": 2.7167,
            "lng": 98.7833,
            "source": "default",
            "description": "Museum Huta Bolon dan pertunjukan Tor-Tor"
        },
        {
            "name": "Balige",
            "lat": 2.3333,
            "lng": 99.0667,
            "source": "default",
            "description": "Kota bersejarah dengan TB Silalahi Museum"
        },
        {
            "name": "Pangururan",
            "lat": 2.6000,
            "lng": 98.7500,
            "source": "default",
            "description": "Ibu kota Samosir dengan pemandian air panas"
        },
        {
            "name": "Air Terjun Sipiso-piso",
            "lat": 2.9167,
            "lng": 98.5167,
            "source": "default",
            "description": "Air terjun tertinggi di Indonesia (120m)"
        },
        {
            "name": "Tongging",
            "lat": 2.9000,
            "lng": 98.5333,
            "source": "default",
            "description": "Viewpoint indah di utara Danau Toba"
        },
        {
            "name": "Pantai Pasir Putih Parbaba",
            "lat": 2.5833,
            "lng": 98.7667,
            "source": "default",
            "description": "Pantai berpasir putih di Samosir"
        },
        {
            "name": "Bukit Holbung",
            "lat": 2.5667,
            "lng": 98.7833,
            "source": "default",
            "description": "Spot selfie populer dengan pemandangan danau"
        }
    ]


def save_locations_json(locations: List[Dict], output_path: str = None):
    """Save extracted locations to JSON file"""
    
    if output_path is None:
        script_dir = Path(__file__).parent
        output_path = script_dir.parent / "data" / "locations.json"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(locations, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Saved {len(locations)} locations to {output_path}")


def load_locations_json(input_path: str = None) -> List[Dict]:
    """Load locations from JSON file"""
    
    if input_path is None:
        script_dir = Path(__file__).parent
        input_path = script_dir.parent / "data" / "locations.json"
    
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []


if __name__ == "__main__":
    print("=" * 60)
    print("🗺️  Extracting Location Coordinates from PDFs")
    print("=" * 60)
    
    # Try to extract from PDFs
    locations = extract_all_locations()
    
    # If no locations found, use defaults
    if not locations:
        print("\n⚠️  No coordinates found in PDFs")
        print("💡 Using default Danau Toba landmarks...")
        locations = get_default_toba_locations()
    
    # Save to JSON
    save_locations_json(locations)
    
    # Preview
    print("\n📍 Extracted locations:")
    print("-" * 60)
    for loc in locations:
        print(f"  • {loc['name']}")
        print(f"    Coordinates: ({loc['lat']}, {loc['lng']})")
        print(f"    Source: {loc['source']}")
        if 'description' in loc:
            print(f"    Description: {loc['description']}")
        print()
    
    print("=" * 60)
    print(f"✅ Total: {len(locations)} locations saved to data/locations.json")
    print("=" * 60)
