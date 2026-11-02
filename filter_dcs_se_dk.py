import csv
import requests
import re
import html

DCS_LIVE_URL = "https://dcs.dk/pricelist?kundenummer=Shymon%20Uzzman&type=145501807be2cac040288d2b3285684ae47940"

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
    for k, v in row.items():
        val_str = str(v).strip()
        if not val_str:
            continue
        val_lower = val_str.lower()
        if any(kw in val_lower for kw in ['leveranstid', 'förväntad', 'incoming', 'delivery', 'forventet', 'bestilt']):
            return 0
        if k and any(s_kw in k.lower() for s_kw in ['lager', 'stock', 'antal', 'qty', 'quantity', 'status']):
            digits = ''.join(c for c in val_str.split('+')[0].split('(')[0] if c.isdigit())
            if digits:
                return int(digits)
            if val_str.upper() in ['JA', 'IN STOCK', 'AVAILABLE', 'ON STOCK']:
                return 10

    for v in row.values():
        val_str = str(v).strip()
        if val_str.isdigit() and len(val_str) <= 3:
            num = int(val_str)
            if num > 0:
                return num
                
    return 0

def clean_ean(val):
    if not val or str(val).lower() == 'none':
        return ""
    val_str = str(val).strip()
    if '.' in val_str:
        val_str = val_str.split('.')[0]
    digits = ''.join(c for c in val_str if c.isdigit())
    if len(digits) >= 8:
        return digits
    return ""

def clean_html_description(raw_text):
    if not raw_text or str(raw_text).lower() == 'none':
        return ""
    cleanr = re.compile('<.*?>')
    cleansed = re.sub(cleanr, ' ', str(raw_text))
    decoded = html.unescape(cleansed)
    return re.sub(r'\s+', ' ', decoded).strip()

def get_row_value(row, possible_keys):
    for key, val in row.items():
        if not key or not val:
            continue
        clean_key = key.strip().lower()
        for pk in possible_keys:
            if pk.lower() == clean_key or pk.lower() in clean_key:
                val_str = str(val).strip()
                if val_str and val_str.lower() != 'none':
                    return val_str
    return ""

def run_workflow():
    print("🚀 Running DCS SE/DK filter...")
    res = requests.get(DCS_LIVE_URL)
    res.raise_for_status()
    
    lines = res.text.splitlines()
    delimiter = ';' if ';' in lines[0] else '\t'
    reader = list(csv.DictReader(lines, delimiter=delimiter))

    products = []
    for row in reader:
        stock_qty = parse_immediate_stock(row)
        
        sku = get_row_value(row, ['Produktnummer', 'PRODUCT NUMBER', 'SKU', 'Varenummer', 'ItemNo'])
        if not sku:
            continue

        # Extract EAN checking explicit barcode headers first
        ean = ""
        for k, val in row.items():
            if k and any(ek in k.lower() for ek in ['ean', 'gtin', 'barcode', 'stregkode', 'strekkode', 'streckkod']):
                ean = clean_ean(val)
                if ean:
                    break
        
        if not ean:
            for val in row.values():
                val_clean = clean_ean(val)
                if len(val_clean) in [8, 12, 13, 14]:
                    ean = val_clean
                    break

        name = get_row_value(row, ['Produktnamn', 'Name', 'Tittel', 'Produktnavn'])
        category = get_row_value(row, ['Kategori namn', 'Category', 'Kategori'])
        
        price_raw = get_row_value(row, ['Pris', 'Price', 'pris'])
        try:
            price_sek = float(price_raw.replace(',', '.'))
        except ValueError:
            continue

        if stock_qty < MIN_STOCK or price_sek >= MAX_PRICE_SEK or price_sek == 0:
            continue
            
        condition = get_row_value(row, ['Tilstand', 'Condition'])
        if not is_brand_new_sealed(name, condition):
            continue

        text_check = f"{category} {name}".lower()
        if not any(kw in text_check for kw in TAX_SAFE_KEYWORDS):
            continue

        raw_desc = get_row_value(row, ['Beskrivelse', 'Description', 'Tekst', 'Specifikationer', 'Info'])
        clean_desc = clean_html_description(raw_desc)
        
        description = f"Produkt: {name}. Kategori: {category}."
        if clean_desc and clean_desc.lower() != name.lower():
            description += f" {clean_desc}"

        # Reliable image URL generation using the SKU image path
        image_url = f"https://dcs.dk/images/items/{sku}.jpg"

        products.append({
            "sku": sku,
            "ean": ean,
            "name": name,
            "category": category,
            "price_sek": round(price_sek, 2),
            "stock": stock_qty,
            "description": description,
            "image_url": image_url
        })

        if len(products) >= 200:
            break

    output_fields = ["sku", "ean", "name", "category", "price_sek", "stock", "description", "image_url"]
    with open('dcs_filtered_se_dk.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, delimiter=';')
        writer.writeheader()
        writer.writerows(products)
        
    print(f"✅ Created dcs_filtered_se_dk.csv with {len(products)} products.")

if __name__ == '__main__':
    run_workflow()
