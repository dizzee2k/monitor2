import requests
from bs4 import BeautifulSoup
import time
import os
import json # <-- Add this import
from urllib.parse import urlparse # <-- Add this import

# === CONFIG ===
PRODUCTS = {
    "Mystery Pokémon Item": "https://www.target.com/p/-/A-94336414",
    "Lego Minecraft": "https://www.target.com/p/lego-minecraft-the-lush-cave-fight-building-toy-30705/-/A-93104070#lnk=sametab",
    "April 2025 Special Collectible": "https://www.target.com/p/2025-pokemon-april-special-collectible-trading-cards/-/A-94411686?preselect=94411686",
    "SV 3.5 Booster Bundle Box": "https://www.target.com/p/pokemon-scarlet-violet-s3-5-booster-bundle-box/-/A-88897904?preselect=88897904"
}

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") # Or your hardcoded URL for local testing
CHECK_INTERVAL = 300
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
alerted_items = set()

def get_tcin_from_url(url_string):
    """Extracts the TCIN (product ID, numbers only) from a Target URL."""
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
        response = requests.get(url, headers=HEADERS, timeout=20) # Increased timeout
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # --- Save HTML for debugging if needed (can be commented out once stable) ---
        try:
            parsed_url = urlparse(url)
            path_part = parsed_url.path.strip("/")
            product_id_segment = tcin # Use the extracted TCIN for a cleaner filename part
            
            safe_product_id_part = "".join(c if c.isalnum() or c in ['-', '_'] else '_' for c in product_id_segment)
            filename = f"debug_target_page_A-{safe_product_id_part}.html" # Prepend A- for consistency
            
            with open(filename, "w", encoding="utf-8") as f:
                f.write(soup.prettify())
            print(f"DEBUG: Full HTML content saved to: {filename}")
        except Exception as e:
            print(f"DEBUG: Could not save HTML to file for {url}: {e}")
        # --- End Save HTML ---

        # Find the __TGT_DATA__ script tag
        script_tag = soup.find("script", string=lambda t: t and "__TGT_DATA__" in t)
        if not script_tag:
            print(f"DEBUG: __TGT_DATA__ script tag not found for {url}. Marking as OOS.")
            return False

        # Extract the JSON string
        # The JSON is within JSON.parse("..."). We need to grab the content inside JSON.parse("...")
        json_str = None
        if script_tag.string:
            content = script_tag.string
            # Look for the start of the JSON string within JSON.parse("...")
            # This might need to be more robust if the structure varies slightly
            start_marker = 'JSON.parse("'
            end_marker = '"))),' # Assuming deepFreeze ends like this
            
            start_index = content.find(start_marker)
            if start_index != -1:
                start_index += len(start_marker)
                # Find the balancing end for JSON.parse("...") - this is tricky because the JSON string itself can have ");"
                # Let's find the specific end marker for __TGT_DATA__
                # 'value: deepFreeze(JSON.parse("..."))), writable: false }'
                # We need to find the end of the JSON string before the first closing parenthesis of JSON.parse()
                
                # A simpler way to find the JSON is to look for the structure around __PRELOADED_QUERIES__
                # Often it's like: value: deepFreeze(JSON.parse("{\"__PRELOADED_QUERIES__\":{...}}")),
                
                # Let's try to find the specific assignment part more reliably
                # This regex is an attempt, might need refinement
                import re
                match = re.search(r"__TGT_DATA__\s*:\s*\{\s*configurable:\s*false,\s*enumerable:\s*true,\s*value:\s*deepFreeze\(JSON\.parse\((.*?)\)\),\s*writable:\s*false\s*\}", content, re.DOTALL)
                if match:
                    json_str_with_quotes = match.group(1)
                    # The captured group includes the outer quotes of the string literal
                    if json_str_with_quotes.startswith('"') and json_str_with_quotes.endswith('"'):
                        json_str = json_str_with_quotes[1:-1]
                        # Unescape escaped characters like \\" -> \" and \n -> newline etc.
                        json_str = json_str.encode().decode('unicode_escape')
                    elif json_str_with_quotes.startswith("'") and json_str_with_quotes.endswith("'"):
                         json_str = json_str_with_quotes[1:-1]
                         json_str = json_str.encode().decode('unicode_escape') # May not be needed for single quotes
                else:
                    print(f"DEBUG: Could not regex parse the JSON block from __TGT_DATA__ for {url}.")


        if not json_str:
            print(f"DEBUG: Could not extract JSON string from __TGT_DATA__ for {url}. Marking as OOS.")
            return False
            
        # print(f"DEBUG: Extracted JSON string (first 500 chars): {json_str[:500]}")

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"DEBUG: Failed to decode JSON from __TGT_DATA__ for {url}: {e}")
            print(f"DEBUG: JSON string snippet that failed (first 1000 chars): {json_str[:1000]}")
            return False

        # Navigate through the JSON to find the product information
        # This path might change if Target updates their site structure.
        product_data = None
        if data.get("__PRELOADED_QUERIES__") and data["__PRELOADED_QUERIES__"].get("queries"):
            for query_entry in data["__PRELOADED_QUERIES__"]["queries"]:
                if isinstance(query_entry, list) and len(query_entry) == 2:
                    query_details = query_entry[0]
                    query_result = query_entry[1]
                    if isinstance(query_details, list) and len(query_details) == 2:
                        query_name = query_details[0]
                        query_params = query_details[1]
                        if query_name == "@web/domain-product/get-pdp-v1" and isinstance(query_params, dict) and query_params.get("tcin") == tcin:
                            if query_result and query_result.get("data") and query_result["data"].get("product"):
                                product_data = query_result["data"]["product"]
                                break
        
        if not product_data:
            print(f"DEBUG: Product data for TCIN {tcin} not found in __TGT_DATA__ JSON for {url}. Marking as OOS.")
            return False

        # Now check for availability within product_data
        # Option 1: Check street date for pre-orders (like the Pokemon Prismatic Box)
        street_date_str = product_data.get("item", {}).get("mmbv_content", {}).get("street_date")
        if street_date_str:
            from datetime import datetime, timezone
            try:
                street_date = datetime.strptime(street_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                # Ensure current_date is also timezone-aware (UTC) for proper comparison
                current_date = datetime.now(timezone.utc)
                if street_date > current_date:
                    print(f"DEBUG: Item {tcin} is a pre-order (Street Date: {street_date_str}). Marking as OOS for now.")
                    return False
            except ValueError:
                print(f"DEBUG: Could not parse street_date: {street_date_str} for {tcin}")

        # Option 2: Check eligibility rules (like for the Lego item)
        eligibility_rules = product_data.get("item", {}).get("eligibility_rules", {})
        
        # Check for shipping availability
        ship_to_guest = eligibility_rules.get("ship_to_guest", {}).get("is_active", False)
        if ship_to_guest:
            print(f"DEBUG: Item {tcin} IS ELIGIBLE for ship_to_guest. Marking as IN STOCK.")
            return True

        # Check for pickup availability (OPU - Order Pickup) via 'hold' eligibility
        # Note: Target's internal names for fulfillment can vary. 'hold' often refers to OPU.
        opu_available = eligibility_rules.get("hold", {}).get("is_active", False)
        if opu_available:
            print(f"DEBUG: Item {tcin} IS ELIGIBLE for Order Pickup (hold.is_active). Marking as IN STOCK.")
            return True
            
        # Check for Same Day Delivery (SDD)
        sdd_available = eligibility_rules.get("scheduled_delivery", {}).get("is_active", False)
        if sdd_available:
            print(f"DEBUG: Item {tcin} IS ELIGIBLE for Scheduled Delivery. Marking as IN STOCK.")
            return True
            
        # Fallback: If none of the above specific active flags are true, assume OOS from JSON perspective
        print(f"DEBUG: No clear IN_STOCK indicators in JSON eligibility_rules for TCIN {tcin} for {url}. ship_to_guest: {ship_to_guest}, opu_available (hold): {opu_available}, sdd_available: {sdd_available}. Marking as OOS.")
        return False

    except requests.exceptions.RequestException as e:
        print(f"Error checking {url}: RequestException - {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred in is_in_stock for {url}: {e}")
        # import traceback
        # traceback.print_exc() # Uncomment for detailed traceback during debugging
        return False

# (main and send_discord_alert functions remain the same)
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
            
            time.sleep(2) 

        print(f"--- Loop finished, sleeping for {CHECK_INTERVAL} seconds ---")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    if not PRODUCTS:
        print("🚫 No products configured in the PRODUCTS dictionary. Exiting.")
    else:
        main()
        main()
