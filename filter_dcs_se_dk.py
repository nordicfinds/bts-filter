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

def extract_image_url(row, sku):
    """Dynamically search all row keys for any URL, or construct standard DCS image link."""
    # 1. Search every column in the feed for anything starting with http/https or containing image keywords
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

    # 2. Fallback: Construct standard DCS SKU image URL if no direct column exists
    if sku:
        return f"https://dcs.dk/images/items/{sku}.jpg"
    return ""

def run_workflow():
    print("🚀 Fetching live DCS feed with dynamic image extraction & SKU fallback...")
    res = requests.get(DCS_LIVE_URL)
    res.raise_for_status()
    
    lines = res.text.splitlines()
    delimiter = ';' if ';' in lines[0] else '\t'
    reader = csv.DictReader(lines, delimiter=delimiter)

    products = []
    for row in reader:
        stock_status = str(row.get('Lagerstatus', '')).strip().upper()
        
        try:
            stock_qty = int(str(row.get('Lagerantall', row.get('Stock', '5'))).strip())
        except ValueError:
            stock_qty = 5 if stock_status == 'JA' else 0

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

        products.append({
            "sku": sku,
            "name": name,
            "category": category,
            "price_sek": round(price_sek, 2),
            "stock": stock_qty,
            "image_url": image_url
        })

        if len(products) >= 200:
            break

    with open('dcs_filtered_se_dk.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(
            f, 
            fieldnames=["sku", "name", "category", "price_sek", "stock", "image_url"], 
            delimiter=';'
        )
        writer.writeheader()
        writer.writerows(products)
        
    print(f"✅ Generated dcs_filtered_se_dk.csv with {len(products)} products and image URLs.")

if __name__ == '__main__':
    run_workflow()
