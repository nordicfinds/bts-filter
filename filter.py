import csv
import urllib.request

# BTS Feed URL
FEED_URL = "https://www.btswholesaler.com/generatefeedbts?user_id=1429150&pass=Avedore556,&format=CSV&language_code=en-GB"

# Targeted EANs/SKUs list or target brand keywords
TARGET_BRANDS = [
    "AL HARAMAIN", 
    "AFNAN", 
    "PARIS CORNER", 
    "MAISON ALHAMBRA", 
    "FRAGRANCE WORLD", 
    "FRENCH AVENUE", 
    "ARMAF"
]

print("Downloading master BTS feed...")
urllib.request.urlretrieve(FEED_URL, "bts_raw.csv")

clean_rows = []
total_count = 0

with open("bts_raw.csv", mode="r", encoding="utf-8", errors="ignore") as infile:
    reader = csv.DictReader(infile)
    fieldnames = reader.fieldnames
    
    for row in reader:
        mfg = (row.get("manufacturer") or "").upper()
        # Keep matching items up to 950 products max to stay safely under Base.com free limit
        if any(brand in mfg for brand in TARGET_BRANDS):
            clean_rows.append(row)
            total_count += 1
            if total_count >= 950:
                break

print(f"Filtered total: {len(clean_rows)} products.")

with open("bts_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(clean_rows)

print("Clean CSV saved successfully!")
