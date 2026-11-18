import sys
import os
import json
import time
import requests
from camoufox.sync_api import Camoufox

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "DUMMY_TELEGRAM_TOKEN_PROTECTED")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1936436999")
X_USERNAME = os.getenv("X_USERNAME", "Pulup302")
X_PASSWORD = os.getenv("X_PASSWORD", "ciroxtreme0703")
SESSION_FILE = "session_x.json"

def send_telegram(text):
    print(f"[TELEGRAM] {text}")
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)
    except Exception as e:
        print(f"[ERR] Failed to send telegram text: {e}")

def send_telegram_photo(photo_path, caption=""):
    print(f"[TELEGRAM PHOTO] {photo_path} - {caption}")
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        with open(photo_path, "rb") as f:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, files={"photo": f}, timeout=20)
    except Exception as e:
        print(f"[ERR] Failed to send photo: {e}")

def login_and_search(query="Barca"):
    send_telegram(f"🐦 [X Runner] Memulai eksekusi X Engine untuk query: '{query}'...")
    
    # Run Camoufox with direct IP (GitHub Actions runner datacenter IP is accepted by X web)
    with Camoufox(headless=True, i_know_what_im_doing=True) as browser:
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        
        # Load existing cookies if any
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r") as f:
                    cookies = json.load(f)
                    context.add_cookies(cookies)
                    print(f"Loaded {len(cookies)} cookies from {SESSION_FILE}")
            except Exception as e:
                print(f"Failed to load cookies: {e}")

        page = context.new_page()
        
        # 1. Check if already logged in by opening home
        print("Checking session status on x.com/home...")
        try:
            page.goto("https://x.com/home", timeout=45000, wait_until="domcontentloaded")
            time.sleep(5)
        except Exception as e:
            print(f"Navigation warning: {e}")
        
        # Check if login required
        if "/i/flow/login" in page.url or page.locator("text='Sign in to X'").count() > 0 or page.locator("a[href='/login']").count() > 0 or "login" in page.url:
            print("Session not active or cookies expired. Starting login flow...")
            send_telegram("🔑 Melakukan login otomatis akun Pulup302...")
            page.goto("https://x.com/i/flow/login", timeout=45000, wait_until="domcontentloaded")
            time.sleep(6)
            page.screenshot(path="login_step1.png")
            
            # Input Username
            username_input = page.locator("input[autocomplete='username'], input[name='text']").first
            if username_input.count() > 0:
                print("Entering username...")
                username_input.fill(X_USERNAME)
                time.sleep(1)
                # Click next
                next_btn = page.locator("button:has-text('Next'), role=button[name='Next']").first
                if next_btn.count() > 0:
                    next_btn.click()
                else:
                    page.keyboard.press("Enter")
                time.sleep(4)
                
                # Check for unusual activity / email prompt
                if page.locator("input[data-testid='ocfEnterTextTextInput']").count() > 0 or "phone or username" in page.content().lower():
                    print("Twitter requested verification identifier...")
                    page.locator("input[data-testid='ocfEnterTextTextInput']").first.fill(X_USERNAME)
                    time.sleep(1)
                    page.keyboard.press("Enter")
                    time.sleep(4)
                
                # Input Password
                password_input = page.locator("input[name='password'], input[type='password']").first
                if password_input.count() > 0:
                    print("Entering password...")
                    password_input.fill(X_PASSWORD)
                    time.sleep(1)
                    login_btn = page.locator("button:has-text('Log in'), role=button[name='Log in']").first
                    if login_btn.count() > 0:
                        login_btn.click()
                    else:
                        page.keyboard.press("Enter")
                    time.sleep(8)
                else:
                    print("Password field not found!")
                    page.screenshot(path="no_password.png")
                    send_telegram_photo("no_password.png", "⚠️ Kolom password tidak ditemukan")
            else:
                print("Username field not found!")
                page.screenshot(path="no_username.png")
                send_telegram_photo("no_username.png", "⚠️ Kolom username tidak ditemukan")
            
            # Save cookies after login
            cookies = context.cookies()
            with open(SESSION_FILE, "w") as f:
                json.dump(cookies, f, indent=2)
            print(f"Saved {len(cookies)} cookies to {SESSION_FILE}")
            page.screenshot(path="logged_in.png")
            send_telegram_photo("logged_in.png", "✅ Status Login X.com")
        else:
            print("Already logged in with existing session!")

        # 2. Execute Search with Latest filter (f=live)
        search_url = f"https://x.com/search?q={query}&f=live"
        print(f"Navigating to search URL: {search_url}")
        page.goto(search_url, timeout=45000, wait_until="domcontentloaded")
        time.sleep(6)
        
        # Take screenshot of live search results
        page.screenshot(path="search_live.png")
        
        # Scrape tweets
        tweet_elements = page.locator("article[data-testid='tweet']").all()
        print(f"Found {len(tweet_elements)} tweets on page!")
        
        results = []
        for i, el in enumerate(tweet_elements[:7]):
            try:
                text_content = el.locator("div[data-testid='tweetText']").first.inner_text()
            except Exception:
                text_content = "(Media/No text)"
            try:
                user_info = el.locator("div[data-testid='User-Name']").first.inner_text().replace("\n", " ")
            except Exception:
                user_info = "Unknown User"
            
            tweet_text = f"👤 {user_info}\n💬 {text_content}"
            results.append(tweet_text)
        
        # Format report message
        if results:
            report = f"🔥 Postingan Terbaru di X untuk '{query}' (Live):\n\n" + "\n\n───────────────────\n\n".join(results)
            send_telegram(report)
            send_telegram_photo("search_live.png", f"📸 Bukti Live Search X untuk: {query}")
        else:
            send_telegram(f"⚠️ Tidak ditemukan tweet untuk query '{query}', cek screenshot terlampir.")
            send_telegram_photo("search_live.png", f"Live Search Result: {query}")

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else "Barca"
    login_and_search(q)
