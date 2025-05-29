import requests
from bs4 import BeautifulSoup
import time
import os

# === CONFIG ===
PRODUCTS = {
    "Mystery Pokémon Item": "https://www.target.com/p/-/A-94336414",
    "Lego Minecraft": "https://www.target.com/p/lego-minecraft-the-lush-cave-fight-building-toy-30705/-/A-93104070#lnk=sametab",
    "April 2025 Special Collectible": "https://www.target.com/p/2025-pokemon-april-special-collectible-trading-cards/-/A-94411686?preselect=94411686",
    "SV 3.5 Booster Bundle Box": "https://www.target.com/p/pokemon-scarlet-violet-s3-5-booster-bundle-box/-/A-88897904?preselect=88897904"
}

# Ensure DISCORD_WEBHOOK_URL is set in your Heroku config vars or environment variables
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
CHECK_INTERVAL = 300  # Every 5 minutes (300 seconds)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Track which items we've already alerted on (avoid spam)
alerted_items = set()

def is_in_stock(url):
    """
    Checks if a product is in stock by looking for specific HTML elements and attributes.
    Focuses on the 'data-test="shippingButton"' as per user finding.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # print(f"DEBUG: Checking {url}, page title: {soup.title.string if soup.title else 'No title'}")

        # 1. Check for explicit "Out of Stock" blocks first.
        # !!! USER ACTION: Verify this selector by inspecting an OOS page on Target !!!
        sold_out_block_selector = {"data-test": "soldOutBlock"} # Example selector
        sold_out_block = soup.find(attrs=sold_out_block_selector)
        if sold_out_block:
            sold_out_text = sold_out_block.get_text(strip=True).lower()
            if "out of stock" in sold_out_text or "sold out" in sold_out_text or "unavailable" in sold_out_text:
                print(f"DEBUG: Confirmed OOS via element matching {sold_out_block_selector} for {url}")
                return False

        # 2. Look for the specific purchase button(s) identified.
        # Focusing on "shippingButton" as requested.
        # Ensure this selector corresponds to a button that, when active (not disabled),
        # truly means the item is available for purchase and shipping.
        purchase_button_selectors = [
            {"data-test": "shippingButton"},
            # {"data-test": "addToCartButton"},  # Keep others commented for this focused test
            # {"data-test": "pickUpButton"},
            # {"data-test": "scheduledPickupButton"}
        ]

        button_found_and_active = False
        for selector_attrs in purchase_button_selectors:
            selector_str = ", ".join([f"{k}='{v}'" for k, v in selector_attrs.items()])
            button = soup.find("button", attrs=selector_attrs)

            if button:
                print(f"DEBUG: Found button with selector {{{selector_str}}} for {url}.")
                if 'disabled' in button.attrs:
                    print(f"DEBUG: Button {{{selector_str}}} is DISABLED.")
                else:
                    print(f"DEBUG: Button {{{selector_str}}} is ACTIVE (not disabled). Item IN STOCK.")
                    button_found_and_active = True
                    break 
            else:
                print(f"DEBUG: Button with selector {{{selector_str}}} NOT FOUND for {url}.")

        if button_found_and_active:
            return True
        
        # If the specific button wasn't found or wasn't active:
        # Check if there's a main "Add to Cart" button as a fallback (verify its data-test attribute)
        # This is an example, you'd need to find the correct data-test for Target's main add to cart button
        main_add_to_cart_selector = {"data-test": "addToCartButton"} # Or whatever it truly is
        main_add_to_cart_button = soup.find("button", attrs=main_add_to_cart_selector)
        if main_add_to_cart_button:
            selector_str = ", ".join([f"{k}='{v}'" for k, v in main_add_to_cart_selector.items()])
            print(f"DEBUG: Found fallback button with selector {{{selector_str}}} for {url}.")
            if 'disabled' not in main_add_to_cart_button.attrs:
                print(f"DEBUG: Fallback button {{{selector_str}}} is ACTIVE. Item IN STOCK.")
                return True
            else:
                print(f"DEBUG: Fallback button {{{selector_str}}} is DISABLED.")


        page_text_lower = soup.get_text().lower()
        oos_keywords = ["out of stock", "currently unavailable", "sold out", "not available for shipping"]
        if any(keyword in page_text_lower for keyword in oos_keywords):
            print(f"DEBUG: General OOS keyword found in page text and no active buy button for {url}")
            return False
            
        print(f"DEBUG: No active primary purchase button (e.g., shippingButton) found and no definitive OOS indicators for {url}. Assuming OOS to be safe.")
        return False

    except requests.exceptions.RequestException as e:
        print(f"Error checking {url}: RequestException - {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while checking {url}: {e}")
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
            
            time.sleep(2) 

        print(f"--- Loop finished, sleeping for {CHECK_INTERVAL} seconds ---")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    if not PRODUCTS:
        print("🚫 No products configured in the PRODUCTS dictionary. Exiting.")
    else:
        main()
    if not PRODUCTS:
        print("🚫 No products configured in the PRODUCTS dictionary. Exiting.")
    else:
        main()
