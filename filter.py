import csv
import urllib.request

FEED_URL = "https://www.btswholesaler.com/generatefeedbts?user_id=1429150&pass=Avedore556%2C&format=csv&language_code=en-GB"

FULL_BRANDS = [
    "AFNAN", "AL HARAMAIN", "ARABIYAT", "ARMAF", "FRAGRANCE WORLD", 
    "FRENCH AVENUE", "LATTAFA", "MAISON ALHAMBRA", "RASASI", "SWISS ARABIAN",
    "PARIS CORNER"
]

print("Starting fresh download from BTS...")
req = urllib.request.Request(FEED_URL, headers={'User-Agent': 'Mozilla/5.0'})

try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        content = resp.read().decode('utf-8', errors='ignore')
        lines = content.splitlines()
    print(f"Successfully downloaded {len(lines)} total lines.")
except Exception as e:
    print(f"Download error: {e}")
    lines = []

if lines:
    delim = ';' if ';' in lines[0] else ','
    reader = csv.DictReader(lines, delimiter=delim)
    
    clean_rows = []
    checked_count = 0
    
    for row in reader:
        checked_count += 1
        row_text = " ".join([str(val) for val in row.values()]).upper()
        
        # Check if any brand is in the row text
        if any(brand in row_text for brand in FULL_BRANDS):
            clean_rows.append(row)
            if len(clean_rows) >= 950:
                break
                
    print(f"Checked {checked_count} rows total.")
    print(f"Found matches: {len(clean_rows)}")
    
    # Save output
    with open("bts_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames, delimiter=delim)
        writer.writeheader()
        writer.writerows(clean_rows)
    print("bts_filtered.csv saved successfully!")
else:
    print("Error: No lines to process.")
