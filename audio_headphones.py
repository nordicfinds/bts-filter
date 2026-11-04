import os
import io
import json
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

# 5. Target Audio & Tech Brands Whitelist
target_brands = [
    'sony', 'bose', 'jabra', 'philips', 'apple', 'samsung', 'logitech', 'dudao'
]
df = df[df['Producentnavn'].astype(str).str.lower().isin(target_brands)]

# 6. Audio & Headphone Specific Keywords Filter
audio_keywords = [
    'earbud', 'earphone', 'headphone', 'headset', 'speaker', 'airpods', 'buds'
]
audio_pattern = '|'.join(audio_keywords)

df_filtered = df[df['Varenavn'].astype(str).str.lower().str.contains(audio_pattern, na=False)].copy()

# 7. Price Ceiling Filter (Max 2000)
# Clean and convert price column to numeric (assuming column name is 'Pris' or similar)
price_col = next((col for col in df_filtered.columns if 'pris' in col.lower() or 'price' in col.lower()), 'Pris')
df_filtered['Parsed_Price'] = pd.to_numeric(df_filtered[price_col].astype(str).str.replace(',', '.', regex=False), errors='coerce').fillna(0)
df_filtered = df_filtered[df_filtered['Parsed_Price'] <= 2000]

# 8. Sort by Stock Depth & Limit to Top 40 Audio Items
df_final = df_filtered.sort_values(by='Stock', ascending=False).head(40).copy()

# 9. Extract Images via JSON / Script Parsers & Fallback ID Patterns
def get_images(row):
    product_link = row.get('Produkt link', '')
    item_id = str(row.get('Varenummer', '')).strip()
    images = []
    
    if isinstance(product_link, str) and product_link.startswith('http'):
        try:
            res = requests.get(product_link, timeout=5)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # Method A: Look for script tags containing product image arrays
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string and '/upload/products/' in script.string:
                        import re
                        found = re.findall(r'\/upload\/products\/[a-zA-Z0-9_\/.-]+\.(?:jpg|jpeg|png)', script.string)
                        for f in found:
                            full_url = f.startswith('http') and f or f"https://dcs.dk{f if f.startswith('/') else '/' + f}"
                            cleaned = full_url.replace('/cache/product_list_grid/', '/').replace('/cache/product_view_main/', '/')
                            if cleaned not in images:
                                images.append(cleaned)
                
                # Method B: Standard image tags fallback
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
            
    # Fallback to direct item ID pattern if page scraping yielded nothing
    if not images and item_id:
        images.append(f"https://dcs.dk/upload/products/{item_id}.jpg")
        
    return images

print("Extracting high-resolution images for Audio & Headphones (Top 40)...")
rows = df_final.to_dict('records')
with ThreadPoolExecutor(max_workers=10) as executor:
    all_images = list(executor.map(get_images, rows))

# Assign extracted images across 16 separate image columns for BaseLinker
for i in range(16):
    col_name = f'Image_URL_{i+1}'
    df_final[col_name] = [imgs[i] if len(imgs) > i else '' for imgs in all_images]

# 10. Save Category File
output_filename = 'audio_headphones.csv'
df_final.to_csv(output_filename, sep=';', index=False)
print(f"Sync finished successfully. {output_filename} updated with {len(df_final)} items.")
