import csv
import urllib.request
import urllib.error
import time

FEED_URL = "https://www.btswholesaler.com/generatefeedbts?user_id=1429150&pass=Avedore556%2C&format=csv&language_code=en-GB"

# 1. Full-Catalog Brands (Always match all items up to cap)
FULL_BRANDS = [
    "AFNAN", "AMIKA", "ARABIYAT", "ARMAF", "FRAGRANCE WORLD", 
    "FRENCH AVENUE", "LATTAFA", "MAISON ALHAMBRA", "PARIS CORNER", "RASASI"
]

# 2. Targeted Brands (Max ~10 top-selling lines/keywords per brand)
BRAND_KEYWORDS = {
    "ABERCROMBIE": ["FIERCE", "FIRST INSTINCT", "AUTHENTIC", "AWAY", "NATURALLY FIERCE"],
    "ARDELL": ["WHISPIES", "DEMI", "MAGNETIC", "DUO", "INDIVIDUAL", "LASH"],
    "BENEFIT": ["BENETINT", "POREFESSIONAL", "BADGAL", "ROLLER LASH", "HOOLA", "GIMME BROW", "PRECISELY MY BROW", "THEY'RE REAL", "FLUFF UP"],
    "BRITNEY SPEARS": ["FANTASY", "CURIOUS", "MIDNIGHT FANTASY", "PREROGATIVE", "IN CONTROL"],
    "CAROLINA HERRERA": ["GOOD GIRL", "BAD BOY", "212", "VERY GOOD GIRL", "CH", "HERRERA CONFIDENTIAL"],
    "CHANEL": ["NO 5", "NO.5", "COCO", "BLEU", "CHANCE", "ALLURE", "GABRIELLE", "EGOISTE", "MADEMOISELLE"],
    "CLEAN": ["RESERVE", "WARM COTTON", "RAIN", "SKIN", "PURE SOAP", "APPLE BLOSSOM", "FRESH LAUNDRY"],
    "DERMALOGICA": ["MICROFOLIANT", "SPECIAL CLEANSING", "PRECLEANSE", "DYNAMIC SKIN", "SMOOTHING CREAM", "BIOLUMIN-C", "CLEAR START"],
    "DR. JART": ["CICAPAIR", "CERAMIDIN", "CRYO RUBBER", "EVERY SUN DAY"],
    "ELIZABETH ARDEN": ["GREEN TEA", "RED DOOR", "5TH AVENUE", "FIFTH AVENUE", "WHITE TEA", "EIGHT HOUR", "RETINOL CERAMIDE"],
    "ESCADA": ["TAJ SUNSET", "ISLAND KISS", "MAGNETISM", "SUMMER FESTIVAL", "SORBETTO ROSSO", "MIAMI BLOSSOM", "CELEBRATE N.O.W."],
    "ESSENCE": ["LASH PRINCESS", "I LOVE EXTREME", "MAKE ME BROW", "JUICY BOMB", "SOFT & PRECISE", "FIT ME"],
    "ESSIE": ["GEL COUTURE", "EXPRESSIE", "GOOD AS GO", "MADEMOISELLE", "BALLET SLIPPERS", "APRICOT CUTICLE"],
    "ESTEE LAUDER": ["ADVANCED NIGHT", "DOUBLE WEAR", "YOUTH-DEW", "BEAUTIFUL", "PLEASURES", "BRONZE GODDESS", "REVITALIZING SUPREME"],
    "GISADA": ["AMBASSADOR", "AMBASSADORA", "TITANIUM", "DONNA", "EXECUTIVE"],
    "GLAM OF SWEDEN": ["LIP GLOSS", "MASCARA", "NAIL", "EYELINER", "CONCEALER", "FOUNDATION", "MASK"],
    "GUCCI": ["BLOOM", "FLORA", "GUILTY", "BAMBOO", "RUSH", "MEMOIRE", "ALCHEMIST"],
    "J.CAT": ["BEAUTY", "BLUSH", "LIPSTICK", "HIGHLIGHTER", "PALETTE"],
    "JEAN-LOUIS SCHERRER": ["SCHERRER", "ONE LOVE", "POP DELIGHTS"],
    "JULIETTE HAS A GUN": ["NOT A PERFUME", "PEAR INC", "SUPERDOSE", "LUST FOR SUN", "VANILLA VIBES", "MAGNOLIA BLISS"],
    "K18": ["MOLECULAR", "REPAIR", "MASK", "PEPTIDE", "SHAMPOO"],
    "LILY LOLO": ["MINERAL", "FOUNDATION", "BB CREAM", "SETTING POWDER"],
    "MISSHA": ["PERFECT COVER", "TIME REVOLUTION", "M MAGIC", "SUPER AQUA"],
    "MIZON": ["SNAIL REPAIR", "COLLAGEN", "HYALURONIC", "ALL IN ONE"],
    "MONTBLANC": ["LEGEND", "EXPLORER", "INDIVIDUEL", "EMBLEM", "STARWALKER", "PRESENCE"],
    "PACO RABANNE": ["1 MILLION", "ONE MILLION", "INVICTUS", "LADY MILLION", "PHANTOM", "OLYMPEA", "FAME", "PURE XS", "BLACK XS"],
    "SALLY HANSEN": ["MIRACLE GEL", "HARD AS NAILS", "INSTA-DRI", "CUTICLE REHAB", "VITAMIN E"],
    "SENSAI": ["CELLULAR", "BRONZING", "SILK", "TOTAL FINISH", "ABSOLUTE SILK"],
    "SOL DE JANEIRO": ["CHEIROSA", "BUM BUM", "62", "68", "71", "40", "59", "BEIJA FLOR", "DELICIA DRENCH"],
    "SWISS ARABIAN": ["SHAGHAF", "CASABLANCA", "GHARAAM", "LAYALI", "ALTARIKH"],
    "THE ORDINARY": ["NIACINAMIDE", "HYALURONIC", "AHA", "CAFFEINE", "RETINOL", "PEPTIDE", "GLYCOLIC", "SQUALANE", "AZELAIC"],
    "TOMMY HILFIGER": ["TOMMY GIRL", "TOMMY", "IMPACT", "NOW"],
    "VERSACE": ["BRIGHT CRYSTAL", "EROS", "DYLAN", "CRYSTAL NOIR", "EAU FRAICHE", "YELLOW DIAMOND", "MAN EAU FRAICHE"]
}

