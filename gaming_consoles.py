import html
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
df["EAN_Clean"] = df["EAN nummer"].astype(str).str.strip().str.zfill(13)

# 3. STRICT Whitelist (ONLY these EANs, deduplicated)
RAW_TARGET_EANS = [
    "0045496453138", "0045496321444", "0196388421442", "711719577171", "0711719021711",
    "0711719022756", "0814585022803", "0711719374107", "0711719020905", "0045496430528",
    "0196388518128", "5905784769448", "0711719022381", "0711719575856", "0889842654714",
    "0045496321475", "0711719023814", "0711719025962", "0711719593072", "0045496321413",
    "0196388518067", "0889842196368", "0045496321390", "0196388518166", "0045496430795",
    "0711719023609", "0711719575924", "0045496321406", "0711719023104", "0196388518234",
]
TARGET_EANS_CLEAN = sorted(set(ean.strip().zfill(13) for ean in RAW_TARGET_EANS))

# Keep ONLY rows from DCS matching your whitelist
df_matched = (
    df[df["EAN_Clean"].isin(TARGET_EANS_CLEAN)]
    .drop_duplicates(subset=["EAN_Clean"], keep="first")
    .copy()
)

# Ensure all 30 whitelist EANs are represented so unavailable/filtered items get Sync_Stock = 0
base_whitelist_df = pd.DataFrame({"EAN_Clean": TARGET_EANS_CLEAN})
df_all = pd.merge(base_whitelist_df, df_matched, on="EAN_Clean", how="left")

# Populate EAN nummer for any whitelist EAN missing from DCS feed
df_all["EAN nummer"] = df_all["EAN nummer"].fillna(df_all["EAN_Clean"])

# Clean stray HTML entities (like &nbsp) in text fields while preserving URLs
for text_col in ["Produktbeskrivelse", "Varenavn", "Modelbetegnelse", "Producentnavn"]:
    if text_col in df_all.columns:
        df_all[text_col] = (
            df_all[text_col]
            .fillna("")
            .astype(str)
            .apply(lambda v: re.sub(r"\s+", " ", html.unescape(v.replace("&nbsp", "&nbsp;"))).strip())
        )

# 4. Evaluate Availability: >= 5 pcs AND Immediate In-Stock (exclude incoming / "delivered to us")
avail_col = "Lagerstatus [Ja Lager eller leveringstiden for varen]"
status_text = df_all[avail_col].fillna("").astype(str).str.lower()

raw_qty = pd.to_numeric(df_all["Beholdning"], errors="coerce").fillna(0).astype(int)
is_in_stock = status_text.str.contains(r"\bja\b|\blager\b|\bin stock\b", regex=True, na=False)
is_incoming = status_text.str.contains(r"delivered|levering|external|delivery", regex=True, na=False)

qualifies_for_stock = (raw_qty >= 5) & is_in_stock & (~is_incoming)

df_all["Stock"] = raw_qty
df_all["Sync_Stock"] = raw_qty.where(qualifies_for_stock, 0).astype(int)

# 5. Parse Raw Wholesale Price Only (no retail markup/formula calculations)
price_col = next((col for col in df_all.columns if "pris" in col.lower() or "price" in col.lower()), None)
if price_col:
    df_all["Parsed_Price"] = pd.to_numeric(
        df_all[price_col].astype(str).str.replace(",", ".", regex=False), errors="coerce"
    ).fillna(0)
else:
    df_all["Parsed_Price"] = 0.0

df_final = df_all.drop(columns=["EAN_Clean"]).copy()

# 6. Thread-Safe Exact-Product Image Scraper for Qualifying In-Stock Items Only
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
    if int(row.get("Sync_Stock", 0)) <= 0:
        return []

    product_link = row.get("Produkt link", "")
    images = []

    def add_image_url(raw_url):
        if not raw_url or "/upload/products/" not in raw_url:
            return
        unquoted = html.unescape(str(raw_url)).strip()
        lower_url = unquoted.lower()
        if any(bad in lower_url for bad in ("brand", "logo", "banner", "icon", "related", "upsell")):
            return
        full_url = (
            unquoted
            if unquoted.startswith("http")
            else f"https://dcs.dk{unquoted if unquoted.startswith('/') else '/' + unquoted}"
        )
        cleaned = re.sub(r"/cache/[^/]+/", "/", full_url)
        if cleaned not in images:
            images.append(cleaned)

    if isinstance(product_link, str) and product_link.startswith("http"):
        s = get_thread_session()
        try:
            res = s.get(product_link, timeout=15)

            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")

                # Focus on product gallery / product detail containers first
                gallery_containers = soup.select(
                    "[class*='gallery'], [class*='product-image'], [class*='product-media'], "
                    "[class*='slider'], [class*='carousel'], [id*='gallery'], [id*='product-image']"
                )

                for container in gallery_containers:
                    # Skip containers that clearly belong to related/similar/recommended products
                    ctx_text = " ".join(
                        filter(
                            None,
                            [
                                " ".join(container.get("class", [])),
                                container.get("id", ""),
                            ],
                        )
                    ).lower()
                    if any(skip in ctx_text for skip in ("related", "similar", "recommend", "upsell", "cross", "recent")):
                        continue

                    for tag in container.find_all(["img", "a", "source"]):
                        for attr in ("src", "data-src", "data-zoom-image", "data-large", "href"):
                            val = tag.get(attr)
                            if isinstance(val, str):
                                add_image_url(val)
                        srcset = tag.get("srcset")
                        if isinstance(srcset, str):
                            for entry in srcset.split(","):
                                url_part = entry.strip().split(" ")[0]
                                add_image_url(url_part)

                # Fallback if gallery container selectors didn't capture any product images
                if not images:
                    for tag in soup.find_all(["img", "a", "source"]):
                        if tag.find_parent(
                            attrs={
                                "class": re.compile(r"related|similar|recommend|upsell|cross|recent|footer|nav|header", re.I)
                            }
                        ):
                            continue
                        for attr in ("src", "data-src", "data-zoom-image", "data-large", "href"):
                            val = tag.get(attr)
                            if isinstance(val, str):
                                add_image_url(val)
        except Exception:
            pass

    time.sleep(0.15)
    return images


print("Extracting images for qualifying in-stock Gaming Consoles & Accessories...")
rows = df_final.to_dict("records")
with ThreadPoolExecutor(max_workers=4) as executor:
    all_images = list(executor.map(get_images, rows))

for i in range(16):
    col_name = f"Image_URL_{i+1}"
    df_final[col_name] = [imgs[i] if len(imgs) > i else "" for imgs in all_images]

# 7. Save Output File
output_filename = "gaming_consoles.csv"
df_final.to_csv(output_filename, sep=";", index=False)
active_count = int((df_final["Sync_Stock"] > 0).sum())
print(
    f"Sync complete. {output_filename} generated with {len(df_final)} whitelist items "
    f"({active_count} in stock >=5, {len(df_final) - active_count} set to Sync_Stock=0)."
)
