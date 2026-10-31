import csv
import urllib.request
import urllib.error
import time
import re

FEED_URL = "https://www.btswholesaler.com/generatefeedbts?user_id=1429150&pass=Avedore556%2C&format=csv&language_code=en-GB"

# 1. EXCLUSIONS: Strictly block items you fulfill yourself
EXCLUDED_PHRASES = ["YARA", "ASAD", "CLUB DE NUIT"]

# 2. PRIORITY BRAND: Grab 100% of Afnan products available
PRIMARY_BRAND = "AFNAN"

# 3. EXACT TOP-SELLING PERFUME NAMES (Brand + Flagship lines to guarantee)
EXACT_BEST_SELLERS = [
    # French Avenue / Fragrance World
    "LIQUID BRUN", "VULCAN FEU", "ROYAL BLEND", "BARAKKAT ROUGE", 
    # Lattafa Bestsellers (Excluding Yara & Asad)
    "KHAMRAH", "KHAMRAH QAHWA", "ECLAIRE", "FAKHAR", "BADE'E AL OUD", 
    "AMEER AL OUD", "ANA ABIYEDH", "NEBRAS", "HONOR & GLORY", "OUD FOR GLORY",
    # Rasasi Bestsellers
    "HAWAS", "HAWAS ICE", "DAAREJ", "AL WISAM",
    # Al Haramain Bestsellers
    "AMBER OUD", "L'AVENTURE", "DETOUR NOIR",
    # Paris Corner / Emir Bestsellers
    "EMIR", "CELESTIAL", "RICH SANTAL", "VALOR", "AUTO GRAPH",
    # Maison Alhambra Bestsellers
    "WOODY OUD", "TOBACCO TOUCH", "PORTO NEROLI", "JEAN LOWE",
    # Other Niche Hits
    "SHIYAAKA", "9PM", "9 PM", "SUPREMACY", "RARE CARBON", "TURATHI BLUE"
]

# 4. FALLBACK BRANDS (To fill any remaining slots up to 150)
OTHER_TARGET_BRANDS = [
    "LATTAFA", "RASASI", "AL HARAMAIN", "PARIS CORNER", 
    "MAISON ALHAMBRA", "ARMAF", "SWISS ARABIAN", "ARABIYAT", 
    "ARD AL ZAAFARAN", "NABEEL", "KHADLAJ", "FRAGRANCE WORLD", "FRENCH AVENUE"
]

EXACT_TARGET_COUNT = 150  # Total exact limit for BTS
MIN_STOCK = 5             # Stock must be >= 5

def clean_price(val):
    if not val:
        return ""
    return re.sub(r'[^0-9\.]', '', val.replace(',', '.'))

def clean_title(title_str):
    if not title_str:
        return ""
    unwanted_terms = [r'\bSpray\b', r'\bVaporisateur\b', r'\bVapo\b']
    cleaned = title_str
    for term in unwanted_terms:
        cleaned = re.sub(term, '', cleaned, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', cleaned).strip()

def get_stock_count(row):
    for col in ['stock', 'quantity', 'qty', 'stock_qty', 'units']:
        if col in row and row[col]:
            try:
                clean_val = re.sub(r'[^0-9\.]', '', str(row[col]))
                return float(clean_val) if clean_val else 0.0
            except ValueError:
                pass
    return 0.0

def has_valid_image(row):
    """Strictly checks for valid non-empty image URLs."""
    image_cols = ['image', 'image_url', 'picture', 'img', 'photo_url', 'image1', 'images']
    for col in image_cols:
        if col in row and row[col]:
            val_str = str(row[col]).strip().lower()
            if val_str and val_str not in ["", "none", "null", "no_image", "n/a", "http://", "https://"]:
                return True
    return False

def is_excluded(row):
    """Check for Yara, Asad, or Club de Nuit"""
    row_text = " ".join([str(v) for v in row.values() if v]).upper()
    for phrase in EXCLUDED_PHRASES:
        if re.search(r'\b' + re.escape(phrase) + r'\b', row_text):
            return True
    return False

def get_item_tier(row):
    """Tier 1: Exact Name Flagships & Afnan | Tier 2: General Target Brands"""
    row_text = " ".join([str(v) for v in row.values() if v]).upper()

    # Priority 1: Check Afnan
    if re.search(r'\bAFNAN\b', row_text):
        return 'tier1'

    # Priority 1: Check Exact Perfume Names
    for name in EXACT_BEST_SELLERS:
        if re.search(r'\b' + re.escape(name) + r'\b', row_text):
            return 'tier1'

    # Priority 2: Check Other Brands
    for brand in OTHER_TARGET_BRANDS:
        if re.search(r'\b' + re.escape(brand) + r'\b', row_text):
            return 'tier2'

    return None

def download_feed():
    req = urllib.request.Request(FEED_URL, headers={'User-Agent': 'Mozilla/5.0'})
    for attempt in range(3):
        try:
            print(f"Downloading BTS catalog (Attempt {attempt+1})...")
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"Download warning: {e}")
            time.sleep(5)
    raise Exception("Failed to fetch BTS feed.")

content = download_feed()
lines = content.splitlines()
print(f"Downloaded catalog with {len(lines)} lines.")

delim = ';' if ';' in lines[0] else ','
reader = csv.DictReader(lines, delimiter=delim)

tier1_candidates = []
tier2_candidates = []

for row in reader:
    # 1. Stock filter
    stock_qty = get_stock_count(row)
    if stock_qty < MIN_STOCK:
        continue

    # 2. Image filter
    if not has_valid_image(row):
        continue

    # 3. Exclusion filter
    if is_excluded(row):
        continue

    # 4. Brand & Name Match Tier
    tier = get_item_tier(row)
    if not tier:
        continue

    if 'price' in row:
        row['price'] = clean_price(row['price'])
    if 'recommended_price' in row:
        row['recommended_price'] = clean_price(row['recommended_price'])

    for name_col in ['name', 'title', 'product_name']:
        if name_col in row:
            row[name_col] = clean_title(row[name_col])

    item = {'row': row, 'stock': stock_qty}
    if tier == 'tier1':
        tier1_candidates.append(item)
    else:
        tier2_candidates.append(item)

# Sort candidates by stock quantity
tier1_candidates.sort(key=lambda x: x['stock'], reverse=True)
tier2_candidates.sort(key=lambda x: x['stock'], reverse=True)

# Combine: Put all Exact Bestsellers & Afnan first, then fill up to 150 total
final_selected = [c['row'] for c in tier1_candidates]

if len(final_selected) < EXACT_TARGET_COUNT:
    needed = EXACT_TARGET_COUNT - len(final_selected)
    final_selected.extend([c['row'] for c in tier2_candidates[:needed]])
else:
    final_selected = final_selected[:EXACT_TARGET_COUNT]

print(f"Matched {len(tier1_candidates)} Tier 1 (Afnan + Named Flagships) and {len(tier2_candidates)} Tier 2 brand items.")
print(f"Outputting exactly top {len(final_selected)} items into bts_filtered.csv.")

if final_selected:
    with open("bts_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames, delimiter=delim)
        writer.writeheader()
        writer.writerows(final_selected)
    print("bts_filtered.csv successfully updated!")
