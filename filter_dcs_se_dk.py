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

def extract_ean(row, sku):
    for k in ['EAN', 'Ean', 'ean', 'GTIN', 'Strekkode', 'BarCode', 'EAN13']:
        val = str(row.get(k, '')).strip()
        if val and val.isdigit():
            return val
            
    for k, val in row.items():
        val_str = str(val).strip()
        if val_str.isdigit() and len(val_str) in [8, 12, 13, 14]:
            return val_str
            
    return str(sku).strip()

def extract_rich_description_with_specs(row, name, category):
    """Combine name, category, and all feed specification columns into a detailed description."""
    desc_lines = [f"<h3>{name}</h3>"]
    if category:
        desc_lines.append(f"<p><b>Kategori:</b> {category}</p>")
    
    specs_lines = ["<br><b>Spesifikasjoner:</b><ul>"]
    has_specs = False

    skip_keys = {'Produktnamn', 'Kategori namn', 'Pris', 'Price', 'Produktnummer', 'SKU', 'Lagerstatus [ja eller förväntad leveranstid]', 'image', 'bilde', 'ean'}
    
    for key, val in row.items():
        if not key or not val:
            continue
        if any(skip in key for skip in skip_keys):
            continue
            
        val_str = str(val).strip()
        if val_str and val_str.lower() != 'none':
            specs_lines.append(f"<li><b>{key}:</b> {val_str}</li>")
            has_specs = True
            
    specs_lines.append("</ul>")
    
    if has_specs:
        desc_lines.extend(specs_lines)
        
    return "".join(desc_lines)

def extract_all_images(row, sku):
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
            
    return "|".join(urls)

def run_workflow():
    print("🚀 Running DCS SE/DK filter with full specifications in descriptions...")
    res = requests.get(DCS_LIVE_URL)
    res.raise_for_status()
    
    lines = res.text.splitlines()
    delimiter = ';' if ';' in lines[0] else '\t'
    reader = list(csv.DictReader(lines, delimiter=delimiter))

    products = []
    for row in reader:
        stock_qty = parse_immediate_stock(row)
        
        sku = ""
        for k in ['PRODUCT NUMBER', 'Produktnummer', 'SKU', 'Varenummer', 'ItemNo']:
            if row.get(k):
                sku = str(row.get(k)).strip()
                break

        name = ""
        for k in ['Produktnamn', 'Name', 'Tittel', 'Produktnavn']:
            if row.get(k):
                name = str(row.get(k)).strip()
                break

        category = ""
        for k in ['Kategori namn', 'Category', 'Kategori']:
            if row.get(k):
                category = str(row.get(k)).strip()
                break
        
        price_raw = row.get('Pris', row.get('Price', '0'))
        try:
            price_dkk = float(str(price_raw).replace(',', '.'))
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

        ean = extract_ean(row, sku)
        image_urls = extract_all_images(row, sku)
        description = extract_rich_description_with_specs(row, name, category)

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
        
    print(f"✅ Created dcs_filtered_se_dk.csv with specifications included in descriptions.")

if __name__ == '__main__':
    run_workflow()
