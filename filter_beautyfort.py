import os
import re
import csv
import requests
import pandas as pd
from zeep import Client
from lxml import etree

EXACT_TARGET_COUNT = 150
MIN_STOCK = 5
OUTPUT_FILE = "beautyfort_filtered.csv"

WSDL_URL = "https://www.beautyfort.com/api/wsdl.wsdl"
USERNAME = "nordicfinds"
SECRET_KEY = "Wh0t7BJpwvkPLIdGbu6KMjYlU1DAx8me2n"

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
    "BLACK OPIUM", "LIBRE", "MON PARIS", "1 MILLION", "ONE MILLION", "INVICTUS",
    "PHANTOM", "OLYMPEA", "LIGHT BLUE", "THE ONE", "BOSS BOTTLED", "THE SCENT"
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

def fetch_live_soap_catalog():
    try:
        client = Client(WSDL_URL)
        header_element = etree.Element('{http://www.beautyfort.com/api/}AuthHeader')
        etree.SubElement(header_element, '{http://www.beautyfort.com/api/}username').text = USERNAME
        etree.SubElement(header_element, '{http://www.beautyfort.com/api/}secret').text = SECRET_KEY
        response = client.service.GetStockFile(StockFileFormat="excel", SortBy="sku", _soapheaders=[header_element])
        if isinstance(response, str) and response.startswith('http'):
            file_resp = requests.get(response, timeout=30)
            with open("live_soap_stock.xlsx", "wb") as f:
                f.write(file_resp.content)
            return "live_soap_stock.xlsx"
        return response
    except Exception:
        return None

matched_items = []
soap_result = fetch_live_soap_catalog()
data_source = soap_result if soap_result else next((f for f in os.listdir('.') if f.startswith('lagerfil') and f.endswith('.xlsx')), None)

def process_row(sku, raw_name, stock_val, price_val, ean, img_raw):
    if not sku or sku.lower() == 'nan' or not raw_name: return None
    try: stock = float(str(stock_val).replace(',', '.')) if pd.notna(stock_val) else 0.0
    except ValueError: stock = 0.0
    if stock < MIN_STOCK: return None

    name = clean_title(raw_name.upper())
    brand = name.split()[0] if name else "UNKNOWN"
    for b in TOP_BRANDS:
        if name.startswith(b) or f" {b} " in name: brand = b; break

    searchable = f"{brand} {name}"
    if BRAND_RE.search(searchable) or MODEL_RE.search(searchable):
        cat = "boss" if any(t in searchable for t in HUGO_BOSS_TERMS) else \
              "armani" if any(t in searchable for t in ARMANI_TERMS) else \
              "gucci" if any(t in searchable for t in GUCCI_TERMS) else \
              "dg" if any(t in searchable for t in DG_TERMS) else "general"
        
        # Determine image URL directly from BeautyFort row data or direct CDN pattern
        img_url = str(img_raw).strip() if pd.notna(img_raw) and str(img_raw).startswith("http") else f"https://www.beautyfort.com/images/products/{sku}.jpg"

        return {
            "sku": sku,
            "brand": brand,
            "name": name,
            "stock": int(stock),
            "price": str(price_val).replace(',', '.'),
            "ean": ean if str(ean).lower() != 'nan' else "",
            "image": img_url,
            "_category": cat
        }
    return None

if isinstance(data_source, str) and data_source.endswith('.xlsx'):
    df = pd.read_excel(data_source, header=0)
    cols = df.columns
    
    # Locate column headers dynamically
    img_col = next((c for c in cols if 'bild' in str(c).lower() or 'image' in str(c).lower() or 'url' in str(c).lower()), None)
    
    for _, row in df.iterrows():
        item = process_row(
            str(row.get(cols[1], '')).strip(),
            str(row.get(cols[2], '')).strip(),
            row.get(cols[3], 0),
            row.get(cols[4], ''),
            str(row.get(cols[0], '')).strip(),
            row.get(img_col, '') if img_col else ''
        )
        if item: matched_items.append(item)

matched_items.sort(key=lambda x: x["stock"], reverse=True)
unique_items = [i for i in matched_items if i['_category'] == 'boss'][:20] + \
               [i for i in matched_items if i['_category'] == 'armani'][:20] + \
               [i for i in matched_items if i['_category'] == 'gucci'][:10] + \
               [i for i in matched_items if i['_category'] == 'dg'][:10]

selected_skus = {i['sku'] for i in unique_items}
if len(unique_items) < EXACT_TARGET_COUNT:
    unique_items.extend([i for i in matched_items if i['sku'] not in selected_skus][:EXACT_TARGET_COUNT - len(unique_items)])

clean_output_items = []
for item in unique_items[:EXACT_TARGET_COUNT]:
    clean_output_items.append({
        "sku": item["sku"],
        "brand": item["brand"],
        "name": item["name"],
        "stock": item["stock"],
        "price": item["price"],
        "ean": item["ean"],
        "image": item["image"]
    })

with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["sku", "brand", "name", "stock", "price", "ean", "image"], delimiter=";")
    writer.writerows(clean_output_items)

print("beautyfort_filtered.csv successfully updated with direct image URLs!")
