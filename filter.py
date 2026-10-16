import csv
import time
import urllib.request
import urllib.error

FEED_URL = "https://www.btswholesaler.com/generatefeedbts?user_id=1429150&pass=Avedore556%2C&format=csv&language_code=en-GB"

FULL_BRANDS = [
    "AFNAN", "AL HARAMAIN", "ARABIYAT", "ARMAF", "FRAGRANCE WORLD", 
    "FRENCH AVENUE", "LATTAFA", "MAISON ALHAMBRA", "RASASI", "SWISS ARABIAN",
    "AMIKA", "GLAM OF SWEDEN", "J.CAT BEAUTY", "LILY LOLO", "MISSHA", "MIZON", "PARIS CORNER"
]

BEST_SELLER_KEYWORDS = {
    "CAROLINA HERRERA": ["GOOD GIRL", "BAD BOY", "212"],
    "CHANEL": ["NO 5", "NO.5", "COCO", "BLEU", "CHANCE", "ALLURE"],
    "GUCCI": ["BLOOM", "FLORA", "GUILTY", "BAMBOO", "RUSH"],
    "PACO RABANNE": ["1 MILLION", "ONE MILLION", "INVICTUS", "LADY MILLION", "PHANTOM", "OLYMPEA", "FAME"],
    "VERSACE": ["BRIGHT CRYSTAL", "EROS", "DYLAN", "CRYSTAL NOIR", "EAU FRAICHE"],
    "MONTBLANC": ["LEGEND", "EXPLORER", "INDIVIDUEL"],
    "TOMMY HILFIGER": ["TOMMY GIRL", "TOMMY"],
    "ESCADA": ["TAJ SUNSET", "ISLAND KISS", "MAGNETISM", "SUMMER"],
    "ELIZABETH ARDEN": ["GREEN TEA", "RED DOOR", "5TH AVENUE", "FIFTH AVENUE", "WHITE TEA"],
    "GISADA": ["AMBASSADOR", "IMPERIAL"],
    "JULIETTE HAS A GUN": ["NOT A PERFUME", "PEAR INC", "SUPERDOSE"],
    "SOL DE JANEIRO": ["CHEIROSA", "BUM BUM", "62", "68", "71", "40"],
    "DERMALOGICA": ["MICROFOLIANT", "SPECIAL CLEANSING", "PRECLEANSE"],
    "THE ORDINARY": ["NIACINAMIDE", "HYALURONIC", "AHA", "CAFFEINE", "RETINOL", "PEPTIDE"],
    "K18": ["MOLECULAR", "REPAIR", "MASK"],
    "DR. JART+": ["CICAPAIR", "CERAMIDIN"],
    "BENEFIT": ["THEY'RE REAL", "ROLLER LASH", "HOOLA", "BENETINT", "GIMME BROW", "BADGAL"],
    "ABERCROMBIE & FITCH": ["FIRST INSTINCT", "FIERCE"],
    "BRITNEY SPEARS": ["FANTASY", "CURIOUS"],
    "CLEAN": ["RESERVE", "WARM COTTON", "RAIN", "SKIN"],
    "ESTÉE LAUDER": ["ADVANCED NIGHT", "DOUBLE WEAR"],
    "ESTEE LAUDER": ["ADVANCED NIGHT", "DOUBLE WEAR"],
    "JEAN-LOUIS SCHERRER": ["SCHERRER"],
    "ESSENCE COSMETICS": ["LASH PRINCIPA", "MASCARA"],
    "ESSIE": ["NAIL", "POLISH", "TOP COAT"],
    "ARDELL": ["WHISPIES", "LASH"],
    "SALLY HANSEN": ["MIRACLE GEL", "HARD AS NAILS"],
    "SENSAI": ["CELLULAR", "BRONZING"]
}

def download_feed_with_retries(url, retries=3, delay=10):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    req = urllib.request.Request(url, headers=headers)
    
    for attempt in range(retries):
        try:
            print(f"Downloading master BTS feed (Attempt {attempt + 1}/{retries})...")
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            print(f"Download failed with error: {e}")
            if attempt < retries - 1:
                print(f"Waiting {delay} seconds before retrying...")
                time.sleep(delay)
            else:
                raise

content = download_feed_with_retries(FEED_URL)
lines = content.splitlines()
print(f"Downloaded total lines: {len(lines)}")

delim = ';' if ';' in lines[0] else ','
reader = csv.DictReader(lines, delimiter=delim)
clean_rows = []

for row in reader:
    row_text = " ".join([str(val) for val in row.values()]).upper()
    
    is_match = False
    if any(brand in row_text for brand in FULL_BRANDS):
        is_match = True
    else:
        for brand, keywords in BEST_SELLER_KEYWORDS.items():
            if brand in row_text:
                if any(kw in row_text for kw in keywords):
                    is_match = True
                    break

    if is_match:
        clean_rows.append(row)
        if len(clean_rows) >= 950:
            break

print(f"SUCCESS! Matched products: {len(clean_rows)}")

if clean_rows:
    with open("bts_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames, delimiter=delim)
        writer.writeheader()
        writer.writerows(clean_rows)
    print("Saved bts_filtered.csv successfully!")
