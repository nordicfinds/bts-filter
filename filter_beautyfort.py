import requests
import xml.etree.ElementTree as ET
import pandas as pd
import re
import csv
import os

# ============ SETTINGS ============
EXACT_TARGET_COUNT = 150
MIN_STOCK = 5
OUTPUT_FILE = "beautyfort_filtered.csv"

# Replace with your actual Beauty Fort API endpoint URL
API_URL = "https://www.beautyfort.com/api/v5/soap" 

TOP_BRANDS = [
    "DIOR", "CHANEL", "VERSACE", "GIORGIO ARMANI", "ARMANI", "YVES SAINT LAURENT",
    "YSL", "PACO RABANNE", "RABANNE", "DOLCE & GABBANA", "DOLCE", "HUGO BOSS",
    "BOSS", "GUCCI", "PRADA", "BURBERRY", "CALVIN KLEIN", "CK", "CAROLINA HERRERA",
    "JEAN PAUL GAULTIER", "GAULTIER", "TOM FORD", "HERMES", "BVLGARI"
]

TOP_MODELS = [
    "SAUVAGE", "FAHRENHEIT", "J'ADORE", "JADORE", "MISS DIOR", "DIOR HOMME",
    "BLEU DE CHANEL", "COCO MADEMOISELLE", "ALLURE", "CHANCE", "N°5", "NO 5",
    "EROS", "DYLAN BLUE", "BRIGHT CRYSTAL", "EROS FLAME",
    "ACQUA DI GIO", "STRONGER WITH YOU", "MY WAY", "SI PASSIONE", "ARMANI CODE",
    "BLACK OPIUM", "LIBRE", "MON PARIS",
    "1 MILLION", "ONE MILLION", "INVICTUS", "PHANTOM", "OLYMPEA", "LADY MILLION",
    "LIGHT BLUE", "THE ONE", "K BY DOLCE", "DEVOTION",
    "BOSS BOTTLED", "THE SCENT", "HUGO MAN", "BOSS ALIVE",
    "GUCCI BLOOM", "GUCCI GUILTY", "FLORA",
    "LUNA ROSSA", "PARADOXE", "CANDY",
    "BURBERRY HER", "GODDESS", "MR BURBERRY", "LONDON",
    "CK ONE", "ETERNITY", "EUPHORIA", "CK BE",
    "GOOD GIRL", "BAD BOY", "212",
    "LE MALE", "SCANDAL", "ULTRA MALE", "DIVINE",
    "BLACK ORCHID", "OMBRÉ LEATHER", "OMBRE LEATHER", "NEROLI PORTOFINO", "TOBACCO VANILLE",
    "TERRE D'HERMES", "H24", "OMNIA"
]

def make_pattern(terms):
    parts = [r"(?<![A-Z0-9])" + re.escape(t) + r"(?![A-Z0-9])" for t in terms]
    return re.compile("|".join(parts))

BRAND_RE = make_pattern(TOP_BRANDS)
MODEL_RE = make_pattern(TOP_MODELS)

def clean_title(title_str):
    if not isinstance(title_str, str):
        return ""
    cleaned = title_str
    for term in [r"\bSpray\b", r"\bSprej\b", r"\bVaporisateur\b", r"\bVapo\b"]:
        cleaned = re.sub(term, "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()

def fetch_live_catalog():
    print("Fetching live catalog from Beauty Fort API...")
    # Add API payload / headers here if required by your account settings
    try:
        response = requests.get(API_URL, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Direct API call failed: {e}")
        # Fallback to local spreadsheet if API call fails or isn't configured
        excel_files = [f for f in os.listdir('.') if f.startswith('lagerfil') and f.endswith('.xlsx')]
        if excel_files:
            print(f"Falling back to local file: {excel_files[0]}")
            return excel_files[0]
        raise SystemExit("No live API data or local Excel file available.")

data_source = fetch_live_catalog()
matched_items = []

if isinstance(data_source, str) and data_source.endswith('.xlsx'):
    df = pd.read_excel(data_source, header=0)
    cols = df.columns
    barcode_col = next((c for c in cols if 'streckkod' in str(c).lower() or 'barcode' in str(c).lower()), cols[0])
    sku_col = next((c for c in cols if 'lagerkod' in str(c).lower() or 'sku' in str(c).lower()), cols[1])
    name_col = next((c for c in cols if 'namn' in str(c).lower() or 'name' in str(c).lower()), cols[2])
    stock_col = next((c for c in cols if 'lagerantal' in str(c).lower() or 'stock' in str(c).lower() or 'antal' in str(c).lower()), cols[3])
    price_col = next((c for c in cols if 'pris' in str(c).lower() or 'price' in str(c).lower()), cols[4])

    for _, row in df.iterrows():
        sku = str(row.get(sku_col, '')).strip()
        raw_name = str(row.get(name_col, '')).strip()
        stock_val = row.get(stock_col, 0)
        price_val = row.get(price_col, '')
        ean = str(row.get(barcode_col, '')).strip()

        if not sku or sku.lower() == 'nan' or not raw_name:
            continue
        try:
            stock = float(str(stock_val).replace(',', '.')) if pd.notna(stock_val) else 0.0
        except ValueError:
            stock = 0.0

        if stock < MIN_STOCK:
            continue

        name = clean_title(raw_name.upper())
        brand = name.split()[0] if name else "UNKNOWN"
        for b in TOP_BRANDS:
            if name.startswith(b) or f" {b} " in name:
                brand = b
                break

        searchable = f"{brand} {name}"
        if BRAND_RE.search(searchable) or MODEL_RE.search(searchable):
            matched_items.append({
                "sku": sku,
                "brand": brand,
                "name": name,
                "stock": int(stock),
                "price": str(price_val).replace(',', '.'),
                "ean": ean if ean.lower() != 'nan' else ""
            })
else:
    # Parse raw live XML response from API
    root = ET.fromstring(data_source)
    for item in root.findall('.//product'):
        sku = item.findtext('sku', default='').strip()
        raw_name = item.findtext('name', default='').strip()
        stock_val = item.findtext('stock', default='0')
        price_val = item.findtext('price', default='0')
        ean = item.findtext('ean', default='').strip()

        try:
            stock = float(stock_val)
        except ValueError:
            stock = 0.0

        if stock < MIN_STOCK:
            continue

        name = clean_title(raw_name.upper())
        brand = name.split()[0] if name else "UNKNOWN"
        for b in TOP_BRANDS:
            if name.startswith(b) or f" {b} " in name:
                brand = b
                break

        searchable = f"{brand} {name}"
        if BRAND_RE.search(searchable) or MODEL_RE.search(searchable):
            matched_items.append({
                "sku": sku,
                "brand": brand,
                "name": name,
                "stock": int(stock),
                "price": price_val,
                "ean": ean
            })

# Sort by highest stock first and trim to target count
matched_items.sort(key=lambda x: x["stock"], reverse=True)
unique_items = matched_items[:EXACT_TARGET_COUNT]

# Save filtered CSV for BaseLinker
with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as outfile:
    writer = csv.DictWriter(outfile, fieldnames=["sku", "brand", "name", "stock", "price", "ean"], delimiter=";")
    writer.writeheader()
    writer.writerows(unique_items)

print(f"\n{OUTPUT_FILE} successfully saved with {len(unique_items)} products!")
