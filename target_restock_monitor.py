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

# Ensure DISCORD_WEBHOOK_URL is set in your Heroku config vars
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
CHECK_INTERVAL = 300  # Every 5 minutes (300 seconds)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    # It's good practice to use a more common User-Agent
}

# Track which items we've already alerted on (avoid spam)
alerted_items = set()

def is_in_stock(url):
    """
    Checks if a product is in stock by fetching the page and looking for specific text.
    """
    try:
        # Make a GET request to the product URL
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        
        # Parse the HTML content of the page
        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text() # Get all the text from the page

        # Define keywords indicating out of stock and in stock
        # This logic might need adjustment if Target changes their website
        out_of_stock_keywords = ["out of stock", "sold out", "unavailable"]
        in_stock_keywords = ["add to cart", "buy now", "ship it", "pick it up", "qty"] # "Qty 1" is a bit specific, broader terms might be better

        # Check if any out-of-stock keyword is present
        is_oos = any(keyword in page_text.lower() for keyword in out_of_stock_keywords)
        if is_oos:
            return False

        # If not explicitly out of stock, check for in-stock indicators
        # This part is crucial and might need fine-tuning
        # For example, some sites might have "Add to Cart" but it's greyed out.
        # A more robust check would look for specific, active buttons or elements.
        is_instock = any(keyword in page_text.lower() for keyword in in_stock_keywords)
        
        # A more specific check for Target might involve looking for particular button elements
        # For example, finding a button with data-test="shippingButton" or similar.
        # This is more robust than generic text search but requires inspecting Target's HTML.
        # Example (conceptual, actual selectors will vary):
        # addToCartButton = soup.find("button", {"data-test": "addToCartButton"}) 
        # shippingButton = soup.find("button", {"data-test": "shippingButton"})
        # if addToCartButton or shippingButton:
        #    return True

        return is_instock # Returns True if an in-stock keyword is found and no out-of-stock keyword was found

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
        # You might want to exit here if the webhook URL is critical
        # return 

    print("🛒 Starting Target product restock monitor...")
    print(f"Checking {len(PRODUCTS)} products every {CHECK_INTERVAL} seconds.")
    
    while True:
        for name, url in PRODUCTS.items():
            try:
                print(f"🔍 Checking: {name} ({url})")
                if is_in_stock(url):
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
                        print(f"🗑️ Resetting alert status for {name}.")
                        alerted_items.discard(name)
            except Exception as e:
                # Catch any unexpected errors during the check for a single product
                print(f"⚠️ An unexpected error occurred in main loop for {name}: {e}")
            
            time.sleep(1) # Small delay between checking different products to be polite to the server

        print(f"--- Loop finished, sleeping for {CHECK_INTERVAL} seconds ---")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
