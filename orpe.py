import csv
import io
import requests

# Your 111 target EANs
TARGET_EANS = {
    "6290171002338", "6290171072836", "6290171002345", "6290171075288", "6290171000983", 
    "6290171070214", "614514424018", "614514459812", "614514331033", "614514331088", 
    "614514331057", "614514178065", "614514331026", "614514331040", "614514331064", 
    "614514465059", "614514331071", "614514465165", "3616305616210", "3616305480620", 
    "3616306096202", "3616305821089", "3614229828559", "3616304691645", "3614228220897", 
    "3616303173098", "3616307390507", "8596540000010", "0737052351186", "737052351155", 
    "0737052352060", "0088300104437", "3614229656152", "3607342020887", "3607343811835", 
    "3607342401501", "3616302016693", "3616301296652", "3616304183621", "3616304175978", 
    "3614228834919", "3616307415255", "31655644851", "31655644288", "6298042001947", 
    "6298042000957", "6290360370194", "6290360375601", "6290360375595", "6298042001565", 
    "3348901608053", "3145891166507", "3145891070606", "3145891124309", "629401518863", 
    "6294015149371", "3605522040229", "3614273070256", "3614272907652", "3614273955423", 
    "3614273955560", "3616304203572", "8005610516134", "3414202000534", "3616305638373", 
    "3414202011769", "3616305187567", "3616302038381", "3614229387049", "3614229387056", 
    "3414202000565", "3414202000510", "3607342359789", "3614202000572", "3614228171427", 
    "3616305270153", "3386460107655", "3614273261425", "3614272761452", "3614273672122", 
    "3614274626865", "3614273261357", "3614274351019", "3614274350739", "3360377002944", 
    "3605971671012", "3605972386021", "3360377027619", "3605973048232", "4011700750009", 
    "4011700750191", "719346065399", "719346258111", "3423474786350", "3423470317527", 
    "8011003804542", "8011003823079", "8011003997022", "8018365270756", "8011003809202", 
    "8011003901579", "8011003901623", "8011003891498", "888066015585", "888066151962", 
    "7640496670252", "7640496672812", "7640496670160", "7640496670276", "7640496671204", 
    "22548298220"
}

PRODUCT_FEED_URL = "https://www.orpe.com/feed/nzZLrHpJVZeunG9N5xKgCczbjmHIFRZOFhE0nSDlz98hed9w/product.csv"
STOCK_FEED_URL = "https://www.orpe.com/feed/nzZLrHpJVZeunG9N5xKgCczbjmHIFRZOFhE0nSDlz98hed9w/stock.csv"
MIN_STOCK = 5

def main():
    print("Fetching stock feed...")
    stock_response = requests.get(STOCK_FEED_URL)
    stock_response.raise_for_status()
    
    stock_data = {}
    stock_reader = csv.DictReader(io.StringIO(stock_response.text))
    for row in stock_reader:
        gtin = row.get("gtin", "").strip()
        qty = row.get("quantity", "0").strip()
        if gtin:
            stock_data[gtin] = int(qty) if qty.isdigit() else 0

    print("Fetching product feed and filtering allowlist...")
    prod_response = requests.get(PRODUCT_FEED_URL)
    prod_response.raise_for_status()

    prod_reader = csv.DictReader(io.StringIO(prod_response.text))
    matched_products = []

    for row in prod_reader:
        gtin = row.get("gtin", "").strip()
        
        if gtin not in TARGET_EANS:
            continue
            
        stock = stock_data.get(gtin, 0)
        if stock < MIN_STOCK:
            continue

        title = row.get("title", "")
        sku = row.get("item_group_id", "")
        description = row.get("description", "")
        brand = row.get("brand", "")
        
        raw_price = row.get("price", "0").split()[0]
        try:
            price = float(raw_price)
        except ValueError:
            price = 0.0

        image_url = row.get("image_link", "")

        matched_products.append({
            "sku": sku,
            "ean": gtin,
            "title": title,
            "brand": brand,
            "description": description,
            "price": price,
            "stock": stock,
            "image": image_url
        })

    output_filename = "orpe_filtered.csv"
    with open(output_filename, mode="w", newline="", encoding="utf-8") as f:
        fieldnames = ["sku", "ean", "title", "brand", "description", "price", "stock", "image"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in matched_products:
            writer.writerow(p)

    print(f"Done! Pulled {len(matched_products)} raw wholesale products saved to {output_filename}.")

if __name__ == "__main__":
    main()
