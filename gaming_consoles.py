import os
import io
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# 1. Fetch DCS Feed
feed_url = os.environ.get("DCS_FEED_URL")
if not feed_url:
    feed_url = "https://dcs.dk/pricelist?kundenummer=Shymon%20Uzzman&type=145501b95430d58794cf995b683fd7eef9a976"

response = requests.get(feed_url)
response.raise_for_status()

# 2. Load CSV Data
df = pd.read_csv(io.StringIO(response.text), sep=';', quotechar='"')
df.columns = df.columns.str.strip()

# Clean up EAN column values for exact matching
df['EAN_Clean'] = df['EAN nummer'].astype(str).str.strip().str.zfill(13)

# 3. Target EAN Whitelist (Gaming & Consoles)
TARGET_EANS = [
    "0045496321390", "0045496321406", "0045496321413", "0045496321444", "0045496321475",
    "0045496430528", "0045496430795", "0045496453138", "0196388421442", "0196388518067",
    "0196388518128", "0196388518166", "0196388518234", "0711719020905", "0711719021711",
    "0711719022381", "0711719022756", "0711719023104", "0711719023609", "0711719023814",
    "0711719025962", "0711719374107", "0711719575856", "0711719575924", "711719577171",
    "0711719593072", "0814585022803", "0889842196368", "0889842654714", "5905784769448",
]

TARGET_EANS_CLEAN = [ean.strip().zfill(13) for ean in TARGET_EANS]

# Filter catalog strictly by Whitelist (only EANs actually present in the DCS feed)
df_whitelist = df[df['EAN_Clean'].isin(TARGET_EANS_CLEAN)].drop_duplicates(subset=['EAN_Clean'], keep='first').copy()

# 4. Stock & Sync_Stock Logic (0 if < 5 or not available, otherwise Beholdning)
status_col = 'Lagerstatus [Ja Lager eller leveringstiden for varen]'
df_whitelist['Stock'] = pd.to_numeric(df_whitelist['Beholdning'], errors='coerce').fillna(0).astype(int)

is_available = (
    df_whitelist[status_col]
    .astype(str)
    .str.strip()
    .str.lower()
    .str.contains(r'\b(?:ja|yes)\b', regex=True, na=False)
)

df_whitelist['Sync_Stock'] = df_whitelist.apply(
    lambda r: int(r['Stock']) if (r['Stock'] >= 5 and is_available.loc[r.name]) else 0,
    axis=1,
)

# 5. Parse Raw Price Column (no markup)
price_col = next((col for col in df_whitelist.columns if 'pris' in col.lower() or 'price' in col.lower()), 'Pris')
df_whitelist['Parsed_Price'] = pd.to_numeric(
    df_whitelist[price_col].astype(str).str.replace(',', '.', regex=False),
    errors='coerce',
).fillna(0)

# Keep clean 13-digit EAN nummer and drop helper column
df_whitelist['EAN nummer'] = df_whitelist['EAN_Clean']
df_final = df_whitelist.drop(columns=['EAN_Clean']).copy()

# 6. Authenticated Scraper Session
session = requests.Session()
session.get("https://dcs.dk/", headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

debug_logs = []

def get_images(row):
    product_link = row.get('Produkt link', '')
    item_name = row.get('Varenavn', 'Unknown')
    images = []

    if isinstance(product_link, str) and product_link.startswith('http'):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://dcs.dk/',
            }
            res = session.get(product_link, headers=headers, timeout=10)
            debug_logs.append(f"Item: {item_name} | Status: {res.status_code} | Link: {product_link}")

            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')

                # Scan script elements
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string and '/upload/products/' in script.string:
                        found = re.findall(r'\/upload\/products\/[a-zA-Z0-9_\/.-]+\.(?:jpg|jpeg|png)', script.string)
                        for f in found:
                            full_url = f.startswith('http') and f or f"https://dcs.dk{f if f.startswith('/') else '/' + f}"
                            cleaned = full_url.replace('/cache/product_list_grid/', '/').replace('/cache/product_view_main/', '/')
                            if cleaned not in images:
                                images.append(cleaned)

                # Fallback to img tags
                if not images:
                    img_tags = soup.find_all('img', src=lambda s: s and '/upload/products/' in s)
                    for img in img_tags:
                        src = img.get('src', '')
                        if 'brand' in src.lower() or 'logo' in src.lower():
                            continue
                        full_url = src if src.startswith('http') else f"https://dcs.dk{src}"
                        cleaned = full_url.replace('/cache/product_list_grid/', '/').replace('/cache/product_view_main/', '/')
                        if cleaned not in images:
                            images.append(cleaned)
        except Exception as e:
            debug_logs.append(f"Error scraping {product_link}: {str(e)}")

    return images

print("Extracting images...")
rows = df_final.to_dict('records')
with ThreadPoolExecutor(max_workers=5) as executor:
    all_images = list(executor.map(get_images, rows))

# Write debug log to file so we can inspect it in GitHub
with open('gaming_scraper_debug.txt', 'w', encoding='utf-8') as f:
    f.write("\n".join(debug_logs))

# Assign extracted images across 16 separate image columns
for i in range(16):
    col_name = f'Image_URL_{i+1}'
    df_final[col_name] = [imgs[i] if len(imgs) > i else '' for imgs in all_images]

# 7. Save Output File
output_filename = 'gaming_consoles.csv'
df_final.to_csv(output_filename, sep=';', index=False)
print(f"Sync finished successfully. {output_filename} updated with {len(df_final)} items.")
