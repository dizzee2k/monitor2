import requests
from bs4 import BeautifulSoup
import time
import os
import json # For parsing JSON data
import re   # For regular expressions
from urllib.parse import urlparse # For parsing URLs and robust filename generation
from datetime import datetime, timezone # For checking pre-order street dates

# === CONFIG ===
PRODUCTS = {
    "Prismatic Mystery": "https://www.target.com/p/-/A-94336414",
    "Surging Sparks Booster Box": "https://www.target.com/p/pok--233-mon-scarlet-violet-surging-sparks-booster-trading-cards/-/A-93486336",
    "Destined Rivals 3 Pack": "https://www.target.com/p/pok--233-mon-trading-card-game--scarlet---38--violet--8212--destined-rivals-three-booster-blister-zebstrika/-/A-94300073",
    "Prismatic Sticker Collection": "https://www.target.com/p/2025-pokemon-prismatic-evolutions-tech-sticker-collection-dw-sylveon/-/A-94300058",
    "Prismatic ETB": "https://www.target.com/p/pok--233-mon-trading-card-game--scarlet---38--violet--8212-prismatic-evolutions-elite-trainer-box--no-aasa/-/A-93954435",
    "Prismatic Poster Collection": "https://www.target.com/p/pok--233-mon-trading-card-game--scarlet---38--violet--8212-prismatic-evolutions-poster-collection--no-aasa/-/A-93803457",
    "Prismatic Bundle": "https://www.target.com/p/pok--233-mon-trading-card-game--scarlet---38--violet--8212-prismatic-evolutions-booster-bundle--no-aasa/-/A-93954446",
    "Prismatic SPC": "https://www.target.com/p/pok--233-mon-trading-card-game--scarlet---38--violet--8212-prismatic-evolutions-super-premium-collection--no-aasa/-/A-94300072",
    "Prismatic Binder": "https://www.target.com/p/pok--233-mon-trading-card-game--scarlet---38--violet--8212-prismatic-evolutions-binder-collection--no-aasa/-/A-94300066",
    "DR Bundle": "https://www.target.com/p/pok--233-mon-trading-card-game--scarlet---38--violet--8212--destined-rivals-booster-bundle--no-aasa/-/A-94300067",
    "Crown Zenith Bundle": "https://www.target.com/p/pok--233-mon-trading-card-game--crown-zenith-booster-bundle-box--no-aasa/-/A-94091405",
    "Lego Minecraft": "https://www.target.com/p/lego-minecraft-the-lush-cave-fight-building-toy-30705/-/A-93104070#lnk=sametab",
    "April 2025 Zard Box": "https://www.target.com/p/2025-pokemon-april-special-collectible-trading-cards/-/A-94411686?preselect=94411686",
    "SV 3.5 151 Booster Bundle Box": "https://www.target.com/p/pokemon-scarlet-violet-s3-5-booster-bundle-box/-/A-88897904?preselect=88897904"
}

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
CHECK_INTERVAL = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
alerted_items = set()

def get_tcin_from_url(url_string):
    try:
        path_segments = urlparse(url_string).path.strip("/").split("/")
        for segment in reversed(path_segments):
            if segment.startswith("A-") and len(segment) > 2 and segment[2:].isdigit():
                return segment[2:]
    except Exception as e:
        print(f"DEBUG: Error extracting TCIN from URL {url_string}: {e}")
    return None

