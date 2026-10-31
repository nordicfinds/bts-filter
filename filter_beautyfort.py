import csv
import urllib.request
import urllib.error
import base64
import json
import time
import re

# Beauty Fort Credentials
USERNAME = "Base.com"
SECRET = "JfPciKxq"
API_URL = "https://api.beautyfort.com/v1/products" 

# 1. PRIORITY 1: Specific Best-Selling Models in the Nordic Market
TOP_MODELS = [
    # Hugo Boss Bestsellers
    "BOSS BOTTLED", "THE SCENT", "HUGO MAN", "BOSS ALIVE", "BOSS FEMME", "HUGO DEEP RED", "BOSS ORANGE",
    
    # Other Major Nordic Bestsellers
    "SAUVAGE", "FAHRENHEIT", "J'ADORE", "MISS DIOR",           # Dior
    "BLACK OPIUM", "LIBRE", "YSL Y", "OPIUM",                 # YSL
    "ACQUA DI GIO", "STRONGER WITH YOU", "MY WAY", "SI",     # Armani
    "1 MILLION", "ONE MILLION", "INVICTUS", "PHANTOM", "OLYMPEA", # Paco Rabanne
    "BLEU DE CHANEL", "COCO MADEMOISELLE", "ALLURE",           # Chanel
    "MONTBLANC EXPLORER", "MONTBLANC LEGEND",                 # Montblanc
    "EROS", "DYLAN BLUE",                                     # Versace
    "LIGHT BLUE", "K BY DOLCE",                               # D&G
    "HERO", "BURBERRY HER",                                   # Burberry
    "CK ONE", "ETERNITY", "EUPHORIA",                         # Calvin Klein
    "LE MALE", "DIVINE", "SCANDAL"                            # JPG
]

# 2. PRIORITY 2: General High-Demand Brands (Fallback to hit 150 target)
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

def fetch_beautyfort_data():
    auth_str = f"{USERNAME}:{SECRET}"
    b64_auth = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
    headers = {
        'Authorization': f'Basic {b64_auth}',
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json'
    }
    req = urllib.request.Request(API_URL, headers=headers)
    for attempt in range(3):
        try:
            print(f"Fetching Beauty Fort catalog (Attempt {attempt+1})...")
            with urllib.request.urlopen(req, timeout=60) as resp:
                content = resp.read().decode('utf-8', errors='ignore')
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return content
        except Exception as e:
            print(f"Fetch warning: {e}")
            time.sleep(5)
    raise Exception("Failed to fetch Beauty Fort catalog.")

raw_data = fetch_beautyfort_data()

top_sellers = []
brand_fallbacks = []

if isinstance(raw_data, (dict, list)):
    items = raw_data.get('products', raw_data) if isinstance(raw_data, dict) else raw_data
    for item in items:
        stock = float(item.get('stock', item.get('quantity', 0)))
        if stock < MIN_STOCK:
            continue

        name = str(item.get('name', item.get('title', ''))).upper()
        product_dict = {
            'sku': str(item.get('sku', item.get('id', ''))),
            'name': clean_title(name),
            'stock': int(stock),
            'price': clean_price(item.get('price', item.get('wholesale_price', ''))),
            'ean': str(item.get('ean', item.get('barcode', '')))
        }

        # Check Priority 1: Top-selling model names
        if any(model in name for model in TOP_MODELS):
            top_sellers.append(product_dict)
        # Check Priority 2: General luxury brand fallback
        elif any(brand in name for brand in TARGET_BRANDS):
            brand_fallbacks.append(product_dict)

# Sort both groups by stock level
top_sellers.sort(key=lambda x: x['stock'], reverse=True)
brand_fallbacks.sort(key=lambda x: x['stock'], reverse=True)

# Merge: Top specific sellers get picked first, brand fallbacks second
final_selected = (top_sellers + brand_fallbacks)[:EXACT_TARGET_COUNT]

print(f"Picked {len(top_sellers)} top-selling Nordic model matches.")
print(f"Total outputting {len(final_selected)} products to CSV.")

if final_selected:
    with open("beautyfort_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
        fieldnames = ['sku', 'name', 'stock', 'price', 'ean']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(final_selected)
    print("beautyfort_filtered.csv successfully created!")
