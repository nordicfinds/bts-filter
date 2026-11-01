import csv
import json
import requests

DCS_LIVE_URL = "https://dcs.dk/pricelist?kundenummer=Shymon%20Uzzman&type=145501807be2cac040288d2b3285684ae47940"
DKK_TO_SEK_RATE = 1.55
MAX_PRICE_SEK = 1300
MIN_STOCK = 5

TAX_SAFE_KEYWORDS = ['tannbørste', 'toothbrush', 'oral', 'dental', 'kabel', 'cable', 'barberblad', 'hode']
EXCLUDE_USED_KEYWORDS = ['brukt', 'brukte', 'used', 'demo', 'demovare', 'b-grade', 'refurbished', 'åpnet eske', 'open box', 'returvare', 'anvendt', 'brugt']

def is_brand_new_sealed(name, condition_field=""):
    text = f"{name} {condition_field}".lower()
    return not any(kw in text for kw in EXCLUDE_USED_KEYWORDS)

def run_se_dk_filter():
    print("Downloading live CSV for Sweden & Denmark tax-safe batch...")
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
        sku = str(row.get('Produktnummer', '')).strip()
        condition = str(row.get('Tilstand', row.get('Condition', ''))).strip()
        image_url = str(row.get('Bilde', '') or row.get('Image', '') or row.get('Billedurl', '')).strip()
        
        try:
            price_dkk = float(str(row.get('Pris', '0')).replace(',', '.'))
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

        images_dict = {}
        if image_url:
            images_dict["0"] = f"url:{image_url}"

        products.append({
            "sku": sku,
            "name": name,
            "category": category,
            "price_sek": round(price_sek, 2),
            "stock": stock_qty,
            "images": images_dict
        })

        if len(products) >= 200:
            break

    with open('dcs_filtered_se_dk.json', 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=4, ensure_ascii=False)
        
    print(f"✅ Filtered {len(products)} brand-new, sealed, tax-safe items for SE & DK.")

if __name__ == '__main__':
    run_se_dk_filter()
