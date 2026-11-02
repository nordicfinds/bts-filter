
import csv
import requests
import re
import html
import os
from io import StringIO
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# DCS SETTINGS
# ==========================================

DCS_LIVE_URL = os.environ["DCS_LIVE_URL"]

MAX_PRICE_SEK = 1300
MIN_STOCK = 5
MAX_PRODUCTS = 200

OUTPUT_FILE = "dcs_filtered_se_dk.csv"

TAX_SAFE_KEYWORDS = [
    'tannbørste', 'toothbrush', 'oral', 'dental',
    'kabel', 'cable', 'barberblad', 'hode'
]

EXCLUDE_USED_KEYWORDS = [
    'brukt', 'brukte', 'used', 'demo', 'demovare',
    'b-grade', 'refurbished', 'åpnet eske',
    'open box', 'returvare', 'anvendt', 'brugt'
]

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 ProductCatalogImporter/2.0"
})


# ==========================================
# CLEANING FUNCTIONS
# ==========================================

def clean_text(value):
    if value is None:
        return ""

    value = html.unescape(str(value))
    value = re.sub(r'<[^>]+>', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def clean_ean(value):
    if not value:
        return ""

    value = str(value).strip()

    if value.lower() in ("none", "nan", "null"):
        return ""

    # Do not silently truncate decimal-looking identifiers.
    if re.fullmatch(r'\d+\.0+', value):
        value = value.split('.')[0]

    digits = re.sub(r'\D', '', value)

    if len(digits) in (8, 12, 13, 14):
        return digits

    return ""


def get_row_value(row, possible_keys):
    for key, value in row.items():
        if not key or value is None:
            continue

        key_clean = key.strip().lower()

        for possible in possible_keys:
            if possible.lower() == key_clean:
                value = str(value).strip()

                if value and value.lower() not in (
                    'none', 'nan', 'null'
                ):
                    return value

    return ""


def is_brand_new(name, condition=""):
    text = f"{name} {condition}".lower()

    return not any(
        keyword in text
        for keyword in EXCLUDE_USED_KEYWORDS
    )


# ==========================================
# STOCK EXTRACTION
# ==========================================

def parse_stock(row):

    stock_keywords = [
        'lager', 'stock', 'antal', 'qty',
        'quantity', 'available'
    ]

    for key, value in row.items():

        if not key or value is None:
            continue

        key_lower = key.lower()
        value = str(value).strip()
        value_lower = value.lower()

        if any(word in value_lower for word in [
            'leveranstid', 'förväntad', 'incoming',
            'delivery', 'forventet', 'bestilt'
        ]):
            if any(word in key_lower for word in stock_keywords):
                return 0

        if any(word in key_lower for word in stock_keywords):

            match = re.search(r'\d+', value)

            if match:
                return int(match.group())

            if value.upper() in [
                'JA', 'IN STOCK', 'AVAILABLE'
            ]:
                return 10

    return 0


# ==========================================
# PRICE EXTRACTION
# ==========================================

def parse_price(value):

    if not value:
        return None

    value = str(value).strip()
    value = value.replace(' ', '')
    value = value.replace('SEK', '').replace('DKK', '')
    value = value.replace('kr', '').replace('Kr', '')

    # Handle common European decimal format.
    if ',' in value:
        value = value.replace('.', '')
        value = value.replace(',', '.')

    try:
        return float(value)
    except ValueError:
        return None


# ==========================================
# EAN EXTRACTION
# ==========================================

def extract_ean(row):

    keywords = [
        'ean', 'gtin', 'barcode',
        'stregkode', 'strekkode', 'streckkod'
    ]

    for key, value in row.items():

        if key and any(
            word in key.lower() for word in keywords
        ):
            ean = clean_ean(value)

            if ean:
                return ean

    return ""


# ==========================================
# IMAGE EXTRACTION
# ==========================================

def extract_image(row, sku):

    image_keywords = [
        'image', 'bild', 'foto', 'picture',
        'media', 'photo', 'img'
    ]

    # First look for an actual image URL in the feed.
    for key, value in row.items():

        if not key or not value:
            continue

        if any(
            word in key.lower()
            for word in image_keywords
        ):

            value = str(value).strip()

            match = re.search(
                r'https?://[^\s,"\']+',
                value,
                re.IGNORECASE
            )

            if match:
                return match.group(0)

    # Fallback: test the old assumed image path.
    if sku:
        candidate = (
            f"https://dcs.dk/images/items/{sku}.jpg"
        )

        try:
            response = session.head(
                candidate,
                timeout=8,
                allow_redirects=True
            )

            if response.status_code == 200:
                content_type = response.headers.get(
                    "Content-Type", ""
                )

                if content_type.lower().startswith("image/"):
                    return candidate

        except requests.RequestException:
            pass

    return ""


# ==========================================
# IMAGE VALIDATION
# ==========================================

def verify_image(url):

    if not url:
        return False

    try:
        response = session.get(
            url,
            headers={"Range": "bytes=0-1023"},
            timeout=12,
            stream=True
        )

        content_type = response.headers.get(
            "Content-Type", ""
        )

        valid = (
            response.status_code in (200, 206)
            and content_type.lower().startswith("image/")
        )

        response.close()
        return valid

    except requests.RequestException:
        return False


# ==========================================
# MAIN WORKFLOW
# ==========================================

def run_workflow():

    print("\nSTARTING DCS PRODUCT FILTER")
    print("=" * 45)

    response = session.get(
        DCS_LIVE_URL,
        timeout=90
    )

    response.raise_for_status()

    content = response.content.decode(
        "utf-8-sig",
        errors="replace"
    )

    sample = content[:10000]

    try:
        delimiter = csv.Sniffer().sniff(
            sample,
            delimiters=";,\t|"
        ).delimiter
    except csv.Error:
        delimiter = ";"

    reader = csv.DictReader(
        StringIO(content),
        delimiter=delimiter
    )

    print("Detected delimiter:", repr(delimiter))
    print("Columns:", reader.fieldnames)

    products = []

    stats = {
        "total": 0,
        "missing_ean": 0,
        "missing_image": 0,
        "filtered": 0
    }

    for row in reader:

        stats["total"] += 1

        sku = get_row_value(row, [
            'Produktnummer',
            'PRODUCT NUMBER',
            'SKU',
            'Varenummer',
            'ItemNo'
        ])

        if not sku:
            continue

        name = get_row_value(row, [
            'Produktnamn',
            'Name',
            'Tittel',
            'Produktnavn'
        ])

        category = get_row_value(row, [
            'Kategori namn',
            'Category',
            'Kategori'
        ])

        price_raw = get_row_value(row, [
            'Pris', 'Price'
        ])

        price = parse_price(price_raw)

        stock = parse_stock(row)

        if price is None or price <= 0:
            continue

        if price >= MAX_PRICE_SEK or stock < MIN_STOCK:
            continue

        condition = get_row_value(row, [
            'Tilstand', 'Condition'
        ])

        if not is_brand_new(name, condition):
            continue

        text_check = f"{category} {name}".lower()

        if not any(
            keyword in text_check
            for keyword in TAX_SAFE_KEYWORDS
        ):
            continue

        ean = extract_ean(row)

        image_url = extract_image(row, sku)

        if not ean:
            stats["missing_ean"] += 1

        if not image_url:
            stats["missing_image"] += 1

        description_raw = get_row_value(row, [
            'Beskrivelse',
            'Description',
            'Tekst',
            'Specifikationer',
            'Info'
        ])

        description = (
            f"Produkt: {name}. Kategori: {category}. "
            f"{clean_text(description_raw)}"
        ).strip()

        products.append({
            "sku": sku,
            "ean": ean,
            "name": name,
            "category": category,
            "price_sek": round(price, 2),
            "stock": stock,
            "description": description,
            "image_url": image_url
        })

        if len(products) >= MAX_PRODUCTS:
            break

    # Verify actual image URLs.
    print("\nChecking product images...")

    with ThreadPoolExecutor(max_workers=8) as executor:

        results = list(
            executor.map(
                verify_image,
                [p["image_url"] for p in products]
            )
        )

    for product, valid in zip(products, results):

        if not valid:
            product["image_url"] = ""

    # Export CSV.
    output_fields = [
        "sku",
        "ean",
        "name",
        "category",
        "price_sek",
        "stock",
        "description",
        "image_url"
    ]

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=output_fields,
            delimiter=";"
        )

        writer.writeheader()
        writer.writerows(products)

    print("\n" + "=" * 45)
    print("WORKFLOW FINISHED")
    print("=" * 45)

    print("Products scanned:", stats["total"])
    print("Products exported:", len(products))
    print("Missing EAN:", stats["missing_ean"])

    print(
        "Missing or invalid images:",
        sum(not p["image_url"] for p in products)
    )

    print("CSV created:", OUTPUT_FILE)


if __name__ == "__main__":
    run_workflow()
