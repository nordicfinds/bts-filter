import csv
import urllib.request
import urllib.error
import time
import re

FEED_URL = "https://www.btswholesaler.com/generatefeedbts?user_id=1429150&pass=Avedore556%2C&format=csv&language_code=en-GB"

# Items you already fulfill yourself (strictly excluded)
EXCLUDED_PHRASES = ["YARA", "ASAD", "CLUB DE NUIT"]

# Priority Brand: All Afnan products will be pulled first
PRIMARY_BRAND = "AFNAN"

# Other preferred brands to fill remaining slots up to 150 total
OTHER_TARGET_BRANDS = [
    "RASASI",
    "AL HARAMAIN",
    "LATTAFA",  # Yara & Asad are excluded via EXCLUDED_PHRASES above
    "PARIS CORNER",
    "MAISON ALHAMBRA",
    "ARMAF",    # Club de Nuit variants are excluded via EXCLUDED_PHRASES above
    "SWISS ARABIAN",
    "ARABIYAT",
    "ARD AL ZAAFARAN",
    "NABEEL",
    "KHADLAJ",
    "AYAT",
    "FRAGRANCE WORLD",
    "FRENCH AVENUE"
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
    image_cols = ['image', 'image_url', 'picture', 'img', 'photo_url', 'image1']
    for col in image_cols:
        if col in row and row[col] and str(row[col]).strip() != "":
            return True
    return False

def is_excluded(row):
    """Check if the row contains any excluded phrases like Yara, Asad, or Club de Nuit"""
    row_text = " ".join([str(v) for v in row.values() if v]).upper()
    for phrase in EXCLUDED_PHRASES:
        if re.search(r'\b' + re.escape(phrase) + r'\b', row_text):
            return True
    return False

def get_brand_category(row):
    """Classify row as 'afnan', 'other', or None"""
    brand_cols = ['brand', 'manufacturer', 'vendor', 'marca', 'brand_name']
    name_cols = ['name', 'title', 'product_name']
    
    # 1. Check Afnan first (Priority)
    for col in brand_cols + name_cols:
        if col in row and row[col]:
            val_upper = str(row[col]).upper()
            if re.search(r'\bAFNAN\b', val_upper):
                return 'afnan'
                
    # 2. Check other target brands
    for col in brand_cols + name_cols:
        if col in row and row[col]:
            val_upper = str(row[col]).upper()
            for brand in OTHER_TARGET_BRANDS:
                if re.search(r'\b' + re.escape(brand) + r'\b', val_upper):
                    return 'other'
                    
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

afnan_candidates = []
other_candidates = []

for row in reader:
    # 1. Stock check
    stock_qty = get_stock_count(row)
    if stock_qty < MIN_STOCK:
        continue

    # 2. Image check
    if not has_valid_image(row):
        continue

    # 3. Skip excluded items (Yara, Asad, Club de Nuit)
    if is_excluded(row):
        continue

    # 4. Check brand match
    brand_type = get_brand_category(row)
    if not brand_type:
        continue

    if 'price' in row:
        row['price'] = clean_price(row['price'])
    if 'recommended_price' in row:
        row['recommended_price'] = clean_price(row['recommended_price'])

    for name_col in ['name', 'title', 'product_name']:
        if name_col in row:
            row[name_col] = clean_title(row[name_col])

    item = {'row': row, 'stock': stock_qty}
    if brand_type == 'afnan':
        afnan_candidates.append(item)
    else:
        other_candidates.append(item)

# Sort candidates by highest stock available
afnan_candidates.sort(key=lambda x: x['stock'], reverse=True)
other_candidates.sort(key=lambda x: x['stock'], reverse=True)

# Build final selection: All Afnan first, then fill remainder from other brands up to 150
final_selected_items = [c['row'] for c in afnan_candidates]

remaining_slots = EXACT_TARGET_COUNT - len(final_selected_items)
if remaining_slots > 0:
    final_selected_items.extend([c['row'] for c in other_candidates[:remaining_slots]])
else:
    # If Afnan alone exceeds 150, cap the list cleanly at 150
    final_selected_items = final_selected_items[:EXACT_TARGET_COUNT]

print(f"Found {len(afnan_candidates)} Afnan items and {len(other_candidates)} other targeted brand items.")
print(f"Outputting exactly {len(final_selected_items)} items into bts_filtered.csv.")

if final_selected_items:
    with open("bts_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames, delimiter=delim)
        writer.writeheader()
        writer.writerows(final_selected_items)
    print("bts_filtered.csv successfully updated!")
