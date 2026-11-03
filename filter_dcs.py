import os
import io
import pandas as pd
import requests

# 1. Fetch DCS Feed
feed_url = os.environ.get("DCS_FEED_URL")
if not feed_url:
    # Fallback to direct URL if environment variable is not set
    feed_url = "https://dcs.dk/pricelist?kundenummer=Shymon%20Uzzman&type=145501b95430d58794cf995b683fd7eef9a976"

response = requests.get(feed_url)
response.raise_for_status()

# 2. Load CSV Data
df = pd.read_csv(io.StringIO(response.text), sep=';', quotechar='"')
df.columns = df.columns.str.strip()

# 3. Basic Stock & Data Hygiene
df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0)
df = df[df['Stock'] >= 5]
df = df[df['Stock status [yes or expected delivery time]'].str.lower() == 'yes']
df = df.dropna(subset=['EAN number', 'Product number'])

# 4. Filter Brand New Items Only (Exclude Pre-owned / Refurbished)
excluded_terms = ['preowned', 'refurbished', 't1a', 'used', 'sekunda']
pattern = '|'.join(excluded_terms)

df = df[~df['Brand'].str.lower().str.contains(pattern, na=False)]
df = df[~df['Name'].str.lower().str.contains(pattern, na=False)]

# 5. Target Core Brands
target_brands = [
    'apple', 'samsung', 'philips', 'panzerglass', 'sony', 'dudao', 
    'bose', 'logitech', 'sandisk', 'kingston technology', 'jabra', 
    'google', 'microsoft', 'msi', 'gigabyte technology', 'asrock', 'innovision multimedia'
]
df = df[df['Brand'].str.lower().isin(target_brands)]

# 6. Swedish Chemical Tax Avoidance (Product Category Keywords)
safe_keywords = [
    # Mobile & Tablet Accessories
    'glass', 'protector', 'screen', 'cover', 'case', 'sleeve', 'pouch', 'wallet',
    'charger', 'powerbank', 'magsafe', 'adapter', 'dock', 'cable', 'holder', 'mount', 'stand',
    
    # Personal Care & Grooming
    'trimmer', 'shaver', 'clipper', 'groomer', 'razor', 'toothbrush', 'sonicare', 'brushhead',
    
    # Audio & Peripherals
    'earbud', 'earphone', 'headphone', 'headset', 'speaker', 'airpods', 'buds',
    'mouse', 'keyboard', 'controller', 'gamepad',
    
    # Storage & Memory
    'memory', 'sdcard', 'microsd', 'flash', 'pendrive', 'ssd'
]
safe_pattern = '|'.join(safe_keywords)

# Filter Sweden catalog strictly to safe categories across target brands
df_se = df[df['Name'].str.lower().str.contains(safe_pattern, na=False)].copy()

# Denmark receives full brand-new catalog across target brands
df_dk = df.copy()

# 7. Sort by Highest Stock & Limit to Top 200 Maximum per Market
df_se = df_se.sort_values(by='Stock', ascending=False).head(200)
df_dk = df_dk.sort_values(by='Stock', ascending=False).head(200)

# 8. Save CSV Outputs (Preserving raw supplier 'Price' in SEK for BaseLinker)
df_se.to_csv('dcs_filtered_se.csv', sep=';', index=False)
df_dk.to_csv('dcs_filtered_dk.csv', sep=';', index=False)

print(f"Sync finished successfully. SE Items: {len(df_se)}, DK Items: {len(df_dk)}")
