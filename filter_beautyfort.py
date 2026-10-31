import os
import re
import csv
import requests
import pandas as pd
from zeep import Client
from zeep.exceptions import Fault
from lxml import etree

# ============ SETTINGS ============
EXACT_TARGET_COUNT = 150
MIN_STOCK = 5
OUTPUT_FILE = "beautyfort_filtered.csv"

WSDL_URL = "https://www.beautyfort.com/api/wsdl.wsdl"
USERNAME = "Base.com"
SECRET_KEY = "JfPciKxq"

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

def fetch_live_soap_catalog():
    print(f"Connecting to Beauty Fort SOAP API ({WSDL_URL})...")
    try:
        client = Client(WSDL_URL)
        
        header_element = etree.Element('{http://www.beautyfort.com/api/}AuthHeader')
        user_elem = etree.SubElement(header_element, '{http://www.beautyfort.com/api/}username')
        user_elem.text = USERNAME
        secret_elem = etree.SubElement(header_element, '{http://www.beautyfort.com/api/}secret')
        secret_elem.text = SECRET_KEY

        print("Calling SOAP method: GetStockFile with format and sorting")
        response = client.service.GetStockFile(
            StockFileFormat="excel",
            SortBy="sku",
            _soapheaders=[header_element]
        )
        
        if isinstance(response, str) and response.startswith('http'):
            print(f"Downloading live stock file from URL: {response}")
            file_resp = requests.get(response, timeout=30)
            file_resp.raise_for_status()
            temp_filename = "live_soap_stock.xlsx"
            with open(temp_filename, "wb") as f:
                f.write(file_resp.content)
            return temp_filename
            
        return response
    except Fault as f:
        print(f"SOAP Fault Error: {f}")
        return None
    except Exception as e:
        print(f"SOAP API Connection Error: {e}")
        return None

matched_items = []
soap_result = fetch_live_soap_catalog()

data_source = soap_result
if not data_source:
    print("Falling back to local spreadsheet file...")
    excel_files = [f for f in os.listdir('.') if f.startswith('lagerfil') and f.endswith('.xlsx')]
    if not excel_files:
        raise SystemExit("No API data or local Excel file available.")
    data_source = excel_files[0]

if isinstance(data_source, str) and data_source.endswith('.xlsx'):
    print(f"Reading inventory data from: {data_source}")
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
    print("Processing direct SOAP object list...")
    for item in soap_result:
        sku = str(getattr(item, 'sku', getattr(item, 'code', ''))).strip()
        raw_name = str(getattr(item, 'name', getattr(item, 'description', ''))).strip()
        stock_val = getattr(item, 'stock', getattr(item, 'quantity', 0))
        price_val = getattr(item, 'price', 0)
        ean = str(getattr(item, 'barcode', getattr(item, 'ean', ''))).strip()

        try:
            stock = float(stock_val)
        except (ValueError, TypeError):
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
                "ean": ean
            })

matched_items.sort(key=lambda x: x["stock"], reverse=True)
unique_items = matched_items[:EXACT_TARGET_COUNT]

with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as outfile:
    writer = csv.DictWriter(outfile, fieldnames=["sku", "brand", "name", "stock", "price", "ean"], delimiter=";")
    writer.writeheader()
    writer.writerows(unique_items)

print(f"\n{OUTPUT_FILE} successfully saved with {len(unique_items)} products!")
