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

def parse_immediate_stock(row):
    """Extract immediate local stock levels safely."""
    stock_fields = ['Lagerantall', 'Stock', 'ImmediateStock', 'Lager', 'Beholdning', 'Qty', 'Quantity']
    
    for field in stock_fields:
        val = str(row.get(field, '')).strip()
        if val:
            # Check if there is an explicit incoming indicator
            # Extract first numeric sequence before any delivery text
            first_part = val.split('+')[0].split('(')[0].split('delivery')[0].strip()
            digits = ''.join(c for c in first_part if c.isdigit())
            if digits:
                return int(digits)
                
    stock_status = str(row.get('Lagerstatus', '')).strip().upper()
    if stock_status in ['JA', 'IN STOCK', 'AVAILABLE', 'ON STOCK']:
        return 10
        
    return 0

def extract_description(row, default_name):
    """Extract product description or fallback to name."""
    desc_keys = ['Beskrivelse', 'Description', 'LongDescription', 'Produktbeskrivelse', 'ShortDescription']
    for key in desc_keys:
        val = str(row.get(key, '')).strip()
        if val and val.lower() != 'none':
            return val
    return default_name

def extract_image_url(row, sku):
    """Extract image URL from feed columns or construct standard SKU path."""
    for key, val in row.items():
        if not val:
            continue
        val_str = str(val).strip()
        if val_str.startswith("http://") or val_str.startswith("https://"):
            return val_str
        if any(img_kw in key.lower() for img_kw in ['img', 'bilde', 'image', 'picture', 'photo']) and val_str:
            if not val_str.startswith("http"):
                return f"https://dcs.dk/images/{val_str}"
            return val_str

    if sku:
        return f"https://dcs.dk/images/items/{sku}.jpg"
    return ""

def run_workflow():
    print("🚀 Running DCS SE/DK filter with descriptions & stock validation...")
    res = requests.get(DCS_LIVE_URL)
    res.raise_for_status()
    
    lines = res.text.splitlines()
    delimiter = ';' if ';' in lines[0] else '\t'
    reader = csv.DictReader(lines, delimiter=delimiter)

    products = []
    for row in reader:
        stock_qty = parse_immediate_stock(row)
        
        name = str(row.get('Produktnamn', '')).strip()
        category = str(row.get('Kategori namn', '')).strip()
        sku = str(row.get('Produktnummer', row.get('SKU', ''))).strip()
        condition = str(row.get('Tilstand', row.get('Condition', ''))).strip()
        
        price_raw = row.get('Pris', '0')
        try:
            price_dkk = float(str(price_raw).replace(',', '.'))
        except ValueError:
            continue

        price_sek = price_dkk * DKK_TO_SEK_RATE

        if stock_qty < MIN_STOCK or price_sek >= MAX_PRICE_SEK:
            continue
            
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
