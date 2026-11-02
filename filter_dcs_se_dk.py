import csv
import requests

# Your working DCS feed URL
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
    raw_status = str(row.get('Lagerstatus [ja eller förväntad leveranstid]', '')).strip()
    status_lower = raw_status.lower()
    
    if any(future_kw in status_lower for future_kw in ['leveranstid', 'förväntad', 'incoming', 'delivery', 'forventet', 'bestilt']):
        return 0

    digits = ''.join(c for c in raw_status.split('+')[0].split('(')[0] if c.isdigit())
    if digits:
        return int(digits)
        
    if raw_status.upper() in ['JA', 'IN STOCK', 'AVAILABLE', 'ON STOCK']:
        return 10
        
    return 0

def run_workflow():
    print("🚀 Connecting to DCS live feed...")
    res = requests.get(DCS_LIVE_URL)
    res.raise_for_status()
    
    lines = res.text.splitlines()
    delimiter = ';' if ';' in lines[0] else '\t'
    reader = list(csv.DictReader(lines, delimiter=delimiter))
    
    print(f"📊 Total items in feed: {len(reader)}")

    products = []
    for row in reader:
        stock_qty = parse_immediate_stock(row)
        
        # 1. Clean SKU / Product Number
        sku = ""
        for k in ['PRODUCT NUMBER', 'Produktnummer', 'SKU', 'Varenummer', 'ItemNo']:
            val = str(row.get(k, '')).strip()
            if val:
                sku = val
                break

        # 2. Clean EAN (Look specifically for barcode fields, fallback to SKU if none)
        ean = ""
        for k in ['EAN', 'Ean', 'ean', 'GTIN', 'Strekkode', 'BarCode', 'EAN13']:
            val = str(row.get(k, '')).strip()
            if val.isdigit() and len(val) in [8, 12, 13, 14]:
                ean = val
                break
        if not ean:
            ean = sku

        # 3. Product Name
        name = ""
        for k in ['Produktnamn', 'Name', 'Tittel', 'Produktnavn']:
            val = str(row.get(k, '')).strip()
            if val:
                name = val
                break

        # 4. Category
        category = ""
        for k in ['Kategori namn', 'Category', 'Kategori']:
            val = str(row.get(k, '')).strip()
            if val:
                category = val
                break
        
        # 5. Price
        price_raw = '0'
        for k in ['Pris', 'Price', 'pris']:
            if row.get(k):
                price_raw = str(row.get(k))
                break

        try:
            price_dkk = float(price_raw.replace(',', '.'))
        except ValueError:
            continue

        price_sek = price_dkk * DKK_TO_SEK_RATE

        # Apply Filters
        if stock_qty < MIN_STOCK or price_sek >= MAX_PRICE_SEK or price_sek == 0:
            continue
            
        condition = str(row.get('Tilstand', row.get('Condition', ''))).strip()
        if not is_brand_new_sealed(name, condition):
            continue

        text_check = f"{category} {name}".lower()
        if not any(kw in text_check for kw in TAX_SAFE_KEYWORDS):
            continue

        # Clean Description (Avoid messy raw key dumps, keep it professional)
        description = f"<h3>{name}</h3><p><b>Kategori:</b> {category}</p><p>Helt ny og uåpnet produkt med rask levering fra lager i Skandinavia.</p>"

        # Image collection
        urls = []
        for key, val in row.items():
            if not val or not key:
                continue
            val_str = str(val).strip()
            key_lower = key.lower()
            if any(img_kw in key_lower for img_kw in ['img', 'bilde', 'image', 'picture', 'photo', 'billede']):
                if val_str.startswith("http://") or val_str.startswith("https://"):
                    if val_str not in urls:
                        urls.append(val_str)
                elif val_str and val_str.lower() != 'none':
                    full_url = f"https://dcs.dk/images/{val_str}"
                    if full_url not in urls:
                        urls.append(full_url)

        if sku:
            sku_url = f"https://dcs.dk/images/items/{sku}.jpg"
            if sku_url not in urls:
                urls.append(sku_url)
        image_urls = "|".join(urls)

        products.append({
            "sku": sku,
            "ean": ean,
            "name": name,
            "category": category,
            "price_sek": round(price_sek, 2),
            "stock": stock_qty,
            "description": description,
            "image_url": image_urls
        })

        if len(products) >= 200:
            break

    output_fields = ["sku", "ean", "name", "category", "price_sek", "stock", "description", "image_url"]
    with open('dcs_filtered_se_dk.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, delimiter=';')
        writer.writeheader()
        writer.writerows(products)
        
    print(f"✅ Successfully created dcs_filtered_se_dk.csv with {len(products)} products.")

if __name__ == '__main__':
    run_workflow()