# Max products safety threshold
MAX_MATCHES = 950

def download_feed():
    req = urllib.request.Request(FEED_URL, headers={'User-Agent': 'Mozilla/5.0'})
    for attempt in range(3):
        try:
            print(f"Downloading BTS catalog (Attempt {attempt+1})...")
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"Download warning: {e}")
            time.sleep(5)
    raise Exception("Failed to fetch BTS feed.")

content = download_feed()
lines = content.splitlines()
print(f"Downloaded catalog with {len(lines)} lines.")

delim = ';' if ';' in lines[0] else ','
reader = csv.DictReader(lines, delimiter=delim)

clean_rows = []

for row in reader:
    row_text = " ".join([str(v) for v in row.values() if v]).upper()
    
    is_match = False
    
    # Check full brands
    if any(b in row_text for b in FULL_BRANDS):
        is_match = True
    else:
        # Check specific best sellers per brand
        for brand, keywords in BRAND_KEYWORDS.items():
            if brand in row_text:
                if any(kw in row_text for kw in keywords):
                    is_match = True
                    break

    if is_match:
        clean_rows.append(row)
        if len(clean_rows) >= MAX_MATCHES:
            print(f"Reached cap of {MAX_MATCHES} matched products.")
            break

print(f"TOTAL MATCHED PRODUCTS: {len(clean_rows)}")

if clean_rows:
    with open("bts_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames, delimiter=delim)
        writer.writeheader()
        writer.writerows(clean_rows)
    print("bts_filtered.csv updated successfully!")
