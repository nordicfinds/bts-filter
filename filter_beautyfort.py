import csv
import re
import os
import io
import gzip
import html
import zipfile
import base64
import hashlib
import time
import uuid
import requests
import xml.etree.ElementTree as ET

# ============ SETTINGS ============
API_ENDPOINT = "https://www.beautyfort.com/api/soap"
API_USERNAME = os.environ.get("BF_USERNAME", "Base.com")
API_SECRET = os.environ.get("BF_SECRET", "JfPciKxq")  # Your API secret key
TEST_MODE = "false"

EXACT_TARGET_COUNT = 150
MIN_STOCK = 5
OUTPUT_FILE = "beautyfort_filtered.csv"

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

# Whole-word matching, so "CK" does not match inside "BLACK"
def make_pattern(terms):
    parts = [r"(?<![A-Z0-9])" + re.escape(t) + r"(?![A-Z0-9])" for t in terms]
    return re.compile("|".join(parts))

BRAND_RE = make_pattern(TOP_BRANDS)
MODEL_RE = make_pattern(TOP_MODELS)


# ============ HELPERS ============
def clean_price(val):
    if not val:
        return ""
    return re.sub(r"[^0-9\.]", "", str(val).replace(",", "."))


def clean_title(title_str):
    if not title_str:
        return ""
    cleaned = title_str
    for term in [r"\bSpray\b", r"\bSprej\b", r"\bVaporisateur\b", r"\bVapo\b"]:
        cleaned = re.sub(term, "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_xml(text):
    text = text.lstrip("\ufeff").strip()
    text = re.sub(r"^<\?xml[^>]*\?>", "", text).strip()
    return ET.fromstring(text)


# ============ CONNECT TO API ============
def build_envelope(method):
    nonce = uuid.uuid4().hex[:16]
    created = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    sha1 = hashlib.sha1(f"{nonce}{created}{API_SECRET}".encode("utf-8"))
    if method == "hex":
        password = base64.b64encode(sha1.hexdigest().encode("utf-8")).decode("utf-8")
    else:
        password = base64.b64encode(sha1.digest()).decode("utf-8")

    return f"""<?xml version="1.0" encoding="utf-8"?>
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


def fetch_response():
    headers = {"Content-Type": "text/xml; charset=UTF-8", "Accept": "text/xml"}
    last_text = ""
    for method in ["hex", "raw"]:
        print(f"Connecting to Beauty Fort (login method: {method})...")
        resp = requests.post(API_ENDPOINT, data=build_envelope(method).encode("utf-8"),
                             headers=headers, timeout=120)
        last_text = resp.text
        with open("raw_response.xml", "w", encoding="utf-8") as f:
            f.write(last_text)
        print("HTTP status:", resp.status_code, "| response length:", len(last_text))
        if "faultstring" in last_text.lower() or resp.status_code != 200:
            print("Server answered with an error:")
            print(last_text[:800])
            continue
        return last_text
    print("\nBoth login methods failed. Check username/secret.")
    raise SystemExit(1)


# ============ FIND THE PRODUCT DATA INSIDE THE RESPONSE ============
def bytes_to_xml_texts(data):
    texts = []
    try:
        if data[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for name in z.namelist():
                    texts.extend(bytes_to_xml_texts(z.read(name)))
            return texts
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        text = data.decode("utf-8-sig", errors="replace").strip()
        if text.startswith("<"):
            texts.append(text)
    except Exception:
        pass
    return texts


def decode_blob(txt):
    if txt.startswith("http://") or txt.startswith("https://"):
        print("Found a download link, downloading:", txt[:100])
        try:
            r = requests.get(txt, timeout=180)
            return bytes_to_xml_texts(r.content)
        except Exception as e:
            print("Download failed:", e)
            return []
    if txt.startswith("<"):
        return [txt]
    try:
        raw = base64.b64decode(txt, validate=True)
        return bytes_to_xml_texts(raw)
    except Exception:
        return []


def candidate_documents(xml_text, depth=0):
    docs = [xml_text]
    if depth > 3:
        return docs
    try:
        root = parse_xml(xml_text)
    except ET.ParseError:
        return docs
    for el in root.iter():
        txt = (el.text or "").strip()
        if len(txt) < 30:
            continue
        for found in decode_blob(html.unescape(txt) if "&lt;" in txt else txt):
            docs.extend(candidate_documents(found, depth + 1))
    return docs


# ============ READ PRODUCTS ============
def extract_products(xml_text, tag_counter):
    products = []
    try:
        root = parse_xml(xml_text)
    except ET.ParseError:
        return products

    for elem in root.iter():
        children = list(elem)
        if not children:
            continue
        sku = full_name = stock_str = price_str = ean = xml_brand = ""
        for child in children:
            tag = child.tag.split("}")[-1].lower()
            tag_counter[tag] = tag_counter.get(tag, 0) + 1
            val = child.text.strip() if child.text else ""
            if tag in ("stockcode", "sku", "code"):
                sku = val
            elif tag in ("fullname", "name", "description", "title"):
                if len(val) > len(full_name):
                    full_name = val
            elif tag == "brand":
                xml_brand = val
            elif tag in ("quantity", "stock", "stocklevel", "qty"):
                stock_str = val
            elif tag in ("price", "lastpurchasedprice", "cost"):
                price_str = val
            elif tag in ("barcode", "ean", "upc"):
                ean = val
        if sku and full_name and "Invalid field value" not in full_name:
            products.append((sku, full_name, xml_brand, stock_str, price_str, ean))
    return products


# ============ MAIN ============
raw_response = fetch_response()
print("\nFirst 1500 characters of the response:")
print(raw_response[:1500])
print("-" * 60)

documents = candidate_documents(raw_response)
print(f"Found {len(documents)} data block(s) to search.")

tag_counter = {}
all_products = []
for d in documents:
    all_products.extend(extract_products(d, tag_counter))

print(f"Products found in the response: {len(all_products)}")

if not all_products:
    print("\nNO PRODUCTS FOUND. Tag names seen in the data:")
    print(sorted(tag_counter.items(), key=lambda x: -x[1])[:25])
    raise SystemExit(1)

seen = set()
unique_items = []
too_low_stock = 0
non_empty_stock_count = 0

for sku, full_name, xml_brand, stock_str, price_str, ean in all_products:
    if sku in seen:
        continue
    seen.add(sku)

    if stock_str:
        non_empty_stock_count += 1

    try:
        stock = float(re.sub(r"[^0-9\.]", "", stock_str)) if stock_str else 0.0
    except ValueError:
        stock = 0.0

    if stock < MIN_STOCK:
        too_low_stock += 1
        continue

    brand = xml_brand.upper()
    name = clean_title(full_name.upper())
    searchable = f"{brand} {name}"

    if BRAND_RE.search(searchable) or MODEL_RE.search(searchable):
        unique_items.append({
            "sku": sku,
            "brand": brand,
            "name": name,
            "stock": int(stock),
            "price": clean_price(price_str),
            "ean": ean,
        })

print(f"Items with non-empty quantity values: {non_empty_stock_count}")
print(f"Removed because stock < {MIN_STOCK}: {too_low_stock}")
print(f"Designer items matched: {len(unique_items)}")

# Keep the items with the highest stock first
unique_items.sort(key=lambda x: x["stock"], reverse=True)
unique_items = unique_items[:EXACT_TARGET_COUNT]

with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as outfile:
    writer = csv.DictWriter(outfile, fieldnames=["sku", "brand", "name", "stock", "price", "ean"], delimiter=";")
    writer.writeheader()
    writer.writerows(unique_items)

print(f"\n{OUTPUT_FILE} saved with {len(unique_items)} products.")
