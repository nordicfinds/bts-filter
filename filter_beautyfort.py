import os
import re
import csv
import requests
import pandas as pd
from zeep import Client
from zeep.exceptions import Fault
from lxml import etree

# ============ SETTINGS ============
EXACT_TARGET_COUNT = 150  # 150 from Beautyfort + 150 from BTS = 300 total
MIN_STOCK = 5
OUTPUT_FILE = "beautyfort_filtered.csv"

WSDL_URL = "https://www.beautyfort.com/api/wsdl.wsdl"
USERNAME = "nordicfinds"
SECRET_KEY = "Wh0t7BJpwvkPLIdGbu6KMjYlU1DAx8me2n"

# Quotas
HUGO_BOSS_TERMS = ["HUGO BOSS", "BOSS"]
ARMANI_TERMS = ["GIORGIO ARMANI", "ARMANI"]
GUCCI_TERMS = ["GUCCI"]
DG_TERMS = ["DOLCE & GABBANA", "DOLCE"]

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
    "CK ONE", "ETERNITY", "EUPHORIA", "CK BE", "GOOD GIRL", "BAD BOY", "212",
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

def fetch_image_by_ean(ean):
    """Fetches high-res product photo from free EAN database."""
    clean_ean = re.sub(r"\D", "", str(ean))
    if not clean_ean or len(clean_ean) < 8:
        return ""
    # Take first EAN if multiple comma-separated exist
    first_ean = clean_ean.split(',')[0] if ',' in clean_ean else clean_ean
    try:
        url = f"https://world.openfoodfacts.org/api/v0/product/{first_ean}.json"
        res = requests.get(url, timeout=2).json()
        if res.get("status") == 1:
            prod = res.get("product", {})
            return prod.get("image_front_url") or prod.get("image_url") or ""
    except Exception:
        pass
    return ""

def fetch_live_soap_catalog():
    print(f"Connecting to Beauty Fort SOAP API ({WSDL_URL})...")
    try:
        client = Client(WSDL_URL)
        header_element = etree.Element('{http://www.beautyfort.com/api/}AuthHeader')
        user_elem = etree.SubElement(header_element, '{http://www.beautyfort.com/api/}username')
        user_elem.text = USERNAME
        secret_elem = etree.SubElement(header_element, '{http://www.beautyfort.com/api/}secret')
        secret_elem.text = SECRET_KEY

        response = client.service.GetStockFile(
            StockFileFormat="excel",
            SortBy="sku",
            _soapheaders=[header_element]
        )
        if isinstance(response, str) and response.startswith('http'):
            file_resp = requests.get(response, timeout=30)
            file_resp.raise_for_status()
            temp_filename = "live_soap_stock.xlsx"
            with open(temp_filename, "wb") as f:
                f.write(file_resp.content)
            return temp_filename
        return response
    except Exception as e:
        print(f"SOAP API Connection Error / Fallback: {e}")
        return None

matched_items = []
soap_result = fetch_live_soap_catalog()
data_source = soap_result if soap_result else next((f for f in os.listdir('.') if f.startswith('lagerfil') and f.endswith('.xlsx')), None)

def process_row(sku, raw_name, stock_val, price_val, ean):
    if not sku or sku.lower() == 'nan' or not raw_name:
        return None
    try:
        stock = float(str(stock_val).replace(',', '.')) if pd.notna(stock_val) else 0.0
    except ValueError:
        stock = 0.0

    if stock < MIN_STOCK:
        return None

    name = clean_title(raw_name.upper())
    brand = name.split()[0] if name else "UNKNOWN"
    for b in TOP_BRANDS:
        if name.startswith(b) or f" {b} " in name:
            brand = b
            break

    searchable = f"{brand} {name}"
    if BRAND_RE.search(searchable) or MODEL_RE.search(searchable):
        category = "general"
        if any(t in searchable for t in HUGO_BOSS_TERMS):
            category = "boss"
        elif any(t in searchable for t in ARMANI_TERMS):
            category = "armani"
        elif any(t in searchable for t in GUCCI_TERMS):
            category = "gucci"
        elif any(t in searchable for t in DG_TERMS):
            category = "dg"

        return {
            "sku": sku,
            "brand": brand,
            "name": name,
            "stock": int(stock),
            "price": str(price_val).replace(',', '.'),
            "ean": ean if str(ean).lower() != 'nan' else "",
            "_category": category
        }
    return None

if isinstance(data_source, str) and data_source.endswith('.xlsx'):
    df = pd.read_excel(data_source, header=0)
    cols = df.columns
    barcode_col = next((c for c in cols if 'streckkod' in str(c).lower() or 'barcode' in str(c).lower()), cols[0])
    sku_col = next((c for c in cols if 'lagerkod' in str(c).lower() or 'sku' in str(c).lower()), cols[1])
    name_col = next((c for c in cols if 'namn' in str(c).lower() or 'name' in str(c).lower()), cols[2])
    stock_col = next((c for c in cols if 'lagerantal' in str(c).lower() or 'stock' in str(c).lower() or 'antal' in str(c).lower()), cols[3])
    price_col = next((c for c in cols if 'pris' in str(c).lower() or 'price' in str(c).lower()), cols[4])

    for _, row in df.iterrows():
        item = process_row(
            str(row.get(sku_col, '')).strip(),
            str(row.get(name_col, '')).strip(),
            row.get(stock_col, 0),
            row.get(price_col, ''),
            str(row.get(barcode_col, '')).strip()
        )
        if item:
            matched_items.append(item)

matched_items.sort(key=lambda x: x["stock"], reverse=True)

boss_items = [i for i in matched_items if i['_category'] == 'boss'][:20]
armani_items = [i for i in matched_items if i['_category'] == 'armani'][:20]
gucci_items = [i for i in matched_items if i['_category'] == 'gucci'][:10]
dg_items = [i for i in matched_items if i['_category'] == 'dg'][:10]

selected_skus = {i['sku'] for i in boss_items + armani_items + gucci_items + dg_items}
unique_items = boss_items + armani_items + gucci_items + dg_items

remaining_slots = EXACT_TARGET_COUNT - len(unique_items)
if remaining_slots > 0:
    general_items = [i for i in matched_items if i['sku'] not in selected_skus]
    unique_items.extend(general_items[:remaining_slots])

unique_items = unique_items[:EXACT_TARGET_COUNT]

print("Fetching product image URLs via EAN database...")
clean_output_items = []
for item in unique_items:
    img_url = fetch_image_by_ean(item["ean"])
    clean_output_items.append({
        "sku": item["sku"],
        "brand": item["brand"],
        "name": item["name"],
        "stock": item["stock"],
        "price": item["price"],
        "ean": item["ean"],
        "image": img_url
    })

with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as outfile:
    writer = csv.DictWriter(outfile, fieldnames=["sku", "brand", "name", "stock", "price", "ean", "image"], delimiter=";")
    writer.writerows(clean_output_items)

print(f"\n{OUTPUT_FILE} successfully updated with images!")
