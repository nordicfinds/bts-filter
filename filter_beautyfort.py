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

    headers = {'Content-Type': 'text/xml; charset=UTF-8', 'Accept': 'text/xml'}
    response = requests.post(API_ENDPOINT, data=soap_envelope, headers=headers, timeout=60)
    if response.status_code != 200:
        raise Exception(f"API request failed: {response.status_code}")
    return response.text

raw_xml = fetch_beautyfort_catalog()
print("Received SOAP response. Inspecting raw catalog items...")

try:
    root = ET.fromstring(raw_xml)
    count = 0
    
    for elem in root.iter():
        sku, full_name, stock_str = '', '', ''
        for child in elem:
            t = child.tag.split('}')[-1].lower()
            val = child.text.strip() if child.text else ''
            if t in ['stockcode', 'sku', 'code']:
                sku = val
            elif t in ['fullname', 'name', 'description', 'title']:
                if len(val) > len(full_name):
                    full_name = val
            elif t in ['quantity', 'stock', 'stocklevel', 'qty']:
                stock_str = val

        if sku and full_name and count < 5:
            print(f"SAMPLE ITEM -> SKU: {sku} | Stock: '{stock_str}' | Name: {full_name}")
            count += 1

except Exception as e:
    print(f"Error: {e}")

# Write empty file to prevent git errors for now while inspecting logs
with open("beautyfort_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
    writer = csv.writer(outfile, delimiter=';')
    writer.writerow(['sku', 'brand', 'name', 'stock', 'price', 'ean', 'image'])
