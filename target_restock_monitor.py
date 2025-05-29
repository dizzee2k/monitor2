import requests
from bs4 import BeautifulSoup
import time

# === CONFIG ===
PRODUCTS = {
    "Mystery Pokémon Item": "https://www.target.com/p/-/A-94336414",
    "April 2025 Special Collectible": "https://www.target.com/p/2025-pokemon-april-special-collectible-trading-cards/-/A-94411686?preselect=94411686",
    "SV 3.5 Booster Bundle Box": "https://www.target.com/p/pokemon-scarlet-violet-s3-5-booster-bundle-box/-/A-88897904?preselect=88897904"
}
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1377565409020219433/QKtODI2sxXxenbTjjtsLKQCAd6zUfW-sMeoYWDuBNItMZ0p-z8lIZDJ4dR0GrC861xdo"
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
        return "Out of stock" not in page_text and ("Add to cart" in page_text or "Ship it" in page_text)
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
