from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import requests

# === CONFIG ===
PRODUCTS = {
    "Mystery Pokémon Item": "https://www.target.com/p/-/A-94336414",
    "Lego Minecraft": "https://www.target.com/p/lego-minecraft-the-lush-cave-fight-building-toy-30705/-/A-93104070#lnk=sametab",
    "April 2025 Special Collectible": "https://www.target.com/p/2025-pokemon-april-special-collectible-trading-cards/-/A-94411686?preselect=94411686",
    "SV 3.5 Booster Bundle Box": "https://www.target.com/p/pokemon-scarlet-violet-s3-5-booster-bundle-box/-/A-88897904?preselect=88897904"
}
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
CHECK_INTERVAL = 300  # Every 5 minutes

# Set up Selenium WebDriver for Heroku
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run in headless mode (no GUI)
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.binary_location = "/app/.apt/usr/lib/chromium-browser/chrome"  # Path to Chrome on Heroku

# Path to ChromeDriver installed by the buildpack
service = Service("/app/.chromedriver/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=chrome_options)

# Track which items we've already alerted on (avoid spam)
alerted_items = set()

def is_in_stock(url):
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        # Check for "Add to cart" button or "Qty 1" element as stock indicators
        add_to_cart = driver.find_elements(By.XPATH, "//button[contains(text(), 'Add to cart')]")
        qty_1 = driver.find_elements(By.XPATH, "//span[contains(text(), 'Qty 1')]")
        out_of_stock = driver.find_elements(By.XPATH, "//*[contains(text(), 'Out of stock')]")
        return (len(add_to_cart) > 0 or len(qty_1) > 0) and len(out_of_stock) == 0
    except Exception as e:
        print(f"Error checking {url}: {e}")
        return False
    finally:
        # Add a small delay to avoid overwhelming the site
        time.sleep(2)

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
    try:
        main()
    finally:
        driver.quit()  # Clean up the WebDriver
