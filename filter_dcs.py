import csv
import json
import requests

# Live DCS Pricelist Direct Download Link
DCS_LIVE_URL = "https://dcs.dk/pricelist?kundenummer=Shymon%20Uzzman&type=145501807be2cac040288d2b3285684ae47940"

DKK_TO_SEK_RATE = 1.55  # Currency conversion multiplier
MAX_PRICE_SEK = 1300    # Purchasing price cap in SEK

# Target Category Keywords
PERSONAL_CARE = ['tannbørste', 'toothbrush', 'barbermaskin', 'shaver', 'trimmer', 'epilator', 'oral', 'dental']
CONSUMER_TECH = ['lader', 'charger', 'kabel', 'cable', 'headset', 'earbuds', 'ørepropper', 'strømbank', 'powerbank', 'adapter']
GAMING_ACC = ['gamepad', 'controller', 'kontroller', 'headset', 'ratt', 'dock', 'joystick']

EXCLUDE_USED = ['brukt', 'brukte', 'used', 'demo', 'demovare', 'b-grade', 'refurbished', 'åpnet eske']
EXCLUDE_CONSOLES = ['playstation 5', 'ps5 console', 'xbox series x', 'xbox series s', 'nintendo switch console']

def is_brand_new(name):
    return not any(kw in name.lower() for kw in EXCLUDE_USED)

def is_console(name):
    return any(kw in name.lower() for kw in EXCLUDE_CONSOLES)

def is_target_category(category, name):
    text = f"{category} {name}".lower()
    return any(kw in text for kw in PERSONAL_CARE + CONSUMER_TECH + GAMING_ACC)

def fetch_and_filter_dcs():
    print(" Downloading live CSV pricelist from DCS...")
    res = requests.get(DCS_LIVE_URL)
    res.raise_for_status()
    
    lines = res.text.splitlines()
    delimiter = ';' if ';' in lines[0] else '\t'
    reader = csv.DictReader(lines, delimiter=delimiter)

    batch1_se_dk = []
    batch2_dk_only = []

    for row in reader:
        stock = str(row.get('Lagerstatus', '')).strip().upper()
        name = str(row.get('Produktnamn', '')).strip()
        category = str(row.get('Kategori namn', '')).strip()
        sku = str(row.get('Produktnummer', '')).strip()
        model = str(row.get('Modellnamn', '')).strip()
        image_url = str(row.get('Bilde', '') or row.get('Image', '') or row.get('Billedurl', '')).strip()
        
        try:
            price_dkk = float(str(row.get('Pris', '0')).replace(',', '.'))
        except ValueError:
            continue

        price_sek = price_dkk * DKK_TO_SEK_RATE

        # Filtering Rules
        if stock != 'JA' or price_sek >= MAX_PRICE_SEK:
            continue
        if not is_brand_new(name) or is_console(name):
            continue
        if not is_target_category(category, name):
            continue

        item = {
            "sku": sku,
            "model": model,
            "name": name,
            "category": category,
            "price_sek": round(price_sek, 2),
            "image_url": image_url,
            "stock": 10
        }

        # Check for chemical tax-safe items (Dental care & simple cables/chargers)
        is_tax_safe = any(kw in f"{category} {name}".lower() for kw in PERSONAL_CARE + ['kabel', 'cable'])

        if is_tax_safe and len(batch1_se_dk) < 250:
            batch1_se_dk.append(item)
        elif len(batch2_dk_only) < 100:
            batch2_dk_only.append(item)

        if len(batch1_se_dk) >= 250 and len(batch2_dk_only) >= 100:
            break

    with open('dcs_filtered_se_dk.json', 'w', encoding='utf-8') as f:
        json.dump(batch1_se_dk, f, indent=4, ensure_ascii=False)
        
    with open('dcs_filtered_dk_only.json', 'w', encoding='utf-8') as f:
        json.dump(batch2_dk_only, f, indent=4, ensure_ascii=False)

    print(f" Filtered {len(batch1_se_dk)} items for SE/DK and {len(batch2_dk_only)} items for DK-only.")

if __name__ == '__main__':
    fetch_and_filter_dcs()
