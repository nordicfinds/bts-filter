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

# Priority 1: Top-selling model names for Nordic market
TOP_MODELS = [
    "BOSS BOTTLED", "THE SCENT", "HUGO MAN", "BOSS ALIVE", "BOSS FEMME", "HUGO DEEP RED", "BOSS ORANGE",
    "SAUVAGE", "FAHRENHEIT", "J'ADORE", "MISS DIOR",
    "BLACK OPIUM", "LIBRE", "YSL Y", "OPIUM",
    "ACQUA DI GIO", "STRONGER WITH YOU", "MY WAY", "SI",
    "1 MILLION", "ONE MILLION", "INVICTUS", "PHANTOM", "OLYMPEA",
    "BLEU DE CHANEL", "COCO MADEMOISELLE", "ALLURE",
    "MONTBLANC EXPLORER", "MONTBLANC LEGEND",
    "EROS", "DYLAN BLUE", "LIGHT BLUE", "K BY DOLCE",
    "HERO", "BURBERRY HER", "CK ONE", "ETERNITY", "EUPHORIA", "LÉ MALE", "DIVINE", "SCANDAL"
]

# Priority 2: General brand fallbacks
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

def fetch_beautyfort_catalog():
    print("Generating Beauty Fort WS-Security Authentication headers...")
    
    nonce = uuid.uuid4().hex[:16]
    created = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    
    # Password formula: base64_encode(sha1(nonce . created . secret)) using binary digest
    raw_str = f"{nonce}{created}{API_SECRET}"
    sha1_binary = hashlib.sha1(raw_str.encode('utf-8')).digest()
    password = base64.b64encode(sha1_binary).decode('utf-8')

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

    print("Sending SOAP request to Beauty Fort...")
    response = requests.post(API_ENDPOINT, data=soap_envelope, headers=headers, timeout=60)
    print(f"Response Status Code: {response.status_code}")

    if response.status_code != 200:
        raise Exception(f"API request failed with status {response.status_code}: {response.text}")

    return response.text

raw_xml = fetch_beautyfort_catalog()
print("Successfully received SOAP XML catalog payload.")

top_sellers = []
brand_fallbacks = []

try:
    root = ET.fromstring(raw_xml)
    for elem in root.iter():
        if elem.tag.endswith('StockFileItem') or elem.tag.endswith('item') or elem.tag.endswith('Product'):
            sku = ''
            name = ''
            stock_str = '0'
            price_str = ''
            ean = ''
            
            for child in elem:
                tag_lower = child.tag.split('}')[-1].lower()
                if tag_lower in ['stockcode', 'sku']:
                    sku = child.text or ''
                elif tag_lower in ['fullname', 'name', 'description']:
                    name = (child.text or '').upper()
                elif tag_lower in ['quantity', 'stock', 'stocklevel']:
                    stock_str = child.text or '0'
                elif tag_lower in ['price', 'lastpurchasedprice']:
                    price_str = child.text or ''
                elif tag_lower in ['barcode', 'ean']:
                    ean = child.text or ''

            try:
                stock = float(stock_str)
            except ValueError:
                stock = 0

            if stock < MIN_STOCK or not name:
                continue

            product_dict = {
                'sku': sku,
                'name': clean_title(name),
                'stock': int(stock),
                'price': clean_price(price_str),
                'ean': ean
            }

            if any(model in name for model in TOP_MODELS):
                top_sellers.append(product_dict)
            elif any(brand in name for brand in TARGET_BRANDS):
                brand_fallbacks.append(product_dict)
                
except Exception as e:
    print(f"Error parsing XML catalog: {e}")

top_sellers.sort(key=lambda x: x['stock'], reverse=True)
brand_fallbacks.sort(key=lambda x: x['stock'], reverse=True)

final_selected = (top_sellers + brand_fallbacks)[:EXACT_TARGET_COUNT]

print(f"Matched {len(top_sellers)} top models and {len(brand_fallbacks)} brand fallbacks.")
print(f"Exporting top {len(final_selected)} items to beautyfort_filtered.csv...")

if final_selected:
    with open("beautyfort_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
        fieldnames = ['sku', 'name', 'stock', 'price', 'ean']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(final_selected)
    print("beautyfort_filtered.csv successfully created!")
else:
    print("Warning: No products matched criteria or catalog was empty.")
