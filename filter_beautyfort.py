import csv
import urllib.request
import urllib.error
import hashlib
import time
import json
import re

USERNAME = "Base.com"
SECRET = "JfPciKxq"

# Priority 1: Top-selling model names for Nordic market
TOP_MODELS = [
    "BOSS BOTTLED", "THE SCENT", "HUGO MAN", "BOSS ALIVE", "BOSS FEMME", "HUGO DEEP RED", "BOSS ORANGE",
    "SAUVAGE", "FAHRENHEIT", "J'ADORE", "MISS DIOR",
    "BLACK OPIUM", "LIBRE", "YSL Y", "OPIUM",
    "ACQUA DI GIO", "STRONGER WITH YOU", "MY WAY", "SI",
    "1 MILLION", "ONE MILLION", "INVICTUS", "PHANTOM", "OLYMPEA",
    "BLEU DE CHANEL", "COCO MADEMOISELLE", "ALLURE",
    "MONTBLANC EXPLORER", "MONTBLANC LEGEND",
    "EROS", "DYLAN BLUE", "LIGHT BLUE", "K BY DOLCE",
    "HERO", "BURBERRY HER", "CK ONE", "ETERNITY", "EUPHORIA", "LE MALE", "DIVINE", "SCANDAL"
]

# Priority 2: General brand fallbacks
TARGET_BRANDS = [
    "HUGO BOSS", "BOSS", "DIOR", "CHANEL", "ARMANI", "GIORGIO ARMANI", 
    "YVES SAINT LAURENT", "YSL", "PACO RABANNE", "RABANNE", 
    "MONTBLANC", "VERSACE", "DOLCE & GABBANA", "BURBERRY", 
    "CALVIN KLEIN", "JEAN PAUL GAULTIER", "TOM FORD", "PRADA"
]

EXACT_TARGET_COUNT = 150
MIN_STOCK = 5

def clean_price(val):
    if not val:
        return ""
    return re.sub(r'[^0-9\.]', '', str(val).replace(',', '.'))

def clean_title(title_str):
    if not title_str:
        return ""
    unwanted_terms = [r'\bSpray\b', r'\bVaporisateur\b', r'\bVapo\b']
    cleaned = title_str
    for term in unwanted_terms:
        cleaned = re.sub(term, '', cleaned, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', cleaned).strip()

def build_beautyfort_headers():
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    token = f"token_{int(time.time())}"
    raw_sig = f"{token}{timestamp}{SECRET}"
    password_hash = hashlib.sha256(raw_sig.encode('utf-8')).hexdigest()

    return {
        'X-Username': USERNAME,
        'X-Token': token,
        'X-Created': timestamp,
        'X-Password': password_hash,
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json'
    }

def fetch_beautyfort_catalog():
    # Official endpoint format from Beauty Fort API v5 docs
    endpoints = [
        "https://api.beautyfort.com/getstockfile",
        "https://api.beautyfort.com/GetStockFile",
        "https://api.beautyfort.com/v5/getstockfile",
        "https://api.beautyfort.com/products"
    ]
    
    headers = build_beautyfort_headers()
    
    for url in endpoints:
        try:
            print(f"Trying Beauty Fort endpoint: {url}")
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as resp:
                content = resp.read().decode('utf-8', errors='ignore')
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return content
        except urllib.error.HTTPError as e:
            print(f"Endpoint {url} returned HTTP {e.code}")
        except Exception as e:
            print(f"Endpoint {url} error: {e}")
            
    raise Exception("Could not reach any valid Beauty Fort API endpoint.")

raw_data = fetch_beautyfort_catalog()

top_sellers = []
brand_fallbacks = []

if isinstance(raw_data, (dict, list)):
    items = raw_data.get('products', raw_data.get('items', raw_data)) if isinstance(raw_data, dict) else raw_data
    for item in items:
        stock = float(item.get('stock', item.get('quantity', item.get('qty', 0))))
        if stock < MIN_STOCK:
            continue

        name = str(item.get('name', item.get('title', item.get('description', '')))).upper()
        product_dict = {
            'sku': str(item.get('sku', item.get('id', ''))),
            'name': clean_title(name),
            'stock': int(stock),
            'price': clean_price(item.get('price', item.get('wholesale_price', ''))),
            'ean': str(item.get('ean', item.get('barcode', '')))
        }

        if any(model in name for model in TOP_MODELS):
            top_sellers.append(product_dict)
        elif any(brand in name for brand in TARGET_BRANDS):
            brand_fallbacks.append(product_dict)

top_sellers.sort(key=lambda x: x['stock'], reverse=True)
brand_fallbacks.sort(key=lambda x: x['stock'], reverse=True)

final_selected = (top_sellers + brand_fallbacks)[:EXACT_TARGET_COUNT]

print(f"Matched {len(top_sellers)} top models and {len(brand_fallbacks)} brand fallbacks.")
print(f"Exporting top {len(final_selected)} items to beautyfort_filtered.csv...")

if final_selected:
    with open("beautyfort_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
        fieldnames = ['sku', 'name', 'stock', 'price', 'ean']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(final_selected)
    print("beautyfort_filtered.csv successfully created!")
