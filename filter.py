import csv
import urllib.request
import urllib.error
import time
import re

FEED_URL = "https://www.btswholesaler.com/generatefeedbts?user_id=1429150&pass=Avedore556%2C&format=csv&language_code=en-GB"

# 1. EXCLUSIONS: Strictly block items fulfilled manually
EXCLUDED_PHRASES = ["YARA", "ASAD", "CLUB DE NUIT"]

# 2. MASTER NORDIC BESTSELLERS LIST (Top Designer & Middle Eastern Hype Perfumes)
# If an item from BTS is NOT on this list, it WILL NOT be pulled.
EXACT_BEST_SELLERS = [
    # --- MIDDLE EASTERN BESTSELLERS ---
    # Afnan
    "AFNAN 9PM", "AFNAN 9 PM", "SUPREMACY SILVER", "SUPREMACY NOT ONLY INTENSE", "SUPREMACY IN OUD", 
    "SNOI", "AFNAN TURATHI BLUE", "TURATHI BROWN", "AFNAN ZIMAYA", "AFNAN HISTORIA",
    # French Avenue / Fragrance World
    "LIQUID BRUN", "VULCAN FEU", "ROYAL BLEND", "BARAKKAT ROUGE 540", "BARAKKAT", "SUITS", "APEX",
    # Lattafa (Excluding Yara & Asad)
    "KHAMRAH", "KHAMRAH QAHWA", "ECLAIRE", "FAKHAR", "BADE'E AL OUD", "OEK",
    "AMEER AL OUD", "ANA ABIYEDH", "NEBRAS", "HONOR & GLORY", "OUD FOR GLORY", "AL NASHAMA",
    # Rasasi
    "HAWAS", "HAWAS ICE", "DAAREJ", "AL WISAM", "SHUHRAH",
    # Al Haramain
    "AMBER OUD", "AMBER OUD GOLD", "AMBER OUD BLEU", "L'AVENTURE", "DETOUR NOIR", "PORTFOLIO",
    # Paris Corner / Emir / Pendora
    "EMIR", "CELESTIAL", "RICH SANTAL", "VALOR", "AUTO GRAPH", "VOUX ELEGANTE", "KAHEELA",
    # Maison Alhambra
    "WOODY OUD", "TOBACCO TOUCH", "PORTO NEROLI", "JEAN LOWE", "JEAN LOWE OMBRE", "ALHAMBRA KISMET",
    # Armaf / Swiss Arabian / Khadlaj
    "SHIYAAKA", "RARE CARBON", "TAG HIM", "CLUB DE NUIT INTENSE", "SHAGHAF OUD", "HAREEM AL SULTAN",

    # --- TOP DESIGNER BESTSELLERS (SE/DK MARKET) ---
    # Yves Saint Laurent (YSL)
    "LIBRE", "BLACK OPIUM", "Y FOR MEN", "MYSLF", "L'HOMME", "LA NUIT DE L'HOMME", "MON PARIS",
    # Dior
    "SAUVAGE", "DIOR HOMME", "DIOR HOMME INTENSE", "MISS DIOR", "J'ADORE", "FAHRENHEIT", "POISON",
    # Carolina Herrera
    "GOOD GIRL", "GOOD GIRL BLUSH", "VERY GOOD GIRL", "BAD BOY", "BAD BOY COBALT", "212 VIP",
    # Jean Paul Gaultier
    "LE MALE", "LE MALE ELIXIR", "ULTRA MALE", "LE BEAU", "SCANDAL", "DIVINE",
    # Giorgio Armani
    "ACQUA DI GIO", "ACQUA DI GIOIA", "MY WAY", "CODE", "STRONGER WITH YOU", "SI", "SI PASSIONE",
    # Prada
    "PARADOXE", "PARADOXE INTENSE", "L'HOMME PRADA", "LUNA ROSSA", "LUNA ROSSA OCEAN", "OCEAN",
    # Versace
    "EROS", "EROS FLAME", "BRIGHT CRYSTAL", "CRYSTAL NOIR", "DYLAN BLUE", "POUR HOMME",
    # Hugo Boss
    "BOSS BOTTLED", "BOSS BOTTLED PARFUM", "THE SCENT", "HUGO MAN", "ALIVE",
    # Paco Rabanne
    "1 MILLION", "ONE MILLION", "1 MILLION ELIXIR", "INVICTUS", "INVICTUS VICTORY", "PHANTOM", "FAME", "OLYMPEA",
    # Dolce & Gabbana
    "LIGHT BLUE", "THE ONE", "D&G K", "D&G Q", "DEVOTION",
    # Montblanc
    "EXPLORER", "EXPLORER PLATINUM", "LEGEND", "LEGEND NIGHT",
    # Tom Ford / Creed / Niche
    "BLACK ORCHID", "VELVET ORCHID", "OMBRE LEATHER", "AVENTUS", "SILVER MOUNTAIN WATER", "DELINA"
]

MAX_TARGET_COUNT = 300  # Strict maximum limit
MIN_STOCK = 10          # Stock threshold to avoid overselling

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
    """Checks for valid non-empty image URLs."""
    image_cols = ['image', 'image_url', 'picture', 'img', 'photo_url', 'image1', 'images']
    for col in image_cols:
        if col in row and row[col]:
            val_str = str(row[col]).strip().lower()
            if val_str and val_str not in ["", "none", "null", "no_image", "n/a", "http://", "https://"]:
                return True
    return False

def is_excluded(row):
    """Check for Yara, Asad, or Club de Nuit exclusions"""
    row_text = " ".join([str(v) for v in row.values() if v]).upper()
    for phrase in EXCLUDED_PHRASES:
        if re.search(r'\b' + re.escape(phrase) + r'\b', row_text):
            return True
    return False

def matches_bestseller(row):
    """Strictly matches item against the master bestseller list."""
    row_text = " ".join([str(v) for v in row.values() if v]).upper()
    for item_name in EXACT_BEST_SELLERS:
        if re.search(r'\b' + re.escape(item_name) + r'\b', row_text):
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

matched_candidates = []

for row in reader:
    # 1. Stock filter (>= 10 pcs)
    stock_qty = get_stock_count(row)
    if stock_qty < MIN_STOCK:
        continue

    # 2. Image filter (Must have picture)
    if not has_valid_image(row):
        continue

    # 3. Exclusion filter
    if is_excluded(row):
        continue

    # 4. Strict Bestseller Verification
    if not matches_bestseller(row):
        continue

    # Clean price (Keep raw EUR value)
    if 'price' in row and row['price']:
        row['price'] = clean_price(row['price'])
    if 'recommended_price' in row and row['recommended_price']:
        row['recommended_price'] = clean_price(row['recommended_price'])

    for name_col in ['name', 'title', 'product_name']:
        if name_col in row:
            row[name_col] = clean_title(row[name_col])

    matched_candidates.append({'row': row, 'stock': stock_qty})

# Sort matched candidates by stock quantity
matched_candidates.sort(key=lambda x: x['stock'], reverse=True)

# Select up to MAX_TARGET_COUNT (300 max)
final_selected = [c['row'] for c in matched_candidates[:MAX_TARGET_COUNT]]

print(f"Matched {len(matched_candidates)} verified bestseller items in BTS stock.")
print(f"Outputting {len(final_selected)} items into bts_filtered.csv.")

if final_selected:
    with open("bts_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames, delimiter=delim)
        writer.writeheader()
        writer.writerows(final_selected)
    print("bts_filtered.csv successfully updated!")
