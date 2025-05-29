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
    "DR Bundle": "https://www.target.com/p/pok--233-mon-trading-card-game--scarlet---38--violet--8212--destined-rivals-booster-bundle--no-aasa/-/A-94300067"
    "Crown Zenith Bundle": "https://www.target.com/p/pok--233-mon-trading-card-game--crown-zenith-booster-bundle-box--no-aasa/-/A-94091405"
    "Lego Minecraft": "https://www.target.com/p/lego-minecraft-the-lush-cave-fight-building-toy-30705/-/A-93104070#lnk=sametab",
    "April 2025 Zard Box": "https://www.target.com/p/2025-pokemon-april-special-collectible-trading-cards/-/A-94411686?preselect=94411686",
    "SV 3.5 151 Booster Bundle Box": "https://www.target.com/p/pokemon-scarlet-violet-s3-5-booster-bundle-box/-/A-88897904?preselect=88897904"
}

# For local testing, you can temporarily hardcode your webhook URL:
# DISCORD_WEBHOOK_URL = "YOUR_ACTUAL_DISCORD_WEBHOOK_URL_GOES_HERE"
# Otherwise, it will use the environment variable (good for Heroku)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

CHECK_INTERVAL = 30  # Every 30 seconds
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Track which items we've already alerted on (avoid spam)
alerted_items = set()

