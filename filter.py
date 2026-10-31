import csv
import urllib.request
import urllib.error
import time
import re

FEED_URL = "https://www.btswholesaler.com/generatefeedbts?user_id=1429150&pass=Avedore556%2C&format=csv&language_code=en-GB"

# Updated Target Models (Added Afnan Extrait/Not Only)
TARGET_MODELS = {
    "RASASI": ["HAWAS", "DAAREJ", "SHUHRAH", "LA YUQAWAM"],
    "FRENCH AVENUE": ["LIQUID BRUN", "ROYAL BLEND", "AFTER EIGHT", "ENIGMA UNO"],
    "AFNAN": ["9PM", "9AM", "TURATHI", "SUPREMACY", "MODEST UNS", "NOT ONLY", "EXTRAIT"], # Added Extrait / Not Only
    "LATTAFA": ["KHAMRAH", "NEBRAS", "FAKHAR", "BADEE AL OUD", "MAAHIR", "HONOR & GLORY"],
    "ARMAF": ["TAG", "VENTANA", "ODYSSEY", "BUCEPHALUS"],
    "GUCCI": ["BLOOM", "FLORA", "GUILTY", "RUSH"],
    "FRAGRANCE WORLD": ["BARAKKAT", "COFFEE BREAK", "DIVIN ASPHALT", "INTRO", "SUITS"],
    "PARIS CORNER": ["EMIR", "KHAIR", "AUTOMNE", "PISTACHIO"],
    "SWISS ARABIAN": ["SHAGHAF", "CASABLANCA", "GHARAAM", "LAYALI"],
    "ARABIYAT": ["PRESTIGE", "OUD AL LAYL", "ARABIYAT KHAS"],
    "CAROLINA HERRERA": ["GOOD GIRL", "BAD BOY", "212", "VERY GOOD GIRL"],
    "CALVIN KLEIN": ["CK ONE", "CK BE", "EUPHORIA", "ETERNITY"],
    "ELIZABETH ARDEN": ["GREEN TEA", "EIGHT HOUR", "5TH AVENUE"],
    "JULIETTE HAS A GUN": ["NOT A PERFUME", "SUPERDOSE", "PEAR INC"],
    "CLEAN": ["WARM COTTON", "RESERVE", "RAIN", "SKIN"],
    "THE ORDINARY": ["NIACINAMIDE", "HYALURONIC", "AHA", "CAFFEINE", "GLYCOLIC"],
    "VERSACE": ["EROS", "BRIGHT CRYSTAL", "DYLAN", "CRYSTAL NOIR"],
    "PACO RABANNE": ["1 MILLION", "ONE MILLION", "INVICTUS", "LADY MILLION", "OLYMPEA"],
    "SOL DE JANEIRO": ["CHEIROSA", "BUM BUM", "62", "68", "71"]
}

EXACT_TARGET_COUNT = 100  # Hard cap for BaseLinker freemium limit
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
    stock_qty = get_stock_count(row)
    if stock_qty < MIN_STOCK:
        continue

    row_text = " ".join([str(v) for v in row.values() if v]).upper()
    
    matched = False
    for brand, models in TARGET_MODELS.items():
        if brand in row_text:
            if any(m in row_text for m in models):
                matched = True
                break

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

# Sort candidate matches by highest stock to ensure availability
candidates.sort(key=lambda x: x['stock'], reverse=True)

# Select strictly up to 100 top matches
final_selected = [c['row'] for c in candidates[:EXACT_TARGET_COUNT]]

print(f"Matched {len(candidates)} specific models meeting criteria.")
print(f"Outputting exactly top {len(final_selected)} items.")

if final_selected:
    with open("bts_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames, delimiter=delim)
        writer.writeheader()
        writer.writerows(final_selected)
    print("bts_filtered.csv successfully updated with target models!")
