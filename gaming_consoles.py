import io
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 1. Fetch DCS Feed with Retry & Timeout
feed_url = os.environ.get("DCS_FEED_URL")
if not feed_url:
    feed_url = "https://dcs.dk/pricelist?kundenummer=Shymon%20Uzzman&type=145501b95430d58794cf995b683fd7eef9a976"

retry_strategy = Retry(
    total=4,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)
adapter = HTTPAdapter(max_retries=retry_strategy)

http = requests.Session()
http.mount("https://", adapter)
http.mount("http://", adapter)

default_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

response = http.get(feed_url, headers=default_headers, timeout=30)
response.raise_for_status()

# 2. Load CSV Data
df = pd.read_csv(io.StringIO(response.text), sep=";", quotechar='"')
df.columns = df.columns.str.strip()

# Clean up EAN column values for exact matching
df["EAN_Clean"] = df["EAN nummer"].astype(str).str.strip().str.zfill(13)

# 3. Target Gaming EAN Whitelist (ONLY these EANs)
RAW_TARGET_EANS = [
    "0045496453138", "0045496321444", "0196388421442", "711719577171", "0711719021711",
    "0711719022756", "0814585022803", "0711719374107", "0711719020905", "0045496430528",
    "0196388518128", "5905784769448", "0711719022381", "0711719575856", "0889842654714",
    "0045496321475", "0711719023814", "0711719025962", "0711719593072", "0045496321413",
    "0196388518067", "0889842196368", "0045496321390", "0196388518166", "0045496430795",
    "0711719023609", "0711719575924", "0045496321406", "0711719023104", "0196388518234",
]

TARGET_EANS_CLEAN = sorted(set(ean.strip().zfill(13) for ean in RAW_TARGET_EANS))
print(f"Loaded {len(RAW_TARGET_EANS)} raw EANs. Filtered down to {len(TARGET_EANS_CLEAN)} unique items.")

# Filter catalog strictly by Whitelist (only items present in DCS feed)
df_whitelist = df[df["EAN_Clean"].isin(TARGET_EANS_CLEAN)].copy()

# 4. Filter Stock >= 5 & Strictly In Stock (exclude incoming / "delivered to us")
avail_col = "Lagerstatus [Ja Lager eller leveringstiden for varen]"
status_text = df_whitelist[avail_col].astype(str).str.lower()

df_whitelist["Stock"] = pd.to_numeric(df_whitelist["Beholdning"], errors="coerce").fillna(0)
has_min_stock = df_whitelist["Stock"] >= 5
is_in_stock = status_text.str.contains(r"\bja\b|\blager\b|\bin stock\b", regex=True, na=False)
is_incoming = status_text.str.contains(r"delivered|levering|external|delivery", regex=True, na=False)

df_whitelist = df_whitelist[has_min_stock & is_in_stock & (~is_incoming)].copy()

# 5. Parse Price column only (no retail price calculation)
price_col = next((col for col in df_whitelist.columns if "pris" in col.lower() or "price" in col.lower()), "Pris")
df_whitelist["Parsed_Price"] = pd.to_numeric(
    df_whitelist[price_col].astype(str).str.replace(",", ".", regex=False), errors="coerce"
).fillna(0)

df_final = df_whitelist.drop(columns=["EAN_Clean"]).copy()

# 6. Thread-Safe Scraper Session
thread_local = threading.local()

def get_thread_session():
    if not hasattr(thread_local, "session"):
        s = requests.Session()
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        s.headers.update({
            **default_headers,
            "Referer": "https://dcs.dk/",
        })
        try:
            s.get("https://dcs.dk/", timeout=15)
        except Exception:
            pass
        thread_local.session = s
    return thread_local.session

def get_images(row):
    product_link = row.get("Produkt link", "")
    images = []

    if isinstance(product_link, str) and product_link.startswith("http"):
        s = get_thread_session()
        try:
            res = s.get(product_link, timeout=15)

            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")

                scripts = soup.find_all("script")
                for script in scripts:
                    if script.string and "/upload/products/" in script.string:
                        found = re.findall(r"\/upload\/products\/[a-zA-Z0-9_\/.-]+\.(?:jpg|jpeg|png)", script.string)
                        for f in found:
                            full_url = f.startswith("http") and f or f"https://dcs.dk{f if f.startswith('/') else '/' + f}"
                            cleaned = full_url.replace("/cache/product_list_grid/", "/").replace("/cache/product_view_main/", "/")
                            if cleaned not in images:
                                images.append(cleaned)

                if not images:
                    img_tags = soup.find_all("img", src=lambda src: src and "/upload/products/" in src)
                    for img in img_tags:
                        src = img.get("src", "")
                        if "brand" in src.lower() or "logo" in src.lower():
                            continue
                        full_url = src if src.startswith("http") else f"https://dcs.dk{src}"
                        cleaned = full_url.replace("/cache/product_list_grid/", "/").replace("/cache/product_view_main/", "/")
                        if cleaned not in images:
                            images.append(cleaned)
        except Exception:
            pass

    time.sleep(0.15)
    return images

print("Extracting images for Gaming Consoles & Accessories...")
rows = df_final.to_dict("records")
with ThreadPoolExecutor(max_workers=4) as executor:
    all_images = list(executor.map(get_images, rows))

for i in range(16):
    col_name = f"Image_URL_{i+1}"
    df_final[col_name] = [imgs[i] if len(imgs) > i else "" for imgs in all_images]

# 7. Save Output File
output_filename = "gaming_consoles.csv"
df_final.to_csv(output_filename, sep=";", index=False)
print(f"Sync complete. {output_filename} generated with {len(df_final)} items.")
