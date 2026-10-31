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

# Preferred Bestseller Models
TOP_MODELS = [
    "SAUVAGE", "FAHRENHEIT", "J'ADORE", "MISS DIOR", "DIOR HOMME",
    "BLEU DE CHANEL", "COCO MADEMOISELLE", "ALLURE HOMME", "CHANCE", "N°5",
    "EROS", "DYLAN BLUE", "BRIGHT CRYSTAL", "EROS FLAME",
    "ACQUA DI GIO", "STRONGER WITH YOU", "MY WAY", "SI PASSIONE", "ARMANI CODE",
    "BLACK OPIUM", "LIBRE", "YSL Y", "Y HOMME", "MON PARIS",
    "1 MILLION", "ONE MILLION", "INVICTUS", "PHANTOM", "OLYMPEA", "LADY MILLION",
    "LIGHT BLUE", "THE ONE", "K BY DOLCE", "DEVOTION",
    "BOSS BOTTLED", "THE SCENT", "HUGO MAN", "BOSS ALIVE", "BOSS FEMME",
    "GUCCI BLOOM", "GUCCI GUILTY", "FLORA GORGEOUS", "MEMOIRE",
    "PRADA LUNA ROSSA", "PARADOXE", "PRADA CANDY",
    "BURBERRY HER", "BURBERRY GODDESS", "MR BURBERRY", "LONDON FOR MEN",
    "CK ONE", "ETERNITY", "EUPHORIA", "CK BE",
    "GOOD GIRL", "BAD BOY", "212 VIP",
    "LE MALE", "SCANDAL", "ULTRA MALE", "DIVINE",
    "BLACK ORCHID", "OMBRÉ LEATHER", "NEROLI PORTOFINO", "TOBACCO VANILLE",
    "TERRE D'HERMES", "H24", "BVLGARI MAN", "OMNIA"
]

# Designer Brands for fallback filling (prevents empty file outputs)
FALLBACK_BRANDS = [
    "DIOR", "CHANEL", "VERSACE", "ARMANI", "YVES SAINT LAURENT", "YSL", 
    "PACO RABANNE", "DOLCE & GABBANA", "HUGO BOSS", "GUCCI", "PRADA", 
    "BURBERRY", "CALVIN KLEIN", "CAROLINA HERRERA", "JEAN PAUL GAULTIER", 
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

    print("Sending SOAP request to Beauty Fort...")
    response = requests.post(API_ENDPOINT, data=soap_envelope, headers=headers, timeout=60)
    print(f"Response Status Code: {response.status_code}")

    if response.status_code != 200:
        raise Exception(f"API request failed with status {response.status_code}: {response.text}")

    return response.text

raw_xml = fetch_beautyfort_catalog()
print("Successfully received SOAP XML catalog payload. Filtering for designer bestsellers...")

matched_items = []
fallback_items = []

try:
    root = ET.fromstring(raw_xml)
    item_count = 0
    
    for elem in root.iter():
        tag_name = elem.tag.split('}')[-1]
        if 'item' in tag_name.lower() or 'stockfileitem' in tag_name.lower():
            sku, name, stock_str, price_str, ean = '', '', '0', '', ''
            
            for child in elem:
                t = child.tag.split('}')[-1].lower()
                if t in ['stockcode', 'sku']:
                    sku = child.text or ''
                elif t in ['fullname', 'name', 'description']:
                    if child.text and len(child.text.strip()) > len(name):
                        name = child.text.strip()
                elif t in ['quantity', 'stock', 'stocklevel']:
                    stock_str = child.text or '0'
                elif t in ['price', 'lastpurchasedprice']:
                    price_str = child.text or ''
                elif t in ['barcode', 'ean']:
                    ean = child.text or ''

            if not name:
                continue
                
            item_count += 1
            try:
                stock = float(stock_str)
            except ValueError:
                stock = 0

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
            
            # 1. Match against exact TOP_MODELS first
            if any(model in upper_name for model in TOP_MODELS):
                matched_items.append(product_dict)
            # 2. Otherwise, match against FALLBACK_BRANDS
            elif any(brand in upper_name for brand in FALLBACK_BRANDS):
                fallback_items.append(product_dict)
            
    print(f"Scanned {item_count} items. Matched {len(matched_items)} primary bestsellers and {len(fallback_items)} secondary designer items.")

except Exception as e:
    print(f"Error parsing XML catalog: {e}")

# Combine primary matches first, then fill up to 150 using secondary designer items
final_selected = (matched_items + fallback_items)[:EXACT_TARGET_COUNT]

print(f"Exporting total {len(final_selected)} items to beautyfort_filtered.csv...")

with open("beautyfort_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
    fieldnames = ['sku', 'name', 'stock', 'price', 'ean']
    writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=';')
    writer.writeheader()
    writer.writerows(final_selected)

print("beautyfort_filtered.csv successfully created!")
