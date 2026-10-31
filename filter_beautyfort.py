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

# Top Designer Brands & Bestsellers to search for inside the title
DESIGNER_KEYWORDS = [
    "SAUVAGE", "DIOR", "CHANEL", "BLEU DE CHANEL", "VERSACE", "EROS",
    "ARMANI", "ACQUA DI GIO", "YSL", "YVES SAINT LAURENT", "BLACK OPIUM",
    "PACO RABANNE", "1 MILLION", "ONE MILLION", "INVICTUS", "DOLCE", "GABBANA",
    "HUGO BOSS", "BOSS", "GUCCI", "PRADA", "BURBERRY", "CALVIN KLEIN", "CK",
    "CAROLINA HERRERA", "GAULTIER", "JEAN PAUL GAULTIER", "TOM FORD", "HERMES", "BVLGARI"
]

EXACT_TARGET_COUNT = 150
MIN_STOCK = 5  # Updated minimum stock threshold to 5

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
				<bf:StockFileField>ImageURL</bf:StockFileField>
			</bf:StockFileFields>
			<bf:SortBy>FullName</bf:SortBy>
			<bf:StockFileEncoding>UTF-8</bf:StockFileEncoding>
		</bf:GetStockFileRequest>
    </soap:Body>
</soap:Envelope>"""

    headers = {
        'Content-Type': 'text/xml; charset=UTF-8',
        'Accept': 'text/xml'
    }

    response = requests.post(API_ENDPOINT, data=soap_envelope, headers=headers, timeout=60)
    if response.status_code != 200:
        raise Exception(f"API request failed with status {response.status_code}: {response.text}")

    return response.text

raw_xml = fetch_beautyfort_catalog()
print("Received SOAP response. Extracting products...")

matched_items = []
fallback_items = []

try:
    root = ET.fromstring(raw_xml)
    
    for elem in root.iter():
        sku, full_name, stock_str, price_str, ean, image_url, xml_brand = '', '', '0', '', '', '', ''
        
        for child in elem:
            t = child.tag.split('}')[-1].lower()
            if t in ['stockcode', 'sku', 'code']:
                sku = child.text or ''
            elif t in ['fullname', 'name', 'description', 'title']:
                if child.text and len(child.text.strip()) > len(full_name):
                    full_name = child.text.strip()
            elif t in ['brand']:
                xml_brand = child.text or ''
            elif t in ['quantity', 'stock', 'stocklevel', 'qty']:
                stock_str = child.text or '0'
            elif t in ['price', 'lastpurchasedprice', 'cost']:
                price_str = child.text or ''
            elif t in ['barcode', 'ean', 'upc']:
                ean = child.text or ''
            elif t in ['imageurl', 'image', 'picture', 'photo']:
                image_url = child.text or ''

        if not sku or not full_name:
            continue

        try:
            stock = float(stock_str)
        except ValueError:
            stock = 0.0

        # Filters out anything under stock of 5
        if stock < MIN_STOCK:
            continue

        brand = xml_brand.strip().upper() if xml_brand else extract_brand(full_name)
        cleaned_name = clean_title(full_name.upper())

        item = {
            'sku': sku,
            'brand': brand,
            'name': cleaned_name,
            'stock': int(stock),
            'price': clean_price(price_str),
            'ean': ean,
            'image': image_url
        }

        if any(kw in cleaned_name for kw in DESIGNER_KEYWORDS):
            matched_items.append(item)
        else:
            fallback_items.append(item)

except Exception as e:
    print(f"Error parsing XML catalog: {e}")

combined_items = matched_items + fallback_items

seen_skus = set()
unique_items = []
for item in combined_items:
    if item['sku'] not in seen_skus:
        seen_skus.add(item['sku'])
        unique_items.append(item)
    if len(unique_items) >= EXACT_TARGET_COUNT:
        break

print(f"Successfully extracted {len(unique_items)} items with stock >= {MIN_STOCK}.")

with open("beautyfort_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
    fieldnames = ['sku', 'brand', 'name', 'stock', 'price', 'ean', 'image']
    writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=';')
    writer.writeheader()
    writer.writerows(unique_items)

print("beautyfort_filtered.csv updated successfully!")
