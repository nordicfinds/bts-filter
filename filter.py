import csv
import urllib.request
import urllib.error
import time
import re
from collections import defaultdict

FEED_URL = "https://www.btswholesaler.com/generatefeedbts?user_id=1429150&pass=Avedore556%2C&format=csv&language_code=en-GB"

# Top High-Demand Brands for the Nordic Market
TARGET_BRANDS = [
    "LATTAFA", 
    "ARMAF", 
    "FRAGRANCE WORLD", 
    "PARIS CORNER", 
    "AFNAN", 
    "RASASI", 
    "FRENCH AVENUE", 
    "SWISS ARABIAN", 
    "ARABIYAT", 
    "CAROLINA HERRERA", 
    "CALVIN KLEIN", 
    "ELIZABETH ARDEN", 
    "JULIETTE HAS A GUN", 
    "CLEAN", 
    "THE ORDINARY", 
    "VERSACE", 
    "PACO RABANNE", 
    "SOL DE JANEIRO"
]

EXACT_TARGET_COUNT = 100  # Exactly 100 items
MIN_STOCK = 5             # Minimum stock requirement

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

# Group products by brand bucket
brand_buckets = defaultdict(list)

for row in reader:
    stock_qty = get_stock_count(row)
    if stock_qty < MIN_STOCK:
        continue

    row_text = " ".join([str(v) for v in row.values() if v]).upper()
    
    matched_brand = None
    for brand in TARGET_BRANDS:
        if brand in row_text:
            matched_brand = brand
            break

    if matched_brand:
        if 'price' in row:
            row['price'] = clean_price(row['price'])
        if 'recommended_price' in row:
            row['recommended_price'] = clean_price(row['recommended_price'])
            
        for name_col in ['name', 'title', 'product_name']:
            if name_col in row:
                row[name_col] = clean_title(row[name_col])
                
        brand_buckets[matched_brand].append({
            'row': row,
            'stock': stock_qty
        })

# Sort items within each brand by highest stock volume first
for brand in brand_buckets:
    brand_buckets[brand].sort(key=lambda x: x['stock'], reverse=True)

# Round-robin selection to guarantee EXACTLY 100 items distributed across brands
final_selected = []
active_brands = [b for b in TARGET_BRANDS if b in brand_buckets]

while len(final_selected) < EXACT_TARGET_COUNT and active_brands:
    brands_to_remove = []
    for brand in active_brands:
        if len(final_selected) >= EXACT_TARGET_COUNT:
            break
        
        items = brand_buckets[brand]
        if items:
            # Pop the highest stock item for this brand
            top_item = items.pop(0)
            final_selected.append(top_item['row'])
        else:
            brands_to_remove.append(brand)
            
    # Clean up brands that ran out of eligible stock items
    for b in brands_to_remove:
        active_brands.remove(b)
        
    # Safety break if total catalog has fewer than 100 items meeting criteria
    if not active_brands:
        break

print(f"Final selected product count: {len(final_selected)}")

if final_selected:
    with open("bts_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames, delimiter=delim)
        writer.writeheader()
        writer.writerows(final_selected)
    print("bts_filtered.csv successfully generated with exact count!")
