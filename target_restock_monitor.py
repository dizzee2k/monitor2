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
        # Set up Chrome options for headless browsing
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.binary_location = "/app/.apt/usr/bin/google-chrome"

        # Set up ChromeDriver
        service = Service("/app/.chromedriver/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Load the page and wait for JavaScript to render
        driver.get(url)
        time.sleep(3)  # Wait for dynamic content to load
        
        # Parse the rendered page with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()
        
        # Find "Add to cart" button using id containing "addToCartButton"
        add_to_cart = soup.find("button", id=lambda x: x and "addToCartButton" in x)
        # Find "Out of stock" message by searching for a div with "out of stock" text
        out_of_stock = None
        for div in soup.find_all("div"):
            if div.text and "out of stock" in div.text.lower():
                out_of_stock = div
                break
        
        # Log details for debugging
        print(f"URL: {url}")
        print(f"Add to cart button: {add_to_cart.prettify() if add_to_cart else 'None'}")
        print(f"Out of stock message element: {out_of_stock.prettify() if out_of_stock else 'None'}")
        
        is_button_enabled = add_to_cart is not None and "disabled" not in add_to_cart.attrs
        is_out_of_stock = out_of_stock is not None
        
        print(f"Button enabled: {is_button_enabled}, Out of stock message: {is_out_of_stock}")
        return is_button_enabled and not is_out_of_stock
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
