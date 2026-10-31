import csv
import re
import base64
import hashlib
import time
import uuid
from zeep import Client, Settings
import requests

WSDL_URL = "https://www.beautyfort.com/api/wsdl/wsdl.wsdl"
API_USERNAME = "Base.com"
API_SECRET = "JfPciKxq"
TEST_MODE = "false"

# Strict Curated List of High-Demand Designer Bestsellers & Brands
TOP_MODELS = [
    "SAUVAGE", "FAHRENHEIT", "J'ADORE", "JADORE", "MISS DIOR", "DIOR HOMME", "DIOR",
    "BLEU DE CHANEL", "COCO MADEMOISELLE", "ALLURE HOMME", "CHANCE", "N°5", "CHANEL",
    "EROS", "DYLAN BLUE", "BRIGHT CRYSTAL", "EROS FLAME", "VERSACE",
    "ACQUA DI GIO", "STRONGER WITH YOU", "MY WAY", "SI PASSIONE", "ARMANI CODE", "ARMANI",
    "BLACK OPIUM", "LIBRE", "YSL Y", "Y HOMME", "MON PARIS", "YSL", "YVES SAINT LAURENT",
    "1 MILLION", "ONE MILLION", "INVICTUS", "PHANTOM", "OLYMPEA", "LADY MILLION", "RABANNE",
    "LIGHT BLUE", "THE ONE", "K BY DOLCE", "DEVOTION", "DOLCE & GABBANA", "DOLCE",
    "BOSS BOTTLED", "THE SCENT", "HUGO MAN", "BOSS ALIVE", "BOSS FEMME", "HUGO BOSS", "BOSS",
    "GUCCI BLOOM", "GUCCI GUILTY", "FLORA GORGEOUS", "MEMOIRE", "GUCCI",
    "PRADA LUNA ROSSA", "PARADOXE", "PRADA CANDY", "PRADA",
    "BURBERRY HER", "BURBERRY GODDESS", "MR BURBERRY", "LONDON FOR MEN", "BURBERRY",
    "CK ONE", "ETERNITY", "EUPHORIA", "CK BE", "CALVIN KLEIN",
    "GOOD GIRL", "BAD BOY", "212 VIP", "CAROLINA HERRERA",
    "LE MALE", "SCANDAL", "ULTRA MALE", "DIVINE", "GAULTIER",
    "BLACK ORCHID", "OMBRÉ LEATHER", "OMBRE LEATHER", "NEROLI PORTOFINO", "TOBACCO VANILLE", "TOM FORD",
    "TERRE D'HERMES", "H24", "BVLGARI MAN", "OMNIA", "HERMES", "BVLGARI"
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
    unwanted_terms = [r'\bSpray\b', r'\bSprej\b', r'\bVaporisateur\b', r'\bVapo\b']
    cleaned = title_str
    for term in unwanted_terms:
        cleaned = re.sub(term, '', cleaned, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', cleaned).strip()

def extract_brand(title_str):
    known_brands = [
        "ABERCROMBIE & FITCH", "CAROLINA HERRERA", "DOLCE & GABBANA", 
        "JEAN PAUL GAULTIER", "YVES SAINT LAURENT", "HUGO BOSS", "CALVIN KLEIN",
        "GIORGIO ARMANI", "PACO RABANNE", "TOM FORD", "DIOR", "CHANEL", 
        "VERSACE", "GUCCI", "PRADA", "BURBERRY", "HERMES", "BVLGARI", "ARMANI", "YSL", "BOSS", "CK"
    ]
    title_upper = title_str.upper()
    for b in known_brands:
        if title_upper.startswith(b) or f" {b} " in title_upper:
            return b
    words = title_str.split()
    return " ".join(words[:2]).upper() if len(words) >= 2 else title_str.upper()

print("Initializing Zeep SOAP client with official WSDL...")
settings = Settings(strict=False)
client = Client(WSDL_URL, settings=settings)

# Generate WS-Security authentication headers
nonce = uuid.uuid4().hex[:16]
created = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
raw_str = f"{nonce}{created}{API_SECRET}"
sha1_hex = hashlib.sha1(raw_str.encode('utf-8')).hexdigest()
password = base64.b64encode(sha1_hex.encode('utf-8')).decode('utf-8')

auth_header = client.get_type('ns0:AuthHeader')(
    Username=API_USERNAME,
    Nonce=nonce,
    Created=created,
    Password=password
)

print("Requesting stock file from Beauty Fort API...")
try:
    response = client.service.GetStockFile(
        TestMode=TEST_MODE,
        StockFileFormat="XML",
        StockFileFields={
            'StockFileField': [
                'StockCode',
                'FullName',
                'Brand',
                'Collection',
                'Quantity',
                'Price',
                'Barcode'
            ]
        },
        SortBy="FullName",
        StockFileEncoding="UTF-8",
        _soapheaders=[auth_header]
    )
except Exception as e:
    print(f"SOAP API Call Failed: {e}")
    response = None

matched_items = []

if response:
    print("SOAP response received successfully. Processing catalog...")
    items_list = response if isinstance(response, (list, tuple)) else getattr(response, 'StockFileItem', []) or getattr(response, 'item', []) or []
    
    for row in items_list:
        sku = str(getattr(row, 'StockCode', '') or '').strip()
        full_name = str(getattr(row, 'FullName', '') or '').strip()
        xml_brand = str(getattr(row, 'Brand', '') or '').strip()
        stock_val = getattr(row, 'Quantity', 0)
        price_val = getattr(row, 'Price', '')
        ean_val = str(getattr(row, 'Barcode', '') or '').strip()

        if not sku or not full_name:
            continue

        try:
            stock = float(stock_val) if stock_val is not None else 0.0
        except (ValueError, TypeError):
            stock = 0.0

        if stock < MIN_STOCK:
            continue

        brand = xml_brand.upper() if xml_brand else extract_brand(full_name)
        cleaned_name = clean_title(full_name.upper())

        if any(model in cleaned_name for model in TOP_MODELS):
            matched_items.append({
                'sku': sku,
                'brand': brand,
                'name': cleaned_name,
                'stock': int(stock),
                'price': clean_price(price_val),
                'ean': ean_val
            })

seen_skus = set()
unique_items = []
for item in matched_items:
    if item['sku'] not in seen_skus:
        seen_skus.add(item['sku'])
        unique_items.append(item)
    if len(unique_items) >= EXACT_TARGET_COUNT:
        break

print(f"Successfully matched {len(unique_items)} designer bestsellers with stock >= {MIN_STOCK}.")

with open("beautyfort_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
    fieldnames = ['sku', 'brand', 'name', 'stock', 'price', 'ean']
    writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=';')
    writer.writeheader()
    writer.writerows(unique_items)

print("beautyfort_filtered.csv successfully updated!")
