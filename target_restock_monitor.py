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
    Checks if a product is in stock. Includes saving full HTML for debugging selectors.
    """
    try:
        print(f"DEBUG: Fetching URL: {url}")
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # --- SAVE FULL HTML FOR DEBUGGING ---
        # >>> Try to run this script locally for this step to easily access the saved file. <<<
        try:
            # Create a somewhat unique filename based on the product URL
            product_id_part = url.strip("/").split("/")[-1] if url.strip("/").split("/") else "unknown_product"
            filename = f"debug_target_page_{product_id_part}.html"
            
            with open(filename, "w", encoding="utf-8") as f:
                f.write(soup.prettify()) # Save the "prettified" (formatted) HTML
            print(f"DEBUG: Full HTML content saved to: {filename}")
            print(f"DEBUG: Please open this file ('{filename}') in a browser and use 'Inspect Element' to find the correct selectors for buttons or stock status.")
        except Exception as e:
            # Fallback if file saving fails (e.g., on Heroku with restricted write access, though current dir should be writable)
            print(f"DEBUG: Could not save HTML to file ({filename}): {e}")
            print(f"DEBUG: Printing a much larger portion of HTML to logs instead (approx first 30000 chars). This might be truncated.")
            print(f"--- HTML START for {url} (approx 30000 chars) ---")
            print(soup.prettify()[:30000]) # Print more characters
            print(f"--- HTML END for {url} ---")
            print(f"DEBUG: If HTML in logs is truncated or hard to use, please try running this script locally to get the full HTML file.")
        # --- END SAVE HTML ---

        # At this point, you would have inspected the saved HTML file and found the correct selectors.
        # The selectors below are placeholders and LIKELY STILL INCORRECT for this product.
        # You MUST update them based on what you find in the 'debug_target_page_....html' file.

        # 1. Check for explicit "Out of Stock" blocks
        # !!! USER ACTION: Find the REAL selector in the saved HTML file !!!
        sold_out_block_selector = {"data-test": "SOME_REAL_SOLD_OUT_SELECTOR"} # Example: might be a class, id, or different data-test
        sold_out_block = soup.find(attrs=sold_out_block_selector)
        if sold_out_block:
            print(f"DEBUG: Found element matching potential OOS selector {sold_out_block_selector}.")
            # Add text check here if needed
            return False # Assuming if this block is found, it's OOS
        else:
            print(f"DEBUG: Element for OOS selector {sold_out_block_selector} NOT FOUND.")

        # 2. Look for purchase buttons
        # !!! USER ACTION: Find the REAL selectors in the saved HTML file !!!
        purchase_button_selectors = [
            # Example: {"id": "actualAddToCartButtonID"},
            # Example: {"class_": "some-button-class-name"}
            # Example: {"data-test": "REAL_BUTTON_SELECTOR_YOU_FOUND"}
            {"data-test": "this-is-still-a-placeholder-shippingButton"},
            {"data-test": "this-is-still-a-placeholder-addToCartButton"}
        ]

        button_found_and_active = False
        for selector_attrs in purchase_button_selectors:
            selector_str = ", ".join([f"{k}='{v}'" for k, v in selector_attrs.items()])
            # Ensure you're looking for the correct tag if it's not always a button (e.g. an <a> tag styled as a button)
            element_to_check = soup.find("button", attrs=selector_attrs) # Or soup.find(attrs=selector_attrs) if not sure of tag

            if element_to_check:
                print(f"DEBUG: Found element with selector {{{selector_str}}}.")
                # For buttons, check 'disabled'. For other elements, the logic might be different.
                if isinstance(element_to_check, type(soup.new_tag("button"))) and 'disabled' in element_to_check.attrs:
                    print(f"DEBUG: Element {{{selector_str}}} is a button and is DISABLED.")
                else:
                    # If it's not a button, or it's a button and not disabled, assume active for now
                    # You might need more specific checks here based on the element type
                    print(f"DEBUG: Element {{{selector_str}}} found and appears ACTIVE. Item IN STOCK.")
                    button_found_and_active = True
                    break 
            else:
                print(f"DEBUG: Element with selector {{{selector_str}}} NOT FOUND.")

        if button_found_and_active:
            return True
        
        print(f"DEBUG: No definitive in-stock indicators found using current selectors. Assuming OOS.")
        return False

    except requests.exceptions.RequestException as e:
        print(f"Error checking {url}: RequestException - {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while checking {url}: {e}")
        return False
            
        print(f"DEBUG: No active primary purchase button found and no definitive OOS indicators for {url}. Assuming OOS to be safe.")
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
