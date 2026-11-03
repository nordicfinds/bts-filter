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

# Print columns to GitHub logs so we can see exact naming if needed
print("Available columns in DCS feed:", df.columns.tolist())

# 3. Find Stock Column dynamically (handles 'Stock', 'Lager', 'Antal', etc.)
stock_col = None
for col in df.columns:
    if 'stock' in col.lower() or 'lager' in col.lower() or 'antal' in col.lower():
        stock_col = col
        break

if not stock_col:
    raise ValueError(f"Could not find stock column in feed. Available columns: {df.columns.tolist()}")

df['Stock'] = pd.to_numeric(df[stock_col], errors='coerce').fillna(0)

# 4. Find Stock Status Column dynamically
status_col = None
for col in df.columns:
    if 'status' in col.lower() or 'delivery' in col.lower():
        status_col = col
        break

df = df[df['Stock'] >= 5]
if status_col:
    df = df[df[status_col].astype(str).str.lower().str.contains('yes|ja', na=False)]

df = df.dropna(subset=['EAN number', 'Product number'])

# 5. Filter Brand New Items Only (Exclude Pre-owned / Refurbished)
excluded_terms = ['preowned', 'refurbished', 't1a', 'used', 'sekunda']
pattern = '|'.join(excluded_terms)

df = df[~df['Brand'].str.lower().str.contains(pattern, na=False)]
df = df[~df['Name'].str.lower().str.contains(pattern, na=False)]

# 6. Target Core Brands
target_brands = [
    'apple', 'samsung', 'philips', 'panzerglass', 'sony', 'dudao', 
    'bose', 'logitech', 'sandisk', 'kingston technology', 'jabra', 
    'google', 'microsoft', 'msi', 'gigabyte technology', 'asrock', 'innovision multimedia'
]
df = df[df['Brand'].str.lower().isin(target_brands)]

# 7. Swedish Chemical Tax Avoidance (Product Category Keywords)
safe_keywords = [
    'glass', 'protector', 'screen', 'cover', 'case', 'sleeve', 'pouch', 'wallet',
    'charger', 'powerbank', 'magsafe', 'adapter', 'dock', 'cable', 'holder', 'mount', 'stand',
    'trimmer', 'shaver', 'clipper', 'groomer', 'razor', 'toothbrush', 'sonicare', 'brushhead',
    'earbud', 'earphone', 'headphone', 'headset', 'speaker', 'airpods', 'buds',
    'mouse', 'keyboard', 'controller', 'gamepad',
    'memory', 'sdcard', 'microsd', 'flash', 'pendrive', 'ssd'
]
safe_pattern = '|'.join(safe_keywords)

df_se = df[df['Name'].str.lower().str.contains(safe_pattern, na=False)].copy()
df_dk = df.copy()

# 8. Sort by Highest Stock & Limit to Top 200 Maximum per Market
df_se = df_se.sort_values(by='Stock', ascending=False).head(200)
df_dk = df_dk.sort_values(by='Stock', ascending=False).head(200)

# 9. Save CSV Outputs
df_se.to_csv('dcs_filtered_se.csv', sep=';', index=False)
df_dk.to_csv('dcs_filtered_dk.csv', sep=';', index=False)

print(f"Sync finished successfully. SE Items: {len(df_se)}, DK Items: {len(df_dk)}")
