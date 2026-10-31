import csv
import re
from zeep import Client
from zeep.wsse.username import UsernameToken

USERNAME = "Base.com"
SECRET = "JfPciKxq"
WSDL_URL = "https://www.beautyfort.com/api/wsdl/v4/wsdl.wsdl"

# Priority 1: Top-selling model names for Nordic market
TOP_MODELS = [
    "BOSS BOTTLED", "THE SCENT", "HUGO MAN", "BOSS ALIVE", "BOSS FEMME", "HUGO DEEP RED", "BOSS ORANGE",
    "SAUVAGE", "FAHRENHEIT", "J'ADORE", "MISS DIOR",
    "BLACK OPIUM", "LIBRE", "YSL Y", "OPIUM",
    "ACQUA DI GIO", "STRONGER WITH YOU", "MY WAY", "SI",
    "1 MILLION", "ONE MILLION", "INVICTUS", "PHANTOM", "OLYMPEA",
    "BLEU DE CHANEL", "COCO MADEMOISELLE", "ALLURE",
    "MONTBLANC EXPLORER", "MONTBLANC LEGEND",
    "EROS", "DYLAN BLUE", "LIGHT BLUE", "K BY DOLCE",
    "HERO", "BURBERRY HER", "CK ONE", "ETERNITY", "EUPHORIA", "LÉ MALE", "DIVINE", "SCANDAL"
]

# Priority 2: General brand fallbacks
TARGET_BRANDS = [
    "HUGO BOSS", "BOSS", "DIOR", "CHANEL", "ARMANI", "GIORGIO ARMANI", 
    "YVES SAINT LAURENT", "YSL", "PACO RABANNE", "RABANNE", 
    "MONTBLANC", "VERSACE", "DOLCE & GABBANA", "BURBERRY", 
    "CALVIN KLEIN", "JEAN PAUL GAULTIER", "TOM FORD", "PRADA"
]

EXACT_TARGET_COUNT = 150
MIN_STOCK = 5

def clean_price(val):
    if not val:
        return ""
    return re.sub(r'[^0-9\.]', '', str(val).replace(',', '.'))

def clean_title(title_str):
    if not title_str:
        return ""
    unwanted_terms = [r'\bSpray\b', r'\bVaporisateur\b', r'\bVapo\b']
    cleaned = title_str
    for term in unwanted_terms:
        cleaned = re.sub(term, '', cleaned, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', cleaned).strip()

def fetch_beautyfort_soap_stock():
    print("Connecting to Beauty Fort SOAP client with WS-Security...")
    client = Client(WSDL_URL, wsse=UsernameToken(USERNAME, SECRET))
    
    # Get the factory to construct complex types required by the WSDL schema
    factory = client.type_factory('ns0')
    
    print("Calling GetStockFile with full schema parameters...")
    response = client.service.GetStockFile(
        TestMode=False,
        StockFileFormat='CSV',
        FieldDelimiter=;',
        StockFileFields=None, # Pulls default standard fields (SKU, name, stock, price, ean)
        SortBy='SKU',
        StockFileEncoding='UTF-8'
    )
    return response

raw_data = fetch_beautyfort_soap_stock()

top_sellers = []
brand_fallbacks = []

if raw_data:
    items = raw_data if isinstance(raw_data, list) else getattr(raw_data, 'item', [])
    
    for item in items:
        sku = str(getattr(item, 'sku', item.get('sku', '')))
        name = str(getattr(item, 'name', item.get('name', ''))).upper()
        stock = float(getattr(item, 'stock', item.get('stock', 0)))
        price = clean_price(getattr(item, 'price', item.get('price', '')))
        ean = str(getattr(item, 'ean', item.get('ean', '')))

        if stock < MIN_STOCK:
            continue

        product_dict = {
            'sku': sku,
            'name': clean_title(name),
            'stock': int(stock),
            'price': price,
            'ean': ean
        }

        if any(model in name for model in TOP_MODELS):
            top_sellers.append(product_dict)
        elif any(brand in name for brand in TARGET_BRANDS):
            brand_fallbacks.append(product_dict)

top_sellers.sort(key=lambda x: x['stock'], reverse=True)
brand_fallbacks.sort(key=lambda x: x['stock'], reverse=True)

final_selected = (top_sellers + brand_fallbacks)[:EXACT_TARGET_COUNT]

print(f"Matched {len(top_sellers)} top models and {len(brand_fallbacks)} brand fallbacks.")
print(f"Exporting top {len(final_selected)} items to beautyfort_filtered.csv...")

if final_selected:
    with open("beautyfort_filtered.csv", mode="w", newline="", encoding="utf-8") as outfile:
        fieldnames = ['sku', 'name', 'stock', 'price', 'ean']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(final_selected)
    print("beautyfort_filtered.csv successfully created!")
