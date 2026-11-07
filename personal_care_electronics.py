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

# 3. Target Personal Care EAN Whitelist
RAW_TARGET_EANS = [
    "8720689012850", "8720689027137", "8710103944119", "880588710010", "3030050161939",
    "8700216555562", "8720689024686", "8720689027298", "8720689030557", "4210201163305",
    "8700216735667", "4210201432982", "8700216646130", "8720689019033", "8720689019033",
    "3030050153361", "3030050175691", "3030050191912", "8006530015431", "8700216612272",
    "4210201432227", "8700216930260", "8006540860809", "8006530016704", "8700216456968",
    "8700216612364", "8700216777131", "8001090914217", "8006540957196", "8700216198899",
    "4210201445197", "8700216931533", "8700216194693", "8006540773178", "4210201434818",
    "8700216774130", "8006540731659", "8720689021685", "8700216199438", "8720689021425",
    "8006540772645", "8700216194761", "8006540743027", "8700216297257", "8700216612470",
    "8006540860960", "8700216778541", "4210201426967", "8006540772409", "8700216932820",
    "8700216297172", "8700216735797", "8710103941941", "8720689027083", "8720689045612",
    "8710103997122", "8720689031875", "8720689016148", "8710103924005", "8720689045209",
    "8720689002219", "8710103997177", "8700216735797", "8720689037846"
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

print("Extracting images for Personal Care Electronics...")
rows = df_final.to_dict('records')
with ThreadPoolExecutor(max_workers=5) as executor:
    all_images = list(executor.map(get_images, rows))

# Expand extracted image list into 16 individual URL columns for BaseLinker
for i in range(16):
    col_name = f'Image_URL_{i+1}'
    df_final[col_name] = [imgs[i] if len(imgs) > i else '' for imgs in all_images]

# 7. Save Output File
output_filename = 'personal_care.csv'
df_final.to_csv(output_filename, sep=';', index=False)
print(f"Sync complete. {output_filename} generated with {len(df_final)} items.")
