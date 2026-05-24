import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ── Config from GitHub Secrets ─────────────────────────────────────────────────
URL                = "https://www.district.in/events/tata-ipl-2026-final-buy-tickets"
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM_NUMBER = os.environ["TWILIO_FROM_NUMBER"]
YOUR_MOBILE_NUMBER = os.environ["YOUR_MOBILE_NUMBER"]
LAST_STATE_FILE    = "last_state.txt"

COMING_SOON_KEYWORDS = ["coming soon", "notify me", "remind me", "not available", "sold out"]
BOOKABLE_KEYWORDS    = ["book ticket", "buy ticket", "book now", "buy now", "get ticket", "purchase"]

# ── Selenium browser setup ─────────────────────────────────────────────────────
def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    # Use chromium on GitHub Actions ubuntu
    import shutil
    chrome_bin = shutil.which("chromium-browser") or shutil.which("chromium") or shutil.which("google-chrome")
    if chrome_bin:
        options.binary_location = chrome_bin
    chromedriver_bin = shutil.which("chromedriver") or "/usr/lib/chromium-browser/chromedriver"
    driver = webdriver.Chrome(service=Service(chromedriver_bin), options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

# ── Fetch button state ─────────────────────────────────────────────────────────
def get_button_state() -> str:
    driver = get_driver()
    try:
        driver.get(URL)
        # Wait up to 10s for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(3)  # let JS render

        buttons = driver.find_elements(By.CSS_SELECTOR, "button, a")
        for btn in buttons:
            try:
                text = btn.text.strip().lower()
                if not text:
                    continue
                if any(k in text for k in COMING_SOON_KEYWORDS):
                    print(f"  Found coming-soon button: '{btn.text.strip()}'")
                    return btn.text.strip()
                if any(k in text for k in BOOKABLE_KEYWORDS):
                    print(f"  Found bookable button: '{btn.text.strip()}'")
                    return btn.text.strip()
            except Exception:
                continue

        print("  No matching button found — returning 'unknown'")
        return "unknown"

    except Exception as e:
        print(f"⚠️ Browser error: {e}")
        return "unknown"
    finally:
        driver.quit()

# ── Telegram ───────────────────────────────────────────────────────────────────
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }, timeout=10)
    if r.status_code == 200:
        print("✅ Telegram sent")
    else:
        print(f"❌ Telegram error: {r.text}")

# ── Twilio Call ────────────────────────────────────────────────────────────────
def make_call():
    from twilio.rest import Client
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    call = client.calls.create(
        to=YOUR_MOBILE_NUMBER,
        from_=TWILIO_FROM_NUMBER,
        twiml='<Response><Say voice="alice" language="en-IN">Alert! IPL Final tickets are now available on District. Book immediately!</Say><Pause length="1"/><Say voice="alice" language="en-IN">Go book now!</Say></Response>'
    )
    print(f"✅ Call initiated: {call.sid}")

# ── Alert ──────────────────────────────────────────────────────────────────────
def fire_alert(old_text: str, new_text: str):
    message = (
        "🚨 <b>IPL FINAL TICKETS ALERT!</b> 🚨\n\n"
        f"🔗 <a href='{URL}'>Book Now on District</a>\n\n"
        f"🔄 Button changed:\n"
        f"  <s>{old_text}</s>  →  <b>{new_text}</b>\n\n"
        "⚡ Go go go — book immediately!"
    )
    print(f"🚨 ALERT — '{old_text}' → '{new_text}'")
    send_telegram(message)
    make_call()

# ── State file ─────────────────────────────────────────────────────────────────
def load_last_state() -> str:
    try:
        with open(LAST_STATE_FILE, "r") as f:
            val = f.read().strip()
            return val if val else None
    except FileNotFoundError:
        return None

def save_state(state: str):
    with open(LAST_STATE_FILE, "w") as f:
        f.write(state)

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print(f"🎯 Checking → {URL}")

    current_state = get_button_state()
    print(f"🔘 Current: '{current_state}'")

    last_state = load_last_state()
    print(f"📌 Last:    '{last_state}'")

    if last_state is None:
        save_state(current_state)
        print(f"📌 First run — baseline saved: '{current_state}'")
        return

    if current_state.lower() == last_state.lower() or current_state == "unknown":
        print("✅ No change detected.")
        return

    print(f"🚨 CHANGE: '{last_state}' → '{current_state}'")
    fire_alert(last_state, current_state)
    save_state(current_state)

if __name__ == "__main__":
    main()
