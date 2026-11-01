import json
import os
import requests

BASE_API_TOKEN = os.getenv("BASELINKER_API_TOKEN")
API_URL = "https://api.baselinker.com/connector.php"

# REPLACE THESE WITH YOUR ACTUAL INVENTORY IDs FROM BASE.COM
INVENTORY_ID_SE_DK = 12345     # Replace with your 'DCS Inventory' ID
INVENTORY_ID_DK_ONLY = 67890   # Replace with your 'DCS special for denmark' ID

def push_to_baselinker(inventory_id, json_file):
    if not os.path.exists(json_file):
        print(f"File {json_file} not found.")
        return

    with open(json_file, 'r', encoding='utf-8') as f:
        products = json.load(f)

    for item in products:
        images_dict = {}
        if item.get('image_url'):
            # Base.com requires the 'url:' prefix for external image links
            images_dict["0"] = f"url:{item['image_url']}"

        parameters = {
            "inventory_id": inventory_id,
            "sku": item['sku'],
            "text_fields": {
                "name": item['name']
            },
            "prices": {
                "0": item['price_sek']
            },
            "stock": {
                "bl_0": item['stock']
            },
            "images": images_dict
        }

        payload = {
            "token": BASE_API_TOKEN,
            "method": "addInventoryProduct",
            "parameters": json.dumps(parameters)
        }

        response = requests.post(API_URL, data=payload)
        res_data = response.json()
        
        if res_data.get("status") == "SUCCESS":
            print(f"Successfully added SKU: {item['sku']} with Image")
        else:
            print(f"❌ Error adding SKU {item['sku']}: {res_data.get('error_message')}")

if __name__ == '__main__':
    push_to_baselinker(INVENTORY_ID_SE_DK, 'dcs_filtered_se_dk.json')
    push_to_baselinker(INVENTORY_ID_DK_ONLY, 'dcs_filtered_dk_only.json')
