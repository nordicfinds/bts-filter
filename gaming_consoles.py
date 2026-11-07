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

# 3. Target Gaming EAN Whitelist (Raw inputs provided)
RAW_TARGET_EANS = [
    "0045496453138", "0045496321444", "0196388421442", "711719577171", "0711719021711",
    "0711719022756", "0814585022803", "0711719374107", "0711719020905", "0045496430528",
    "0196388518128", "5905784769448", "0711719022381", "0711719575856", "0889842654714",
    "0045496321475", "0711719023814", "0711719025962", "0711719593072", "0045496321413",
    "0196388518067", "0889842196368", "0045496321390", "0196388518166", "0045496430795",
    "0711719023609", "0711719575924", "0045496321406", "0711719023104", "0196388518234",
    "0889842654714", "0711719023814"
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

# 6. Authenticated Scraper Session (To pull high-resolution nested image paths)
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
                        full_url = src if src.startswith('
