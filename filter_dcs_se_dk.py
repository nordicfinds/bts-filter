import csv
import requests

DCS_LIVE_URL = "https://dcs.dk/pricelist?kundenummer=Shymon%20Uzzman&type=145501807be2cac040288d2b3285684ae47940"
DKK_TO_SEK_RATE = 1.55
MAX_PRICE_SEK = 1300
MIN_STOCK = 5

TAX_SAFE_KEYWORDS = ['tannbørste', 'toothbrush', 'oral', 'dental', 'kabel', 'cable', 'barberblad', 'hode']
EXCLUDE_USED_KEYWORDS = [
    'brukt', 'brukte', 'used', 'demo', 'demovare', 'b-grade', 
    'refurbished', 'åpnet eske', 'open box', 'returvare', 'anvendt', 'brugt'
]

def is_brand_new_sealed(name, condition_field=""):
    text = f"{name} {condition_field}".lower()
    return not any(kw in text for kw in EXCLUDE_USED_KEYWORDS)

def parse_stock_qty(row):
    """Safely parse stock quantity without discarding items unexpectedly."""
    # Search every key in the row for stock/lager indicators
    for key, val in row.items():
        if not key or not val:
            continue
        key_lower = key.lower()
        if any(k in key_lower for k in ['lagerantall', 'stock', 'beholdning', 'antall', 'qty']):
            val_str = str(val).split('+')[0].split('(')[0].strip()
            digits = ''.join(c for c in val_str if c.isdigit())
            if digits:
                return int(digits)
    
    # Check general status field
    for key, val in row.items():
        if key and 'status' in key.lower():
            val_upper = str(val).strip().upper()
            if val_upper in ['JA', 'IN STOCK', 'AVAILABLE', 'ON STOCK']:
                return 10

    # Default safe fallthrough for items in feed
    return 5

def extract_description(row, default_name):
    for key, val in row.items():
        if key and any(k in key.lower() for k in ['beskrivelse', 'description', 'tekst', 'info']):
            val_str = str(val).strip()
            if val_str and val_str.lower() != 'none':
                return val_str
    return default_name

def extract_image_url(row, sku):
    for key, val in row.items():
        if not val:
            continue
        val_str = str(val).strip()
        if val_str.startswith("http://") or val_str.startswith("https://"):
            return val_str
        if key and any(img_kw in key.lower() for img_kw in ['img', 'bilde', 'image', 'picture', 'photo']) and val_str:
            if not val_str.startswith("http"):
                return f"https://dcs.dk/images/{val_str}"
            return val_str

    if sku:
        return f"https://dcs.dk/images/items/{sku}.jpg"
    return ""

def run_workflow():
    print("🚀 Fetching live DCS feed and checking headers...")
    res = requests.get(DCS_LIVE_URL)
    res.raise_for_status()
    
    lines = res.text.splitlines()
    delimiter = ';' if ';' in lines[0] else '\t'
    reader = list(csv.DictReader(lines, delimiter=delimiter))

    if reader:
        print(f"📋 Feed headers found: {list(reader[0].keys())}")

    products = []
    for row in reader:
        stock_qty = parse_stock_qty(row)
        
        # Name lookup
        name = ""
        for k in ['Produktnamn', 'Name', 'Tittel', 'Beskrivelse', 'Produktnavn']:
            if row.get(k):
                name = str(row.get(k)).strip()
                break

        # Category lookup
        category = ""
        for k in ['Kategori namn', 'Category', 'Kategori']:
            if row.get(k):
                category = str(row.get(k)).strip()
                break

        # SKU lookup
        sku = ""
        for k in ['Produktnummer', 'SKU', 'Varenummer', 'ItemNo']:
            if row.get(k):
                sku = str(row.get(k)).strip()
                break

        # Price lookup
        price_dkk = 0.0
        for k in ['Pris', 'Price', 'Salgspris']:
            if row.get(k):
                try:
                    price_dkk = float(str(row.get(k)).replace(',', '.'))
                    break
                except ValueError:
                    continue

        price_sek = price_dkk * DKK_TO_SEK_RATE

        if stock_qty < MIN_STOCK or price_sek >= MAX_PRICE_SEK or price_sek == 0:
            continue
            
        condition = str(row.get('Tilstand', row.get('Condition', ''))).strip()
        if not is_brand_new_sealed(name, condition):
            continue

        text_check = f"{category} {name}".lower()
        if not any(kw in text_check for kw in TAX_SAFE_KEYWORDS):
            continue

        image_url = extract_image_url(row, sku)
        description = extract_description(row, name)

        products.append({
            "sku": sku,
            "name": name,
            "category": category,
            "price_sek": round(price_sek, 2),
            "stock": stock_qty,
            "description": description,
            "image_url": image_url
        })

        if len(products) >= 200:
            break

    output_fields = ["sku", "name", "category", "price_sek", "stock", "description", "image_url"]
    with open('dcs_filtered_se_dk.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, delimiter=';')
        writer.writeheader()
        writer.writerows(products)
        
    print(f"✅ Created dcs_filtered_se_dk.csv with {len(products)} products.")

if __name__ == '__main__':
    run_workflow()
