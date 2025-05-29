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
        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text()
        # Example: Look for "Buy now" button
        buy_now = soup.find("button", text="Buy now")
        out_of_stock = soup.find("div", class_="styles__AvailabilityMessage")
        return "Out of stock" not in page_text and ("Buy now" in page_text or "Qty 1" in page_text)
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
