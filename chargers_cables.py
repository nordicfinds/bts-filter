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

# 3. Target Accessories, Chargers, Cables & Storage EAN Whitelist
RAW_TARGET_EANS = [
    "194252157022", "0195949121296", "0195950673982", "0195950084658", "0195949376733",
    "8801643979393", "8806094912128", "6976625334919", "0197531544216", "8806094912029",
    "8806094912081", "8806090973369", "8806090104527", "8806094911985", "8806095471761",
    "0840353913776", "8801643979379", "8806092933996", "8806097735618", "8806090973338",
    "8806092673885", "8806095720838", "8806092709904", "8806092709874", "0194252192467",
    "0195949590580", "0195949590696", "6973687242985", "8806092978539", "6976625332595",
    "6976625332618", "0195949371905", "0195949775390", "0195949093432", "0194252750872",
    "194253939276", "0195949122880", "0195949085611", "0195949333989", "8806090545917",
    "8806090545931"
]

# Deduplicate entries while preserving padded 13-digit formatting
TARGET_EANS_CLEAN = list(set([ean.strip().zfill(13) for ean in RAW_TARGET_EANS]))
print(f"Loaded {len(RAW_TARGET_EANS)} raw EANs. Detected duplicates and filtered down to {len(TARGET_EANS_CLEAN)} unique items.")

# Filter catalog strictly by Whitelist
df_whitelist = df[df['EAN_Clean'].isin(TARGET_EANS_CLEAN)].copy()

# 4. Filter Stock & Availability (Minimum 5 stock threshold)
df_whitelist['Stock'] = pd.to_numeric(df_whitelist['Beholdning'], errors='coerce').fillna(0)
df_whitelist = df_whitelist[df_whitelist['Stock'] >= 5]
df_whitelist = df_whitelist[df_whitelist['Lagerstatus [Ja Lager eller leveringstiden for varen]'].astype(str).str.lower().str.contains('ja|yes', na=False)]

# 5. Parse Price column
price_col = next((col for col in df_whitelist.columns if 'pris' in col.lower() or 'price' in col.lower()), 'Pris')
df_whitelist['Parsed_Price'] = pd.to_numeric(df_whitelist[price_col].astype(str).str.replace(',', '.', regex=False), errors='coerce').fillna(0)

df_final = df_whitelist.drop(columns=['EAN_Clean']).copy()

# 6. Authenticated Scraper Session
session = requests.Session()
session.get("https://dcs.dk/", headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

def get_images(row):
    product_link = row.get('Produkt link', '')
    images = []
    
    if isinstance(product_link, str) and product_link.startswith('http'):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://dcs.dk/'
            }
            res = session.get(product_link, headers=headers, timeout=10)
            
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # Scan script elements for nested image subfolder paths
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string and '/upload/products/' in script.string:
                        found = re.findall(r'\/upload\/products\/[a-zA-Z0-9_\/.-]+\.(?:jpg|jpeg|png)', script.string)
                        for f in found:
                            full_url = f.startswith('http') and f or f"https://dcs.dk{f if f.startswith('/') else '/' + f}"
                            cleaned = full_url.replace('/cache/product_list_grid/', '/').replace('/cache/product_view_main/', '/')
                            if cleaned not in images:
                                images.append(cleaned)
                
                # Fallback to img tags if dynamic script extraction returns empty
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
        except Exception:
            pass
            
    return images

print("Extracting images for Accessories, Chargers, and Cables...")
rows = df_final.to_dict('records')
with ThreadPoolExecutor(max_workers=5) as executor:
    all_images = list(executor.map(get_images, rows))

# Expand extracted image list into 16 individual URL columns for BaseLinker
for i in range(16):
    col_name = f'Image_URL_{i+1}'
    df_final[col_name] = [imgs[i] if len(imgs) > i else '' for imgs in all_images]

# 7. Save Output File
output_filename = 'chargers_cables.csv'
df_final.to_csv(output_filename, sep=';', index=False)
print(f"Sync complete. {output_filename} generated with {len(df_final)} items.")