def get_tcin_from_url(url_string):
    """Extracts the TCIN (product ID, numbers only) from a Target URL."""
    try:
        path_segments = urlparse(url_string).path.strip("/").split("/")
        for segment in reversed(path_segments):
            # Target TCINs are usually prefixed with "A-" in the URL
            if segment.startswith("A-") and len(segment) > 2 and segment[2:].isdigit():
                return segment[2:] # Return only the numerical part
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
        try:
            parsed_url = urlparse(url)
            path_part = parsed_url.path.strip("/")
            product_id_for_filename = tcin # Use the extracted TCIN for a cleaner filename part
            
            # Sanitize the segment to make it a valid filename component
            safe_product_id_part = "".join(c if c.isalnum() or c in ['-', '_'] else '_' for c in product_id_for_filename)
            filename = f"debug_target_page_A-{safe_product_id_part}.html" # Prepend A- for consistency
            
            with open(filename, "w", encoding="utf-8") as f:
                f.write(soup.prettify())
            print(f"DEBUG: Full HTML content saved to: {filename}")
        except Exception as e:
            print(f"DEBUG: Could not save HTML to file for {url}: {e}")
        # --- End Save HTML ---

        script_tag = soup.find("script", string=lambda t: t and "__TGT_DATA__" in t)
        if not script_tag:
            print(f"DEBUG: __TGT_DATA__ script tag not found for {url}. Marking as OOS.")
            return False

        json_str = None
        if script_tag.string:
            content = script_tag.string
            # Corrected Regex: Looks for '__TGT_DATA__' (as a string literal) and then the JSON.parse call
            # This regex captures the string argument passed to JSON.parse()
            match = re.search(
                r"['\"]__TGT_DATA__['\"]\s*:\s*\{\s*configurable:\s*false,\s*enumerable:\s*true,\s*value:\s*deepFreeze\(JSON\.parse\((.*?)\)\),\s*writable:\s*false\s*\}",
                content,
                re.DOTALL
            )
            if match:
                json_arg_str = match.group(1).strip() # This is the argument to JSON.parse(), e.g., "\"{\\\"foo\\\": ...}\""
                
                # Remove outer quotes of the string literal and unescape
                if json_arg_str.startswith('"') and json_arg_str.endswith('"'):
                    json_str = json_arg_str[1:-1]
                elif json_arg_str.startswith("'") and json_arg_str.endswith("'"): # Handle single quotes too
                    json_str = json_arg_str[1:-1]
                else:
                    print(f"DEBUG: Captured JSON argument for __TGT_DATA__ is not correctly quoted: {json_arg_str[:100]}...")
                    return False # Cannot proceed if not properly quoted

                try:
                    # Python's json.loads can often handle strings with escaped characters directly
                    # if they are standard JSON escapes. The encode/decode unicode_escape is more robust.
                    json_str = json_str.encode('latin-1', 'backslashreplace').decode('unicode-escape')
                except Exception as e:
                    print(f"DEBUG: Error during unicode_escape of JSON string for {url}: {e}")
                    return False
            else:
                print(f"DEBUG: Could not regex parse the JSON block from __TGT_DATA__ for {url}.")
                # If regex fails, print a snippet of the script tag for manual inspection
                tgt_data_idx = content.find("'__TGT_DATA__'")
                if tgt_data_idx != -1:
                    print(f"DEBUG: Snippet around __TGT_DATA__ for {url}:\n{content[max(0, tgt_data_idx-100) : tgt_data_idx+400]}")
                return False
        
        if not json_str:
            print(f"DEBUG: Could not extract JSON string from __TGT_DATA__ for {url}. Marking as OOS.")
            return False

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"DEBUG: Failed to decode JSON from __TGT_DATA__ for {url}: {e}")
            print(f"DEBUG: JSON string snippet that failed (first 1000 chars): {json_str[:1000]}")
            return False

        product_data = None
        if data.get("__PRELOADED_QUERIES__") and data["__PRELOADED_QUERIES__"].get("queries"):
            for query_entry in data["__PRELOADED_QUERIES__"]["queries"]:
                if isinstance(query_entry, list) and len(query_entry) == 2:
                    query_details, query_result = query_entry[0], query_entry[1]
                    if isinstance(query_details, list) and len(query_details) == 2:
                        query_name, query_params = query_details[0], query_details[1]
                        if query_name == "@web/domain-product/get-pdp-v1" and isinstance(query_params, dict) and query_params.get("tcin") == tcin:
                            if query_result and query_result.get("data") and query_result["data"].get("product"):
                                product_data = query_result["data"]["product"]
                                break
        
        if not product_data:
            print(f"DEBUG: Product data for TCIN {tcin} not found in __TGT_DATA__ JSON for {url}. Marking as OOS.")
            return False

        # Check for pre-order street date
        street_date_str = product_data.get("item", {}).get("mmbv_content", {}).get("street_date")
        if street_date_str:
            try:
                street_date = datetime.strptime(street_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                current_date = datetime.now(timezone.utc)
                if street_date > current_date:
                    print(f"DEBUG: Item {tcin} is a pre-order (Street Date: {street_date_str}). Marking as OOS for now.")
                    return False
            except ValueError:
                print(f"DEBUG: Could not parse street_date: {street_date_str} for {tcin}")

        # Check eligibility rules for different fulfillment methods
        eligibility_rules = product_data.get("item", {}).get("eligibility_rules", {})
        
        ship_to_guest_active = eligibility_rules.get("ship_to_guest", {}).get("is_active", False)
        if ship_to_guest_active:
            print(f"DEBUG: Item {tcin} IS ELIGIBLE for ship_to_guest. Marking as IN STOCK.")
            return True

        opu_active = eligibility_rules.get("hold", {}).get("is_active", False) # 'hold' often means Order Pickup
        if opu_active:
            print(f"DEBUG: Item {tcin} IS ELIGIBLE for Order Pickup (hold.is_active). Marking as IN STOCK.")
            return True
            
        sdd_active = eligibility_rules.get("scheduled_delivery", {}).get("is_active", False) # Same Day Delivery
        if sdd_active:
            print(f"DEBUG: Item {tcin} IS ELIGIBLE for Scheduled Delivery. Marking as IN STOCK.")
            return True
            
        print(f"DEBUG: No clear IN_STOCK indicators in JSON eligibility_rules for TCIN {tcin}. ship_to_guest: {ship_to_guest_active}, opu_active (hold): {opu_active}, sdd_active: {sdd_active}. Marking as OOS.")
        return False

    except requests.exceptions.RequestException as e:
        print(f"Error checking {url}: RequestException - {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred in is_in_stock for {url}: {e}")
        # For more detailed error info during development:
        # import traceback
        # traceback.print_exc()
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
            
            time.sleep(3) # Slightly increased delay between product checks

        print(f"--- Loop finished, sleeping for {CHECK_INTERVAL} seconds ---")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    if not PRODUCTS:
        print("🚫 No products configured in the PRODUCTS dictionary. Exiting.")
    else:
        main()
