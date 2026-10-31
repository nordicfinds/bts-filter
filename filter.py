import csv
import urllib.request
import urllib.error
import time
import re

FEED_URL = "https://www.btswholesaler.com/generatefeedbts?user_id=1429150&pass=Avedore556%2C&format=csv&language_code=en-GB"

# Strictly Middle Eastern & Arabian Niche / Inspired Brands
MIDDLE_EASTERN_BRANDS = [
    "LATTAFA",
    "AFNAN",
    "FRENCH AVENUE",
    "PARIS CORNER",
    "MAISON ALHAMBRA",
    "RASASI",
    "AL HARAMAIN",
    "ARMAF",
    "SWISS ARABIAN",
    "ARABIYAT",
    "ARD AL ZAAFARAN",
    "NABEEL",
    "KHADLAJ",
    "AYAT"
]

EXACT_TARGET_COUNT = 100  # Strictly top 100 items for BaseLinker budget
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
    """Check if the row has a non-empty image URL/path."""
    image_cols = ['image', 'image_url', 'picture', 'img', 'photo_url', 'image1']
    for col in image_cols:
        if col in row and row[col] and str(row[col]).strip() != "":
            return True
    return False

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

candidates = []

for row in reader:
    # 1. Check stock threshold (Must be >= 5)
    stock_qty = get_stock_count(row)
    if stock_qty < MIN_STOCK:
        continue

    # 2. Check for missing image
    if not has_valid_image(row):
        continue

    row_text = " ".join([str(v) for v in row.values() if v]).upper()
    
    # 3. Match ONLY Middle Eastern Brands
    matched = any(brand in row_text for brand in MIDDLE_EASTERN_BRANDS)

    if matched:
        if 'price' in row:
            row['price'] = clean_price(row['price'])
        if 'recommended_price' in row:
            row['recommended_price'] = clean_price(row['recommended_price'])
            
        for name_col in ['name', 'title', 'product_name']:
            if name_col in row:
                row[name_col] = clean_title(row[name_col])
                
        candidates.append({
            'row': row,
            'stock': stock_qty
        })

# Sort all valid Middle Eastern matches by highest stock available
candidates.sort(key=lambda x: x['stock'], reverse=True)

# Take strictly the top 100 with valid images and stock >= 5
final_selected = [c['row'] for c in candidates[:EXACT_TARGET_COUNT]]

print(f"Matched {len(candidates)} total Middle Eastern perfumes with images and stock >= {MIN_STOCK}.")
print(f"Outputting exactly top {len(final_selected)} items into bts_filtered.csv.")

if final_selected:
    with open("bts_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames, delimiter=delim)
        writer.writeheader()
        writer.writerows(final_selected)
    print("bts_filtered.csv successfully updated!")
