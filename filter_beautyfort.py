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

# Target Designer Keywords
DESIGNER_KEYWORDS = [
    "SAUVAGE", "FAHRENHEIT", "J'ADORE", "JADORE", "MISS DIOR", "DIOR",
    "BLEU DE CHANEL", "COCO", "ALLURE", "CHANCE", "CHANEL",
    "EROS", "DYLAN BLUE", "BRIGHT CRYSTAL", "VERSACE",
    "ACQUA DI GIO", "STRONGER WITH YOU", "MY WAY", "ARMANI",
    "BLACK OPIUM", "LIBRE", "YSL", "OPIUM",
    "1 MILLION", "ONE MILLION", "INVICTUS", "PHANTOM", "OLYMPEA", "RABANNE",
    "LIGHT BLUE", "THE ONE", "DOLCE", "GABBANA",
    "BOSS BOTTLED", "HUGO", "BOSS",
    "GUCCI", "BLOOM", "GUILTY",
    "PRADA", "LUNA ROSSA", "PARADOXE",
    "BURBERRY", "HERO",
    "CK ONE", "ETERNITY", "EUPHORIA", "CALVIN KLEIN",
    "GOOD GIRL", "BAD BOY", "CAROLINA HERRERA",
    "GAULTIER", "LE MALE", "SCANDAL",
    "TOM FORD", "HERMES", "BVLGARI"
]

EXACT_TARGET_COUNT = 150
MIN_STOCK = 1

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

def fetch_beautyfort_catalog():
    print("Generating Beauty Fort WS-Security Authentication headers...")
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

    headers = {
        'Content-Type': 'text/xml; charset=UTF-8',
        'Accept': 'text/xml'
    }

    response = requests.post(API_ENDPOINT, data=soap_envelope, headers=headers, timeout=60)
    if response.status_code != 200:
        raise Exception(f"API request failed with status {response.status_code}: {response.text}")

    return response.text

raw_xml = fetch_beautyfort_catalog()
print("Successfully received SOAP XML catalog payload.")

matched_items = []
fallback_items = []

try:
    root = ET.fromstring(raw_xml)
    total_parsed = 0

    # Scan through XML elements
    for elem in root.iter():
        sku, name, stock_str, price_str, ean = '', '', '0', '', ''
        
        for child in elem:
            t = child.tag.split('}')[-1].lower()
            if t in ['stockcode', 'sku', 'code']:
                sku = child.text or ''
            elif t in ['fullname', 'name', 'description', 'title']:
                if child.text and len(child.text.strip()) > len(name):
                    name = child.text.strip()
            elif t in ['quantity', 'stock', 'stocklevel', 'qty']:
                stock_str = child.text or '0'
            elif t in ['price', 'lastpurchasedprice', 'cost']:
                price_str = child.text or ''
            elif t in ['barcode', 'ean', 'upc']:
                ean = child.text or ''

        if not sku or not name:
            continue

        total_parsed += 1

        try:
            stock = float(stock_str)
        except ValueError:
            stock = 0.0

        if stock < MIN_STOCK:
            continue

        product_dict = {
            'sku': sku,
            'name': clean_title(name.upper()),
            'stock': int(stock),
            'price': clean_price(price_str),
            'ean': ean
        }

        upper_name = product_dict['name']
        if any(kw in upper_name for kw in DESIGNER_KEYWORDS):
            matched_items.append(product_dict)
        else:
            fallback_items.append(product_dict)

    print(f"Total parsed items with valid SKU/Name: {total_parsed}")
    print(f"Matched {len(matched_items)} designer items, {len(fallback_items)} fallback items.")

except Exception as e:
    print(f"Error parsing XML catalog: {e}")

# Combine matched first, then fallback to reach 150 items
final_selected = (matched_items + fallback_items)[:EXACT_TARGET_COUNT]

# Deduplicate by SKU
seen_skus = set()
unique_final = []
for item in final_selected:
    if item['sku'] not in seen_skus:
        seen_skus.add(item['sku'])
        unique_final.append(item)

print(f"Writing {len(unique_final)} items to beautyfort_filtered.csv...")

with open("beautyfort_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
    fieldnames = ['sku', 'name', 'stock', 'price', 'ean']
    writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=';')
    writer.writeheader()
    writer.writerows(unique_final)

print("beautyfort_filtered.csv updated successfully!")
