import requests
from bs4 import BeautifulSoup
import time

# === CONFIG ===
PRODUCTS = {
    "Mystery Pokémon Item": "https://www.target.com/p/-/A-94336414",
    "Lego Minecraft": "https://www.target.com/p/lego-minecraft-the-lush-cave-fight-building-toy-30705/-/A-93104070#lnk=sametab",
    "April 2025 Special Collectible": "https://www.target.com/p/2025-pokemon-april-special-collectible-trading-cards/-/A-94411686?preselect=94411686",
    "SV 3.5 Booster Bundle Box": "https://www.target.com/p/pokemon-scarlet-violet-s3-5-booster-bundle-box/-/A-88897904?preselect=88897904"
}
import os
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
CHECK_INTERVAL = 300  # Every 5 minutes
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# Track which items we've already alerted on (avoid spam)
alerted_items = set()

def is_in_stock(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        soup = BeautifulSoup(response.text, "html.parser")

        add_to_cart = soup.find("button", {"data-test": "addToCartButton"})
        out_of_stock = soup.find("div", {"data-test": "notAvailableMessage"})

        # Log details for debugging
        print(f"Add to cart button: {add_to_cart}")
        print(f"Out of stock message element: {out_of_stock}")

        is_button_disabled = False
        if add_to_cart:
            is_button_disabled = add_to_cart.has_attr('disabled') or 'disabled' in add_to_cart.get('class', [])
        else:
            print("Add to cart button not found.")
            return False # If add to cart button is not found, assume it is out of stock

        is_out_of_stock = out_of_stock is not None

        print(f"Button disabled: {is_button_disabled}, Out of stock message: {is_out_of_stock}")

        return not is_button_disabled and not is_out_of_stock

    except requests.exceptions.RequestException as e:
        print(f"HTTP Error checking {url}: {e}")
        return False
    except Exception as e:
        print(f"Error checking {url}: {e}")
        return False

def send_discord_alert(product_name, url):
    data = {
        "content": f"🔔 **{product_name} is back in stock!**\n{url}",
        "username": "Pokemon Restock Bot"
    }
    response = requests.post(DISCORD_WEBHOOK_URL, json=data)
    print(f"✅ Alert sent for {product_name}: {response.status_code}")

def main():
    print("🛒 Starting Target product restock monitor...")
    while True:
        for name, url in PRODUCTS.items():
            try:
                print(f"🔍 Checking: {name}")
                if is_in_stock(url):
                    if name not in alerted_items:
                        print(f"✅ {name} IN STOCK! Sending alert...")
                        send_discord_alert(name, url)
                        alerted_items.add(name)
                    else:
                        print(f"ℹ️ {name} is in stock but already alerted.")
                else:
                    print(f"❌ {name} is out of stock.")
                    alerted_items.discard(name)  # Reset if it goes out of stock again
            except Exception as e:
                print(f"⚠️ Error checking {name}: {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
