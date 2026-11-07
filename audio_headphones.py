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

# 6. Safe Image Assignment using the feed's native image column if present
image_col = next((col for col in df_final.columns if 'billede' in col.lower() or 'image' in col.lower() or 'foto' in col.lower()), None)

for i in range(16):
    col_name = f'Image_URL_{i+1}'
    if i == 0 and image_col:
        df_final[col_name] = df_final[image_col].fillna('')
    else:
        df_final[col_name] = ''

# Fallback: construct safe image URLs using Varenummer for items missing a direct feed image
for idx, row in df_final.iterrows():
    item_id = str(row.get('Varenummer', '')).strip()
    if item_id and not df_final.loc[idx, 'Image_URL_1']:
        df_final.loc[idx, 'Image_URL_1'] = f"https://dcs.dk/upload/products/{item_id}.jpg"

# 7. Save Output File
output_filename = 'audio_headphones.csv'
df_final.to_csv(output_filename, sep=';', index=False)
print(f"Sync finished successfully. {output_filename} updated with {len(df_final)} whitelisted audio items.")
