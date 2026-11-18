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
    
    with Camoufox(headless=True, i_know_what_im_doing=True) as browser:
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        
        # Load existing cookies if any
        has_session = False
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r") as f:
                    cookies = json.load(f)
                    if cookies:
                        context.add_cookies(cookies)
                        print(f"Loaded {len(cookies)} cookies from {SESSION_FILE}")
                        has_session = True
            except Exception as e:
                print(f"Failed to load cookies: {e}")

        page = context.new_page()
        
        # 1. Pastikan status login
        need_login = True
        if has_session:
            print("Checking session status on x.com/home...")
            try:
                page.goto("https://x.com/home", timeout=35000, wait_until="domcontentloaded")
                time.sleep(4)
                if "/login" not in page.url and page.locator("a[data-testid='AppTabBar_Profile_Link']").count() > 0:
                    need_login = False
                    print("Verified: Already logged in with active profile!")
            except Exception as e:
                print(f"Session check error: {e}")

        if need_login:
            print("Starting login flow at https://x.com/i/flow/login...")
            send_telegram("🔑 Membuka halaman login resmi X.com untuk akun Pulup302...")
            page.goto("https://x.com/i/flow/login", timeout=45000, wait_until="domcontentloaded")
            time.sleep(6)
            
            # Tunggu elemen input muncul
            try:
                page.wait_for_selector("input", timeout=15000)
            except Exception:
                pass
            
            page.screenshot(path="login_step1.png")
            send_telegram_photo("login_step1.png", "Halaman Login X.com Terbuka")
            
            # Step 1: Input username
            user_input = page.locator("input").first
            if user_input.count() > 0:
                print(f"Filling username {X_USERNAME}...")
                user_input.click()
                user_input.fill(X_USERNAME)
                time.sleep(1)
                page.keyboard.press("Enter")
                time.sleep(4)
            else:
                print("Username input selector not matched!")
            
            # Step 1.5: Phone or username verification jika diminta
            try:
                if page.locator("input[data-testid='ocfEnterTextTextInput']").count() > 0:
                    print("X asked for alternate identifier...")
                    page.locator("input[data-testid='ocfEnterTextTextInput']").first.fill(X_USERNAME)
                    time.sleep(1)
                    page.keyboard.press("Enter")
                    time.sleep(4)
            except Exception:
                pass

            # Step 2: Input password
            try:
                page.wait_for_selector("input[name='password'], input[type='password']", timeout=10000)
            except Exception:
                pass
            
            pwd_input = page.locator("input[name='password'], input[type='password']").first
            if pwd_input.count() > 0:
                print("Filling password...")
                pwd_input.click()
                pwd_input.fill(X_PASSWORD)
                time.sleep(1)
                page.keyboard.press("Enter")
                time.sleep(8)
            else:
                print("Password input not found!")
                page.screenshot(path="pwd_missing.png")
                send_telegram_photo("pwd_missing.png", "Password field missing")

            # Persist cookies
            cookies = context.cookies()
            auth_token = next((c for c in cookies if c.get("name") == "auth_token"), None)
            if auth_token:
                print(f"SUCCESS! auth_token found: {auth_token['value'][:8]}...")
                with open(SESSION_FILE, "w") as f:
                    json.dump(cookies, f, indent=2)
                page.screenshot(path="login_success.png")
                send_telegram_photo("login_success.png", "🎉 Berhasil Login X.com!")
            else:
                print("Warning: auth_token cookie not found in session!")
                page.screenshot(path="login_state.png")
                send_telegram_photo("login_state.png", "Status akhir login")

        # 2. Execute Search with Latest filter (f=live)
        search_url = f"https://x.com/search?q={query}&f=live"
        print(f"Navigating to search URL: {search_url}")
        page.goto(search_url, timeout=45000, wait_until="domcontentloaded")
        time.sleep(8)
        
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
            send_telegram_photo("search_live.png", f"📸 Bukti Live Search X: {query}")
        else:
            send_telegram(f"⚠️ Tidak ada tweet yang ditarik, lihat tangkapan layar live search.")
            send_telegram_photo("search_live.png", f"Live Search Result: {query}")

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else "Barca"
    login_and_search(q)
