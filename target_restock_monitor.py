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
    Relies heavily on finding active (not disabled) purchase buttons.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15) # Increased timeout
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        soup = BeautifulSoup(response.text, "html.parser")

        # --- Debugging: You can uncomment this to save the page HTML if needed ---
        # with open(f"debug_page_{url.split('/')[-1]}.html", "w", encoding="utf-8") as f:
        #     f.write(soup.prettify())
        # print(f"DEBUG: Checking {url}, page title: {soup.title.string if soup.title else 'No title'}")
        # ---

        # Strategy:
        # 1. Look for explicit "Out of Stock" messages/blocks first.
        # 2. If not found, look for an active "Add to Cart", "Ship it", or "Pick it up" button.

        # 1. Check for common "Out of Stock" indicators
        # !!! USER ACTION: Verify this selector by inspecting an OOS page on Target !!!
        # Common `data-test` attribute for this is often 'soldOutBlock' or similar text content.
        sold_out_block_selector = {"data-test": "soldOutBlock"} # Example selector
        sold_out_block = soup.find(attrs=sold_out_block_selector)
        if sold_out_block:
            sold_out_text = sold_out_block.get_text(strip=True).lower()
            if "out of stock" in sold_out_text or "sold out" in sold_out_text or "unavailable" in sold_out_text:
                print(f"DEBUG: Confirmed OOS via element matching {sold_out_block_selector} for {url}")
                return False

        # 2. Look for "Add to Cart", "Ship it", or "Pick it up" buttons
        # !!! USER ACTION: Verify these `data-test` selectors by inspecting Target product pages !!!
        # The order matters: check the most likely/primary ones first.
        purchase_button_selectors = [
            {"data-test": "shippingButton"},   # Often for shippable items
            {"data-test": "addToCartButton"},  # Generic add to cart
            {"data-test": "pickUpButton"},     # For in-store pickup
            {"data-test": "scheduledPickupButton"} # Another pickup variant
        ]

        button_found_and_active = False
        for selector_attrs in purchase_button_selectors:
            selector_str = ", ".join([f"{k}='{v}'" for k, v in selector_attrs.items()])
            button = soup.find("button", attrs=selector_attrs) # Specifically look for <button> tags

            if button:
                print(f"DEBUG: Found button with selector {{{selector_str}}} for {url}.")
                if 'disabled' in button.attrs:
                    print(f"DEBUG: Button {{{selector_str}}} is DISABLED.")
                    # If this button is disabled, it doesn't indicate stock for THIS action.
                    # Continue to check other potential buttons.
                else:
                    print(f"DEBUG: Button {{{selector_str}}} is ACTIVE (not disabled). Item IN STOCK.")
                    button_found_and_active = True
                    break  # Found an active button, no need to check others for this product
            else:
                print(f"DEBUG: Button with selector {{{selector_str}}} NOT FOUND for {url}.")

        if button_found_and_active:
            return True

        # 3. Fallback: If no active purchase button was found, and no explicit soldOutBlock,
        #    check general page text as a last resort, but be cautious.
        #    This can be noisy. The absence of an active buy button is a strong indicator of OOS.
        page_text_lower = soup.get_text().lower()
        oos_keywords = ["out of stock", "currently unavailable", "sold out", "not available for shipping"]
        if any(keyword in page_text_lower for keyword in oos_keywords):
             # This is a broad check. If specific elements like buttons were not found or disabled,
             # and these general OOS keywords exist, it's likely OOS.
            print(f"DEBUG: General OOS keyword found in page text and no active buy button for {url}")
            return False
            
        print(f"DEBUG: No active purchase button found and no definitive OOS indicators for {url}. Assuming OOS to be safe.")
        return False # Default to False to avoid false positives if status is unclear

    except requests.exceptions.RequestException as e:
        print(f"Error checking {url}: RequestException - {e}")
        return False # Treat request errors as out of stock or unable to determine
    except Exception as e:
        print(f"An unexpected error occurred while checking {url}: {e}")
        return False

def send_discord_alert(product_name, url):
    """
    Sends an alert to the configured Discord webhook.
    """
    if not DISCORD_WEBHOOK_URL:
        print("🚨 DISCORD_WEBHOOK_URL is not set. Cannot send alert.")
        return

    data = {
        "content": f"🔔 **{product_name} is back in stock!**\n{url}",
        "username": "Target Restock Bot" # You can customize the bot's name
        # "avatar_url": "URL_TO_AN_IMAGE_FOR_THE_BOT" # Optional: add an avatar
    }
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=10)
        response.raise_for_status() # Raise an exception for HTTP errors
        print(f"✅ Alert sent for {product_name}: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"🚨 Failed to send Discord alert for {product_name}: {e}")
    except Exception as e:
        print(f"🚨 An unexpected error occurred while sending Discord alert: {e}")

def main():
    """
    Main loop to continuously check product stock.
    """
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ DISCORD_WEBHOOK_URL environment variable not found. Alerts will not be sent.")
        # Consider if the script should exit if the webhook URL is not set,
        # depending on how critical alerts are. For now, it continues.

    print("🛒 Starting Target product restock monitor...")
    print(f"Checking {len(PRODUCTS)} products every {CHECK_INTERVAL} seconds.")
    
    while True:
        for name, url in PRODUCTS.items():
            try:
                print(f"🔍 Checking: {name} ({url})")
                in_stock_status = is_in_stock(url) # Store result to avoid calling twice
                
                if in_stock_status:
                    if name not in alerted_items:
                        print(f"✅ {name} IN STOCK! Sending alert...")
                        send_discord_alert(name, url)
                        alerted_items.add(name) # Add to set after successful alert
                    else:
                        print(f"ℹ️ {name} is in stock but already alerted.")
                else:
                    print(f"❌ {name} is out of stock.")
                    # If it goes out of stock, remove it from alerted_items
                    # so it can be alerted again if it comes back in stock.
                    if name in alerted_items:
                        print(f"🗑️ Resetting alert status for {name} as it's now OOS.")
                        alerted_items.discard(name)
            except Exception as e:
                # Catch any unexpected errors during the check for a single product
                print(f"⚠️ An unexpected error occurred in main loop for {name}: {e}")
            
            time.sleep(2) # Small delay between checking different products to be polite to Target's server

        print(f"--- Loop finished, sleeping for {CHECK_INTERVAL} seconds ---")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    if not PRODUCTS:
        print("🚫 No products configured in the PRODUCTS dictionary. Exiting.")
    else:
        main()
