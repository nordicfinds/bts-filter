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

# 5. Whitelist Brands
target_brands = [
    'apple', 'samsung', 'philips', 'panzerglass', 'sony', 'dudao', 
    'bose', 'logitech', 'sandisk', 'kingston technology', 'jabra', 
    'google', 'microsoft', 'msi', 'gigabyte technology', 'asrock', 'innovision multimedia'
]
df = df[df['Producentnavn'].astype(str).str.lower().isin(target_brands)]

# 6. Swedish Chemical Tax Safe Categories
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

# 7. Sort and limit to top 200 items
df_final = df_filtered.sort_values(by='Stock', ascending=False).head(200).copy()

# 8. Scrape Direct Image URLs
def get_image_url(product_link):
    if not isinstance(product_link, str) or not product_link.startswith('http'):
        return ''
    try:
        res = requests.get(product_link, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            img_tag = soup.find('img', src=lambda s: s and '/upload/products/' in s)
            if img_tag and img_tag.get('src'):
                src = img_tag['src']
                return src if src.startswith('http') else f"https://dcs.dk{src}"
    except Exception:
        pass
    return ''

print("Fetching direct image URLs for items...")
with ThreadPoolExecutor(max_workers=10) as executor:
    df_final['Image_URL'] = list(executor.map(get_image_url, df_final['Produkt link']))

# 9. Export Master File
df_final.to_csv('dcs_filtered.csv', sep=';', index=False)
print(f"Sync finished. Master catalog updated with {len(df_final)} items and image URLs.")
