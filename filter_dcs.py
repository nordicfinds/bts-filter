import os
import io
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

# 3. Filter Stock & Availability (Minimum 5 stock, confirmed status)
df['Stock'] = pd.to_numeric(df['Beholdning'], errors='coerce').fillna(0)
df = df[df['Stock'] >= 5]
df = df[df['Lagerstatus [Ja Lager eller leveringstiden for varen]'].astype(str).str.lower().str.contains('ja|yes', na=False)]
df = df.dropna(subset=['EAN nummer', 'Varenummer'])

# 4. Filter Brand New Items Only
excluded_terms = ['preowned', 'refurbished', 't1a', 'used', 'sekunda']
pattern = '|'.join(excluded_terms)

df = df[~df['Producentnavn'].astype(str).str.lower().str.contains(pattern, na=False)]
df = df[~df['Varenavn'].astype(str).str.lower().str.contains(pattern, na=False)]

# 5. Target Core Brands Whitelist
target_brands = [
    'apple', 'samsung', 'philips', 'panzerglass', 'sony', 'dudao', 
    'bose', 'logitech', 'sandisk', 'kingston technology', 'jabra', 
    'google', 'microsoft', 'msi', 'gigabyte technology', 'asrock', 'innovision multimedia'
]
df = df[df['Producentnavn'].astype(str).str.lower().isin(target_brands)]

# 6. Swedish Chemical Tax Safe Product Categories
safe_keywords = [
    'glass', 'protector', 'screen', 'cover', 'case', 'sleeve', 'pouch', 'wallet',
    'charger', 'powerbank', 'magsafe', 'adapter', 'dock', 'cable', 'holder', 'mount', 'stand',
    'trimmer', 'shaver', 'clipper', 'groomer', 'razor', 'toothbrush', 'sonicare', 'brushhead',
    'earbud', 'earphone', 'headphone', 'headset', 'speaker', 'airpods', 'buds',
    'mouse', 'keyboard', 'controller', 'gamepad',
    'memory', 'sdcard', 'microsd', 'flash', 'pendrive', 'ssd'
]
safe_pattern = '|'.join(safe_keywords)

df_filtered = df[df['Varenavn'].astype(str).str.lower().str.contains(safe_pattern, na=False)].copy()

# 7. Sort by Stock Depth & Limit to Top 200 Items
df_final = df_filtered.sort_values(by='Stock', ascending=False).head(200).copy()

# 8. Scrape Full-Resolution Images (Strictly from Product Pages)
def clean_image_url(url):
    """Strip thumbnail cache paths to force full-resolution images."""
    if not url:
        return ''
    return url.replace('/cache/product_list_grid/', '/').replace('/cache/product_view_main/', '/')

def get_all_product_images(row):
    product_link = row.get('Produkt link', '')
    images = []
    
    if isinstance(product_link, str) and product_link.startswith('http'):
        try:
            res = requests.get(product_link, timeout=5)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                img_tags = soup.find_all('img', src=lambda s: s and '/upload/products/' in s)
                for img in img_tags:
                    src = img.get('src', '')
                    full_url = src if src.startswith('http') else f"https://dcs.dk{src}"
                    cleaned_url = clean_image_url(full_url)
                    if cleaned_url and cleaned_url not in images:
                        images.append(cleaned_url)
        except Exception:
            pass
            
    return images

print("Scraping verified full-resolution product images...")
rows = df_final.to_dict('records')
with ThreadPoolExecutor(max_workers=10) as executor:
    all_images = list(executor.map(get_all_product_images, rows))

# Assign extracted images across 16 separate image columns for BaseLinker
for i in range(16):
    col_name = f'Image_URL_{i+1}'
    df_final[col_name] = [imgs[i] if len(imgs) > i else '' for imgs in all_images]

# 9. Save Master File
df_final.to_csv('dcs_filtered.csv', sep=';', index=False)
print(f"Sync finished successfully. Master catalog updated with {len(df_final)} items.")
