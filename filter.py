import csv
import urllib.request

# BTS Feed URL with encoded password (Avedore556,)
FEED_URL = "https://www.btswholesaler.com/generatefeedbts?user_id=1429150&pass=Avedore556%2C&format=csv&language_code=en-GB"

# Target Brands/Keywords
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

# Send request with a browser User-Agent to avoid HTTP 403 blocks
req = urllib.request.Request(
    FEED_URL, 
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
)

with urllib.request.urlopen(req) as response, open("bts_raw.csv", "wb") as outfile:
    outfile.write(response.read())

clean_rows = []
total_count = 0

with open("bts_raw.csv", mode="r", encoding="utf-8", errors="ignore") as infile:
    reader = csv.DictReader(infile)
    fieldnames = reader.fieldnames
    
    for row in reader:
        mfg = (row.get("manufacturer") or "").upper()
        # Keep matching items up to 950 products max to stay under Base.com free limit
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
