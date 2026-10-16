import csv
import urllib.request

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

print("Downloading master BTS feed...")

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0'}
req = urllib.request.Request(FEED_URL, headers=headers)

try:
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8', errors='ignore')
        with open("bts_raw.csv", "w", encoding="utf-8") as outfile:
            outfile.write(content)
    print("Download successful!")
except Exception as e:
    print(f"FAILED TO DOWNLOAD FEED: {e}")

clean_rows = []
total_count = 0

try:
    with open("bts_raw.csv", mode="r", encoding="utf-8", errors="ignore") as infile:
        lines = infile.readlines()
        if lines:
            print(f"Raw file total lines downloaded: {len(lines)}")
            print(f"Header preview: {lines[0][:120]}")
            
            # Detect delimiter automatically
            delim = ';' if ';' in lines[0] else ','
            reader = csv.DictReader(lines, delimiter=delim)
            fieldnames = reader.fieldnames
            
            for row in reader:
                mfg = (row.get("manufacturer") or row.get("Brand") or row.get("brand") or "").upper()
                title = (row.get("name") or row.get("title") or row.get("Product Name") or "").upper()
                
                is_match = False
                
                if any(brand in mfg for brand in FULL_BRANDS):
                    is_match = True
                else:
                    for brand, keywords in BEST_SELLER_KEYWORDS.items():
                        if brand in mfg:
                            if any(keyword in title for keyword in keywords):
                                is_match = True
                                break

                if is_match:
                    clean_rows.append(row)
                    total_count += 1
                    if total_count >= 950:
                        break

    print(f"Filtered total best-sellers: {len(clean_rows)} products.")

    if clean_rows:
        with open("bts_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(clean_rows)
        print("Clean CSV saved successfully!")
except Exception as e:
    print(f"Error processing CSV file: {e}")
