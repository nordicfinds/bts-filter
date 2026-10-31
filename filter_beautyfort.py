import csv
import re
import base64
import hashlib
import time
import uuid
import requests
import xml.etree.ElementTree as ET

API_ENDPOINT = "https://www.beautyfort.com/api/soap"
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

def fetch_beautyfort_catalog():
    print("Generating Beauty Fort WS-Security authentication headers...")
    nonce = uuid.uuid4().hex[:16]
    created = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    
    raw_str = f"{nonce}{created}{API_SECRET}"
    sha1_hex = hashlib.sha1(raw_str.encode('utf-8')).hexdigest()
    password = base64.b64encode(sha1_hex.encode('utf-8')).decode('utf-8')

    # Removed invalid 'ImageURL' from StockFileFields
    soap_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:bf="http://www.beautyfort.com/api/">
	<soap:Header>
		<bf:AuthHeader>
			<bf:Username>{API_USERNAME}</bf:Username>
			<bf:Nonce>{nonce}</bf:Nonce>
			<bf:Created>{created}</bf:Created>
			<bf:Password>{password}</bf:Password>
		</bf:AuthHeader>
    </soap:Header>
    <soap:Body>
		<bf:GetStockFileRequest>
			<bf:TestMode>{TEST_MODE}</bf:TestMode>
			<bf:StockFileFormat>XML</bf:StockFileFormat>
			<bf:StockFileFields>
				<bf:StockFileField>StockCode</bf:StockFileField>
				<bf:StockFileField>FullName</bf:StockFileField>
				<bf:StockFileField>Brand</bf:StockFileField>
				<bf:StockFileField>Collection</bf:StockFileField>
				<bf:StockFileField>Quantity</bf:StockFileField>
				<bf:StockFileField>Price</bf:StockFileField>
				<bf:StockFileField>Barcode</bf:StockFileField>
			</bf:StockFileFields>
			<bf:SortBy>FullName</bf:SortBy>
			<bf:StockFileEncoding>UTF-8</bf:StockFileEncoding>
		</bf:GetStockFileRequest>
    </soap:Body>
</soap:Envelope>"""

    headers = {'Content-Type': 'text/xml; charset=UTF-8', 'Accept': 'text/xml'}
    response = requests.post(API_ENDPOINT, data=soap_envelope, headers=headers, timeout=60)
    if response.status_code != 200:
        raise Exception(f"API request failed: {response.status_code}")
    return response.text

raw_xml = fetch_beautyfort_catalog()
print("Received SOAP response. Parsing and applying strict bestseller filters...")

matched_items = []

try:
    root = ET.fromstring(raw_xml)
    
    for elem in root.iter():
        sku, full_name, stock_str, price_str, ean, xml_brand = '', '', '', '', '', ''
        
        for child in elem:
            t = child.tag.split('}')[-1].lower()
            val = child.text.strip() if child.text else ''
            
            if t in ['stockcode', 'sku', 'code']:
                sku = val
            elif t in ['fullname', 'name', 'description', 'title']:
                if len(val) > len(full_name):
                    full_name = val
            elif t in ['brand']:
                xml_brand = val
            elif t in ['quantity', 'stock', 'stocklevel', 'qty']:
                stock_str = val
            elif t in ['price', 'lastpurchasedprice', 'cost']:
                price_str = val
            elif t in ['barcode', 'ean', 'upc']:
                ean = val

        # Skip error nodes or invalid rows
        if not sku or not full_name or "Invalid field value" in full_name:
            continue

        try:
            stock = float(re.sub(r'[^0-9\.]', '', stock_str)) if stock_str else 0.0
        except ValueError:
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
                'price': clean_price(price_str),
                'ean': ean
            })

except Exception as e:
    print(f"Parser Error: {e}")

seen_skus = set()
unique_items = []
for item in matched_items:
    if item['sku'] not in seen_skus:
        seen_skus.add(item['sku'])
        unique_items.append(item)
    if len(unique_items) >= EXACT_TARGET_COUNT:
        break

print(f"Successfully matched {len(unique_items)} specific designer bestsellers with stock >= {MIN_STOCK}.")

with open("beautyfort_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
    fieldnames = ['sku', 'brand', 'name', 'stock', 'price', 'ean']
    writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=';')
    writer.writeheader()
    writer.writerows(unique_items)

print("beautyfort_filtered.csv updated successfully!")
