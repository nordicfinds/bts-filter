import os
import io
import pandas as pd
import requests

# 1. Fetch DCS Feed
feed_url = os.environ.get("DCS_FEED_URL")
if not feed_url:
    feed_url = "https://dcs.dk/pricelist?kundenummer=Shymon%20Uzzman&type=145501b95430d58794cf995b683fd7eef9a976"

response = requests.get(feed_url)
response.raise_for_status()

# 2. Load CSV Data
df = pd.read_csv(io.StringIO(response.text), sep=';', quotechar='"')
df.columns = df.columns.str.strip()

# 3. Filter Stock & Availability
df['Stock'] = pd.to_numeric(df['Beholdning'], errors='coerce').fillna(0)
df = df[df['Stock'] >= 5]
df = df[df['Lagerstatus [Ja Lager eller leveringstiden for varen]'].astype(str).str.lower().str.contains('ja|yes', na=False)]
df = df.dropna(subset=['EAN nummer', 'Varenummer'])

# 4. Filter Brand New Items Only (Exclude Pre-owned / Refurbished)
excluded_terms = ['preowned', 'refurbished', 't1a', 'used', 'sekunda']
pattern = '|'.join(excluded_terms)

df = df[~df['Producentnavn'].astype(str).str.lower().str.contains(pattern, na=False)]
df = df[~df['Varenavn'].astype(str).str.lower().str.contains(pattern, na=False)]

# 5. Target Core Brands
target_brands = [
    'apple', 'samsung', 'philips', 'panzerglass', 'sony', 'dudao', 
    'bose', 'logitech', 'sandisk', 'kingston technology', 'jabra', 
    'google', 'microsoft', 'msi', 'gigabyte technology', 'asrock', 'innovision multimedia'
]
df = df[df['Producentnavn'].astype(str).str.lower().isin(target_brands)]

# 6. Swedish Chemical Tax Avoidance (Product Category Keywords)
safe_keywords = [
    'glass', 'protector', 'screen', 'cover', 'case', 'sleeve', 'pouch', 'wallet',
    'charger', 'powerbank', 'magsafe', 'adapter', 'dock', 'cable', 'holder', 'mount', 'stand',
    'trimmer', 'shaver', 'clipper', 'groomer', 'razor', 'toothbrush', 'sonicare', 'brushhead',
    'earbud', 'earphone', 'headphone', 'headset', 'speaker', 'airpods', 'buds',
    'mouse', 'keyboard', 'controller', 'gamepad',
    'memory', 'sdcard', 'microsd', 'flash', 'pendrive', 'ssd'
]
safe_pattern = '|'.join(safe_keywords)

df_se = df[df['Varenavn'].astype(str).str.lower().str.contains(safe_pattern, na=False)].copy()
df_dk = df.copy()

# 7. Sort by Highest Stock & Limit to Top 200 Maximum per Market
df_se = df_se.sort_values(by='Stock', ascending=False).head(200)
df_dk = df_dk.sort_values(by='Stock', ascending=False).head(200)

# 8. Save CSV Outputs (Keeping raw wholesale 'Pris' in SEK for BaseLinker)
df_se.to_csv('dcs_filtered_se.csv', sep=';', index=False)
df_dk.to_csv('dcs_filtered_dk.csv', sep=';', index=False)

print(f"Sync finished successfully. SE Items: {len(df_se)}, DK Items: {len(df_dk)}")
