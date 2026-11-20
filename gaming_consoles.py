import io
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
from bs4 import BeautifulSoup

# 1. Fetch DCS Feed
feed_url = os.environ.get("DCS_FEED_URL")
if not feed_url:
    feed_url = "https://dcs.dk/pricelist?kundenummer=Shymon%20Uzzman&type=145501b95430d58794cf995b683fd7eef9a976"

response = requests.get(feed_url, timeout=30)
response.raise_for_status()

# 2. Load CSV Data
df = pd.read_csv(io.StringIO(response.text), sep=";", quotechar='"')
df.columns = df.columns.str.strip()

# Clean up EAN column values for exact matching
df["EAN_Clean"] = df["EAN nummer"].astype(str).str.strip().str.zfill(13)

# 3. Target EAN Whitelist (30 Gaming Consoles & Accessories)
RAW_TARGET_EANS = [
    "0045496453138", "0045496321444", "0196388421442", "711719577171", "0711719021711",
    "0711719022756", "0814585022803", "0711719374107", "0711719020905", "0045496430528",
    "0196388518128", "5905784769448", "0711719022381", "0711719575856", "0889842654714",
    "0045496321475", "0711719023814", "0711719025962", "0711719593072", "0045496321413",
    "0196388518067", "0889842196368", "0045496321390", "0196388518166", "0045496430795",
    "0711719023609", "0711719575924", "0045496321406", "0711719023104", "0196388518234",
]
TARGET_EANS_CLEAN = sorted(set(ean.strip().zfill(13) for ean in RAW_TARGET_EANS))

# Filter catalog strictly by Whitelist (deduplicated)
df_matched = (
    df[df["EAN_Clean"].isin(TARGET_EANS_CLEAN)]
    .drop_duplicates(subset=["EAN_Clean"], keep="first")
    .copy()
)

# Keep all 30 whitelist items so unavailable / incoming / <5 stock items get Sync_Stock = 0
base_whitelist_df = pd.DataFrame({"EAN_Clean": TARGET_EANS_CLEAN})
df_whitelist = pd.merge(base_whitelist_df, df_matched, on="EAN_Clean", how="left")
df_whitelist["EAN nummer"] = df_whitelist["EAN nummer"].fillna(df_whitelist["EAN_Clean"])

# 4. Always Update Stock & Sync_Stock (Minimum 5 stock, immediate availability, no incoming/delivery)
avail_col = "Lagerstatus [Ja Lager eller leveringstiden for varen]"
status_series = df_whitelist[avail_col].fillna("").astype(str).str.lower()

raw_stock = pd.to_numeric(df_whitelist["Beholdning"], errors="coerce").fillna(0).astype(int)
has_min_stock = raw_stock >= 5
is_available = status_series.str.contains(r"\bja\b|\byes\b", regex=True, na=False)
is_incoming = status_series.str.contains(r"delivered|levering|delivery|external", regex=True, na=False)

qualifies = has_min_stock & is_available & (~is_incoming)

df_whitelist["Stock"] = raw_stock
df_whitelist["Sync_Stock"] = raw_stock.where(qualifies, 0).astype(int)

# 5. Always Update Raw Wholesale Price column (no retail price calculations)
price_col = next((col for col in df_whitelist.columns if "pris" in col.lower() or "price" in col.lower()), "Pris")
if price_col in df_whitelist.columns:
    df_whitelist["Parsed_Price"] = pd.to_numeric(
        df_whitelist[price_col].astype(str).str.replace(",", ".", regex=False), errors="coerce"
    ).fillna(0)
else:
    df_whitelist["Parsed_Price"] = 0.0

df_final = df_whitelist.drop(columns=["EAN_Clean"]).copy()

# 6. Scraper Session (matching working audio_headphones pattern)
session = requests.Session()
session.get("https://dcs.dk/", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

debug_logs = []


def get_images(row):
    if int(row.get("Sync_Stock", 0)) <= 0:
        return []

    product_link = row.get("Produkt link", "")
    item_name = row.get("Varenavn", "Unknown")
    images = []

    if isinstance(product_link, str) and product_link.startswith("http"):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://dcs.dk/",
            }
            res = session.get(product_link, headers=headers, timeout=10)
            debug_logs.append(f"Item: {item_name} | Status: {res.status_code} | Link: {product_link}")

            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")

                # Scan script elements
                scripts = soup.find_all("script")
                for script in scripts:
                    if script.string and "/upload/products/" in script.string:
                        found = re.findall(r"\/upload\/products\/[a-zA-Z0-9_\/.-]+\.(?:jpg|jpeg|png)", script.string)
                        for f in found:
                            full_url = f.startswith("http") and f or f"https://dcs.dk{f if f.startswith('/') else '/' + f}"
                            cleaned = full_url.replace("/cache/product_list_grid/", "/").replace("/cache/product_view_main/", "/")
                            if cleaned not in images:
                                images.append(cleaned)

                # Fallback to img tags
                if not images:
                    img_tags = soup.find_all("img", src=lambda s: s and "/upload/products/" in s)
                    for img in img_tags:
                        src = img.get("src", "")
                        if "brand" in src.lower() or "logo" in src.lower():
                            continue
                        full_url = src if src.startswith("http") else f"https://dcs.dk{src}"
                        cleaned = full_url.replace("/cache/product_list_grid/", "/").replace("/cache/product_view_main/", "/")
                        if cleaned not in images:
                            images.append(cleaned)
        except Exception as e:
            debug_logs.append(f"Error scraping {product_link}: {str(e)}")

    time.sleep(0.1)
    return images


print("Extracting images...")
rows = df_final.to_dict("records")
with ThreadPoolExecutor(max_workers=5) as executor:
    all_images = list(executor.map(get_images, rows))

# Write debug log to file so we can inspect it in GitHub
with open("scraper_debug.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(debug_logs))

# Assign extracted images across 16 separate image columns
for i in range(16):
    col_name = f"Image_URL_{i+1}"
    df_final[col_name] = [imgs[i] if len(imgs) > i else "" for imgs in all_images]

# 7. Save Output File
output_filename = "gaming_consoles.csv"
df_final.to_csv(output_filename, sep=";", index=False)
print(f"Sync finished successfully. {output_filename} updated with {len(df_final)} items.")
