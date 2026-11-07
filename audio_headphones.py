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

# 3. Target EAN Whitelist (45 Headphones & Earphones)
TARGET_EANS = [
    "0195950543742", "0195951378923", "0195949506123", "0195951378718", "0195949689567",
    "0195949688485", "0190198001733", "0194252818527", "0190198107077", "0194253715122",
    "0195949508967", "0194253715306", "0017817848961", "0017817849791", "0017817846172",
    "0017817859639", "0017817859684", "0017817859738", "0017817861212", "0017817867009",
    "0017817867016", "0017817860048", "0017817846912", "0017817853460", "0017817861120",
    "0017817854726", "0017817860482", "8806097984832", "8806097985341", "8806090270123",
    "8806090270062", "8806097621027", "4548736171374", "4548736142862", "4548736156432",
    "4548736142374", "5706991022865", "5706991022827", "5706991024364", "5706991024340",
    "5706991022803", "5706991024302", "5706991023275", "8887910060117"
]

TARGET_EANS_CLEAN = [ean.strip().zfill(13) for ean in TARGET_EANS]

# Filter catalog strictly by Whitelist
df_whitelist = df[df['EAN_Clean'].isin(TARGET_EANS_CLEAN)].copy()

# 4. Filter Stock & Availability (Minimum 5 stock)
df_whitelist['Stock'] = pd.to_numeric(df_whitelist['Beholdning'], errors='coerce').fillna(0)
df_whitelist = df_whitelist[df_whitelist['Stock'] >= 5]
df_whitelist = df_whitelist[df_whitelist['Lagerstatus [Ja Lager eller leveringstiden for varen]'].astype(str).str.lower().str.contains('ja|yes', na=False)]

# 5. Parse Price column
price_col = next((col for col in df_whitelist.columns if 'pris' in col.lower() or 'price' in col.lower()), 'Pris')
df_whitelist['Parsed_Price'] = pd.to_numeric(df_whitelist[price_col].astype(str).str.replace(',', '.', regex=False), errors='coerce').fillna(0)

df_final = df_whitelist.drop(columns=['EAN_Clean']).copy()

# 6. Authenticated Scraper Session to bypass 404 login wall
session = requests.Session()
# Establish session cookies by hitting the main catalog site first
session.get("https://dcs.dk/", headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

def get_images(row):
    product_link = row.get('Produkt link', '')
    item_id = str(row.get('Varenummer', '')).strip()
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
                
                # Extract image paths from script elements
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string and '/upload/products/' in script.string:
                        found = re.findall(r'\/upload\/products\/[a-zA-Z0-9_\/.-]+\.(?:jpg|jpeg|png)', script.string)
                        for f in found:
                            full_url = f.startswith('http') and f or f"https://dcs.dk{f if f.startswith('/') else '/' + f}"
                            cleaned = full_url.replace('/cache/product_list_grid/', '/').replace('/cache/product_view_main/', '/')
                            if cleaned not in images:
                                images.append(cleaned)
                
                # Fallback to img tags if scripts didn't catch them
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

print("Extracting authenticated high-resolution images for Audio & Headphones...")
rows = df_final.to_dict('records')
with ThreadPoolExecutor(max_workers=5) as executor:
    all_images = list(executor.map(get_images, rows))

# Assign extracted images across 16 separate image columns for BaseLinker
for i in range(16):
    col_name = f'Image_URL_{i+1}'
    df_final[col_name] = [imgs[i] if len(imgs) > i else '' for imgs in all_images]

# 7. Save Output File
output_filename = 'audio_headphones.csv'
df_final.to_csv(output_filename, sep=';', index=False)
print(f"Sync finished successfully. {output_filename} updated with {len(df_final)} items.")
