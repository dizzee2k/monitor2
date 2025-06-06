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

        # --- Save HTML for debugging (can be commented out once stable) ---
        # try:
        #     product_id_for_filename = tcin
        #     safe_product_id_part = "".join(c if c.isalnum() or c in ['-', '_'] else '_' for c in product_id_for_filename)
        #     filename = f"debug_target_page_A-{safe_product_id_part}.html"
        #     with open(filename, "w", encoding="utf-8") as f:
        #         f.write(soup.prettify())
        # except Exception as e:
        #     print(f"DEBUG: Could not save HTML to file for {url}: {e}")
        # --- End Save HTML ---

        # --- HTML Check for Add to Cart Button ---
        # These are common data-test attributes. You might need to adjust them
        # by inspecting the HTML of an in-stock item.
        possible_atc_button_selectors = [
            {"data-test": "addToCartButton"},
            {"data-test": "shippingButton"} 
            # Add more selectors if Target uses others for the main purchase button
        ]
        
        found_active_atc_button_in_html = False
        atc_button_details = "No primary ATC button found in HTML"

        for selector in possible_atc_button_selectors:
            button = soup.find("button", attrs=selector)
            if button:
                selector_str = ", ".join([f"{k}='{v}'" for k,v in selector.items()])
                if 'disabled' in button.attrs:
                    atc_button_details = f"Button {selector_str} found but DISABLED in HTML."
                    print(f"DEBUG: TCIN {tcin} - {atc_button_details}")
                    # If a primary button is found and explicitly disabled, likely OOS for that method
                    # For now, we'll let JSON confirm, but this is a strong negative signal.
                else:
                    atc_button_details = f"Button {selector_str} found and ACTIVE in HTML."
                    print(f"DEBUG: TCIN {tcin} - {atc_button_details}")
                    found_active_atc_button_in_html = True
                    break # Found an active button
            # else:
                # print(f"DEBUG: TCIN {tcin} - Button with selector {selector} NOT found in HTML.")
        
        # If no active primary purchase button is found in the initial HTML,
        # it's a strong indicator of OOS, especially for shippable items.
        if not found_active_atc_button_in_html:
            print(f"DEBUG: TCIN {tcin} - No clearly active 'Add to Cart' or 'Shipping' button found in initial HTML. Details: {atc_button_details}. Marking OOS.")
            return False
        
        # --- JSON Verification (If HTML check passed) ---
        print(f"DEBUG: TCIN {tcin} - Active button found in HTML, proceeding to JSON verification.")
        script_tag = soup.find("script", string=lambda t: t and "__TGT_DATA__" in t)
        if not script_tag or not script_tag.string:
            print(f"DEBUG: TCIN {tcin} - __TGT_DATA__ script tag not found or empty. Marking as OOS despite HTML button.")
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
                    return False # Error during parsing
            else: # Should not happen if regex is correct and HTML structure is as expected
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
            print(f"DEBUG: Product data for TCIN {tcin} not found in __TGT_DATA__ JSON. Marking OOS.")
            return False

        # Pre-order Check
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

        # JSON based checks for shipping
        is_product_purchasable_json = product_data_from_json.get("purchasable")
        
        online_channel_eligible_json = False
        online_channel_reason_json = "UNKNOWN"
        purchasing_channels = product_data_from_json.get("item", {}).get("fulfillment", {}).get("purchasing_channel_eligibility", [])
        for channel_info in purchasing_channels:
            if isinstance(channel_info, dict) and channel_info.get("channel") == "ONLINE":
                online_channel_eligible_json = channel_info.get("is_eligible", False)
                online_channel_reason_json = str(channel_info.get("reason", "UNKNOWN")).upper()
                break
        
        shipping_options_data = product_data_from_json.get("item", {}).get("fulfillment", {}).get("shipping_options", {})
        if not isinstance(shipping_options_data, dict): shipping_options_data = {}
        shipping_order_limit_json = shipping_options_data.get("order_limit", -1)
        
        print(f"DEBUG: TCIN {tcin} - JSON - Purchasable: {is_product_purchasable_json}, OnlineChannelEligible: {online_channel_eligible_json}, OnlineChannelReason: '{online_channel_reason_json}', ShipLimit: {shipping_order_limit_json}")

        if is_product_purchasable_json is False:
            print(f"DEBUG: TCIN {tcin} - JSON 'purchasable' is False. Marking OOS.")
            return False

        positive_online_reasons = ["AVAILABLE", "IN_STOCK", "PREORDER_SELLABLE"]
        if online_channel_eligible_json and online_channel_reason_json in positive_online_reasons:
            if shipping_order_limit_json == 0:
                 print(f"DEBUG: TCIN {tcin} - JSON Online channel OK ('{online_channel_reason_json}') but shipping_order_limit is 0. Marking OOS.")
                 return False
            print(f"DEBUG: TCIN {tcin} - JSON Online channel eligible and reason '{online_channel_reason_json}' is positive. Marking IN STOCK.")
            return True
        
        print(f"DEBUG: TCIN {tcin} - JSON checks did not confirm shippable stock. OnlineChannelEligible: {online_channel_eligible_json} (Reason: '{online_channel_reason_json}'). Marking OOS.")
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

        # --- Save HTML for debugging (can be commented out once stable) ---
        # try:
        #     product_id_for_filename = tcin
        #     safe_product_id_part = "".join(c if c.isalnum() or c in ['-', '_'] else '_' for c in product_id_for_filename)
        #     filename = f"debug_target_page_A-{safe_product_id_part}.html"
        #     with open(filename, "w", encoding="utf-8") as f:
        #         f.write(soup.prettify())
        # except Exception as e:
        #     print(f"DEBUG: Could not save HTML to file for {url}: {e}")
        # --- End Save HTML ---

        # --- HTML Check for Add to Cart Button ---
        # These are common data-test attributes. You might need to adjust them
        # by inspecting the HTML of an in-stock item.
        possible_atc_button_selectors = [
            {"data-test": "addToCartButton"},
            {"data-test": "shippingButton"} 
            # Add more selectors if Target uses others for the main purchase button
        ]
        
        found_active_atc_button_in_html = False
        atc_button_details = "No primary ATC button found in HTML"

        for selector in possible_atc_button_selectors:
            button = soup.find("button", attrs=selector)
            if button:
                selector_str = ", ".join([f"{k}='{v}'" for k,v in selector.items()])
                if 'disabled' in button.attrs:
                    atc_button_details = f"Button {selector_str} found but DISABLED in HTML."
                    print(f"DEBUG: TCIN {tcin} - {atc_button_details}")
                    # If a primary button is found and explicitly disabled, likely OOS for that method
                    # For now, we'll let JSON confirm, but this is a strong negative signal.
                else:
                    atc_button_details = f"Button {selector_str} found and ACTIVE in HTML."
                    print(f"DEBUG: TCIN {tcin} - {atc_button_details}")
                    found_active_atc_button_in_html = True
                    break # Found an active button
            # else:
                # print(f"DEBUG: TCIN {tcin} - Button with selector {selector} NOT found in HTML.")
        
        # If no active primary purchase button is found in the initial HTML,
        # it's a strong indicator of OOS, especially for shippable items.
        if not found_active_atc_button_in_html:
            print(f"DEBUG: TCIN {tcin} - No clearly active 'Add to Cart' or 'Shipping' button found in initial HTML. Details: {atc_button_details}. Marking OOS.")
            return False
        
        # --- JSON Verification (If HTML check passed) ---
        print(f"DEBUG: TCIN {tcin} - Active button found in HTML, proceeding to JSON verification.")
        script_tag = soup.find("script", string=lambda t: t and "__TGT_DATA__" in t)
        if not script_tag or not script_tag.string:
            print(f"DEBUG: TCIN {tcin} - __TGT_DATA__ script tag not found or empty. Marking as OOS despite HTML button.")
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
                    return False # Error during parsing
            else: # Should not happen if regex is correct and HTML structure is as expected
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
            print(f"DEBUG: Product data for TCIN {tcin} not found in __TGT_DATA__ JSON. Marking OOS.")
            return False

        # Pre-order Check
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

        # JSON based checks for shipping
        is_product_purchasable_json = product_data_from_json.get("purchasable")
        
        online_channel_eligible_json = False
        online_channel_reason_json = "UNKNOWN"
        purchasing_channels = product_data_from_json.get("item", {}).get("fulfillment", {}).get("purchasing_channel_eligibility", [])
        for channel_info in purchasing_channels:
            if isinstance(channel_info, dict) and channel_info.get("channel") == "ONLINE":
                online_channel_eligible_json = channel_info.get("is_eligible", False)
                online_channel_reason_json = str(channel_info.get("reason", "UNKNOWN")).upper()
                break
        
        shipping_options_data = product_data_from_json.get("item", {}).get("fulfillment", {}).get("shipping_options", {})
        if not isinstance(shipping_options_data, dict): shipping_options_data = {}
        shipping_order_limit_json = shipping_options_data.get("order_limit", -1)
        
        print(f"DEBUG: TCIN {tcin} - JSON - Purchasable: {is_product_purchasable_json}, OnlineChannelEligible: {online_channel_eligible_json}, OnlineChannelReason: '{online_channel_reason_json}', ShipLimit: {shipping_order_limit_json}")

        if is_product_purchasable_json is False:
            print(f"DEBUG: TCIN {tcin} - JSON 'purchasable' is False. Marking OOS.")
            return False

        positive_online_reasons = ["AVAILABLE", "IN_STOCK", "PREORDER_SELLABLE"]
        if online_channel_eligible_json and online_channel_reason_json in positive_online_reasons:
            if shipping_order_limit_json == 0:
                 print(f"DEBUG: TCIN {tcin} - JSON Online channel OK ('{online_channel_reason_json}') but shipping_order_limit is 0. Marking OOS.")
                 return False
            print(f"DEBUG: TCIN {tcin} - JSON Online channel eligible and reason '{online_channel_reason_json}' is positive. Marking IN STOCK.")
            return True
        
        print(f"DEBUG: TCIN {tcin} - JSON checks did not confirm shippable stock. OnlineChannelEligible: {online_channel_eligible_json} (Reason: '{online_channel_reason_json}'). Marking OOS.")
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
