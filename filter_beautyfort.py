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

# Target Curated List of High-Demand Designer Brands & Models
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
    title_upper = title_str.upper()
    for b in TOP_BRANDS:
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
        raise Exception(f"API request failed with status code: {response.status_code}")
    return response.text

raw_xml = fetch_beautyfort_catalog()
print("Received SOAP response. Extracting products...")

matched_items = []

try:
    # Strip namespaces for clean parsing
    clean_xml = re.sub(r'\sxmlns="[^"]+"', '', raw_xml, count=0)
    clean_xml = re.sub(r'xmlns:[a-zA-Z0-9]+="[^"]+"', '', clean_xml)
    root = ET.fromstring(clean_xml)
    
    # Locate item nodes across potential XML container elements
    items_elements = root.findall('.//StockFileItem') or root.findall('.//item') or root.findall('.//row')
    if not items_elements:
        items_elements = list(root.iter())

    for elem in items_elements:
        sku, full_name, stock_str, price_str, ean, xml_brand = '', '', '', '', '', ''
        
        for child in elem:
            tag_name = child.tag.split('}')[-1].lower()
            val = child.text.strip() if child.text else ''
            
            if tag_name in ['stockcode', 'sku', 'code']:
                sku = val
            elif tag_name in ['fullname', 'name', 'description', 'title']:
                if len(val) > len(full_name):
                    full_name = val
            elif tag_name in ['brand']:
                xml_brand = val
            elif tag_name in ['quantity', 'stock', 'stocklevel', 'qty']:
                stock_str = val
            elif tag_name in ['price', 'lastpurchasedprice', 'cost']:
                price_str = val
            elif tag_name in ['barcode', 'ean', 'upc']:
                ean = val

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

        # Match against either explicit brand OR specific model terms
        is_brand_match = any(b in brand for b in TOP_BRANDS) or any(b in cleaned_name for b in TOP_BRANDS)
        is_model_match = any(m in cleaned_name for m in TOP_MODELS)

        if is_brand_match or is_model_match:
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

print(f"Successfully matched {len(unique_items)} designer items with stock >= {MIN_STOCK}.")

with open("beautyfort_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
    fieldnames = ['sku', 'brand', 'name', 'stock', 'price', 'ean']
    writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=';')
    writer.writeheader()
    writer.writerows(unique_items)

print("beautyfort_filtered.csv updated successfully!")