def is_in_stock(url):
    tcin = get_tcin_from_url(url)
    if not tcin:
        print(f"DEBUG: Could not extract TCIN for URL: {url}. Marking as OOS.")
        return False
    print(f"DEBUG: Extracted TCIN {tcin} for URL {url}")

    try:
        print(f"DEBUG: Fetching URL: {url}")
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        try:
            product_id_for_filename = tcin
            safe_product_id_part = "".join(c if c.isalnum() or c in ['-', '_'] else '_' for c in product_id_for_filename)
            filename = f"debug_target_page_A-{safe_product_id_part}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(soup.prettify())
        except Exception as e:
            print(f"DEBUG: Could not save HTML to file for {url}: {e}")

        script_tag = soup.find("script", string=lambda t: t and "__TGT_DATA__" in t)
        if not script_tag or not script_tag.string:
            print(f"DEBUG: __TGT_DATA__ script tag not found or empty for {url}. Marking as OOS.")
            return False

        content = script_tag.string
        json_str = None
        match = re.search(
            r"['\"]__TGT_DATA__['\"]\s*:\s*\{\s*configurable:\s*false,\s*enumerable:\s*true,\s*value:\s*deepFreeze\(JSON\.parse\((.*?)\)\),\s*writable:\s*false\s*\}",
            content, re.DOTALL
        )
        if match:
            json_arg_str = match.group(1).strip()
            if (json_arg_str.startswith('"') and json_arg_str.endswith('"')) or \
               (json_arg_str.startswith("'") and json_arg_str.endswith("'")):
                json_str = json_arg_str[1:-1]
                try:
                    json_str = json_str.encode('latin-1', 'backslashreplace').decode('unicode-escape')
                except Exception as e:
                    print(f"DEBUG: Error during unicode_escape of JSON string for {url}: {e}")
                    return False
            else:
                print(f"DEBUG: Captured JSON argument for __TGT_DATA__ is not correctly quoted: {json_arg_str[:100]}...")
                return False
        else:
            print(f"DEBUG: Could not regex parse the JSON block from __TGT_DATA__ for {url}.")
            return False
        
        if not json_str:
            print(f"DEBUG: Could not extract JSON string from __TGT_DATA__ for {url}. Marking as OOS.")
            return False

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"DEBUG: Failed to decode JSON from __TGT_DATA__ for {url}: {e}. Snippet: {json_str[:1000]}")
            return False

        product_data_from_json = None
        if data.get("__PRELOADED_QUERIES__") and data["__PRELOADED_QUERIES__"].get("queries"):
            for query_entry in data["__PRELOADED_QUERIES__"]["queries"]:
                if isinstance(query_entry, list) and len(query_entry) == 2:
                    query_details, query_result = query_entry[0], query_entry[1]
                    if isinstance(query_details, list) and len(query_details) == 2:
                        query_name, query_params = query_details[0], query_details[1]
                        if query_name == "@web/domain-product/get-pdp-v1" and isinstance(query_params, dict) and query_params.get("tcin") == tcin:
                            if query_result and query_result.get("data") and query_result["data"].get("product"):
                                product_data_from_json = query_result["data"]["product"]
                                break
        
        if not product_data_from_json:
            print(f"DEBUG: Product data for TCIN {tcin} not found in __TGT_DATA__ JSON for {url}. Marking as OOS.")
            return False
        
        # print(f"DEBUG: Full product_data_from_json for TCIN {tcin}: {json.dumps(product_data_from_json, indent=2)}")


        # Check for pre-order street date
        street_date_str = product_data_from_json.get("item", {}).get("mmbv_content", {}).get("street_date")
        if street_date_str:
            try:
                street_date = datetime.strptime(street_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                current_date = datetime.now(timezone.utc)
                if street_date > current_date:
                    print(f"DEBUG: TCIN {tcin} - Pre-order (Street Date: {street_date_str}). Marking OOS.")
                    return False
            except ValueError:
                print(f"DEBUG: TCIN {tcin} - Could not parse street_date: {street_date_str}")

        # General purchasability flag from the root of product data.
        # We will use this as a secondary check. If it's explicitly False, it's a strong OOS signal.
        is_generally_purchasable = product_data_from_json.get("purchasable") # Get actual value, could be True, False, or None
        print(f"DEBUG: TCIN {tcin} - Top-level 'purchasable' flag: {is_generally_purchasable}")

        # Extract specific shipping options data
        shipping_options_data = {}
        # Path 1: product.item.fulfillment.shipping_options
        item_fulfillment = product_data_from_json.get("item", {}).get("fulfillment", {})
        if isinstance(item_fulfillment, dict):
            shipping_options_data = item_fulfillment.get("shipping_options", {})
        
        # Path 2: product.fulfillment.shipping_options (if not found or empty in path 1)
        if not shipping_options_data or not isinstance(shipping_options_data, dict):
            root_fulfillment = product_data_from_json.get("fulfillment", {})
            if isinstance(root_fulfillment, dict):
                shipping_options_data = root_fulfillment.get("shipping_options", {})
        
        # Ensure shipping_options_data is a dict for safe access
        if not isinstance(shipping_options_data, dict):
            shipping_options_data = {}
            print(f"DEBUG: TCIN {tcin} - shipping_options_data is not a dict after checking paths. Final value: {shipping_options_data}")

        specific_shipping_status = str(shipping_options_data.get("availability_status", "UNKNOWN")).upper()
        shipping_order_limit = shipping_options_data.get("order_limit", -1)
        
        print(f"DEBUG: TCIN {tcin} - SpecificShippingStatus: '{specific_shipping_status}', ShipLimit: {shipping_order_limit}")

        # Primary Condition: Explicitly IN_STOCK or PREORDER_SELLABLE from specific shipping_options
        if specific_shipping_status == "IN_STOCK" or specific_shipping_status == "PREORDER_SELLABLE":
            if shipping_order_limit == 0: 
                print(f"DEBUG: TCIN {tcin} - Specific shipping '{specific_shipping_status}' but limit 0. Marking OOS.")
                return False
            # Even if specific status is IN_STOCK, if top-level purchasable is explicitly False, be cautious.
            if is_generally_purchasable is False:
                 print(f"DEBUG: TCIN {tcin} - Specific shipping '{specific_shipping_status}', but top-level 'purchasable' is False. Marking OOS.")
                 return False
            print(f"DEBUG: TCIN {tcin} - Specific shipping '{specific_shipping_status}'. Marking IN STOCK.")
            return True
        
        # If specific_shipping_status is not clearly "IN_STOCK" or "PREORDER_SELLABLE"
        # Check if the item is explicitly marked as not purchasable at the top level.
        if is_generally_purchasable is False:
            print(f"DEBUG: TCIN {tcin} - Specific shipping status is '{specific_shipping_status}' AND top-level 'purchasable' is False. Marking OOS.")
            return False

        # Fallback for UNKNOWN specific status, if other indicators are positive
        # This is more of a last resort and can be risky for false positives.
        # For now, if specific_shipping_status is not IN_STOCK/PREORDER_SELLABLE, consider it OOS.
        print(f"DEBUG: TCIN {tcin} - Specific shipping_status ('{specific_shipping_status}') is not IN_STOCK/PREORDER_SELLABLE. Top-level purchasable: {is_generally_purchasable}. Marking OOS.")
        return False

    except requests.exceptions.RequestException as e:
        print(f"Error checking {url}: RequestException - {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred in is_in_stock for {url}: {e}")
        import traceback
        traceback.print_exc() 
        return False

def send_discord_alert(product_name, url):
    if not DISCORD_WEBHOOK_URL:
        print("🚨 DISCORD_WEBHOOK_URL is not set. Cannot send alert.")
        return
    data = {
        "content": f"🔔 **{product_name} is back in stock!**\n{url}",
        "username": "Target Restock Bot"
    }
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=10)
        response.raise_for_status()
        print(f"✅ Alert sent for {product_name}: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"🚨 Failed to send Discord alert for {product_name}: {e}")
    except Exception as e:
        print(f"🚨 An unexpected error occurred while sending Discord alert: {e}")

def main():
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ DISCORD_WEBHOOK_URL environment variable not found. Alerts will not be sent.")

    print("🛒 Starting Target product restock monitor...")
    print(f"Checking {len(PRODUCTS)} products every {CHECK_INTERVAL} seconds.")
    
    while True:
        for name, url in PRODUCTS.items():
            try:
                print(f"🔍 Checking: {name} ({url})")
                in_stock_status = is_in_stock(url)
                
                if in_stock_status:
                    if name not in alerted_items:
                        print(f"✅ {name} IN STOCK! Sending alert...")
                        send_discord_alert(name, url)
                        alerted_items.add(name)
                    else:
                        print(f"ℹ️ {name} is in stock but already alerted.")
                else:
                    print(f"❌ {name} is out of stock.")
                    if name in alerted_items:
                        print(f"🗑️ Resetting alert status for {name} as it's now OOS.")
                        alerted_items.discard(name)
            except Exception as e:
                print(f"⚠️ An unexpected error occurred in main loop for {name}: {e}")
            
            time.sleep(3) 

        print(f"--- Loop finished, sleeping for {CHECK_INTERVAL} seconds ---")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    if not PRODUCTS:
        print("🚫 No products configured in the PRODUCTS dictionary. Exiting.")
    else:
        main()
