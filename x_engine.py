import sys
import os
import json
import time
import urllib.parse
import requests
from camoufox.sync_api import Camoufox

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "DUMMY_TELEGRAM_TOKEN_PROTECTED")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1936436999")
X_USERNAME = os.getenv("X_USERNAME", "Pulup302")
X_PASSWORD = os.getenv("X_PASSWORD", "ciroxtreme0703")
SESSION_FILE = "session_x.json"

def send_telegram(text):
    print(f"[TELEGRAM] {text[:120]}...")
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=15)
    except Exception as e:
        print(f"[ERR] Failed to send telegram text: {e}")

def send_telegram_photo(photo_path, caption=""):
    print(f"[TELEGRAM PHOTO] {photo_path} - {caption}")
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        with open(photo_path, "rb") as f:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, files={"photo": f}, timeout=25)
    except Exception as e:
        print(f"[ERR] Failed to send photo: {e}")

def wait_for_telegram_reply(prompt_message, timeout_sec=180):
    send_telegram(f"⏳ {prompt_message}\n\n👉 Kirim balasannya ke chat bot ini dalam {timeout_sec} detik.")
    url_updates = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    last_update_id = 0
    try:
        r = requests.get(url_updates, params={"offset": -1}, timeout=10).json()
        if r.get("result"):
            last_update_id = r["result"][-1]["update_id"]
    except Exception:
        pass

    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        time.sleep(3)
        try:
            r = requests.get(url_updates, params={"offset": last_update_id + 1, "timeout": 5}, timeout=10).json()
            results = r.get("result", [])
            for res in results:
                last_update_id = res["update_id"]
                msg = res.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id"))
                text = msg.get("text", "").strip()
                if chat_id == str(TELEGRAM_CHAT_ID) and text:
                    send_telegram(f"✅ Menerima kode: '{text}', menyuntikkan ke browser...")
                    return text
        except Exception as e:
            print(f"Error polling telegram: {e}")

    send_telegram("❌ Waktu habis (timeout) menunggu kode verifikasi dari Telegram.")
    return None

def inspect_x_state(page):
    """
    Memeriksa kondisi DOM nyata X.com setelah hydration React SPA selesai.
    """
    return page.evaluate("""() => {
        const url = location.href;
        const hasProfileNav = !!document.querySelector(
            "a[data-testid='AppTabBar_Profile_Link'], [data-testid='SideNav_AccountSwitcher_Button'], a[aria-label='Profile']"
        );
        const tweetCount = document.querySelectorAll("article[data-testid='tweet']").length;
        const isLoginFlow = url.includes('/i/flow/login') || url.includes('/login');
        return {
            url,
            hasProfileNav,
            tweetCount,
            isLoginFlow
        };
    }""")

def login_and_search(query="Barca"):
    send_telegram(f"🐦 [X Runner] Memulai eksekusi X Engine untuk query: '{query}'...")

    with Camoufox(headless=True, i_know_what_im_doing=True) as browser:
        context = browser.new_context(viewport={"width": 1280, "height": 900})

        has_session = False
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r") as f:
                    cookies = json.load(f)
                    if cookies:
                        context.add_cookies(cookies)
                        print(f"Loaded {len(cookies)} cookies from {SESSION_FILE}")
                        has_session = any(c.get("name") == "auth_token" for c in cookies)
            except Exception as e:
                print(f"Failed to load cookies: {e}")

        page = context.new_page()

        need_login = True
        if has_session:
            print("Checking session status on https://x.com/home (waiting up to 25s for SPA hydration)...")
            try:
                page.goto("https://x.com/home", timeout=45000, wait_until="domcontentloaded")
                for wait_sec in range(1, 26):
                    time.sleep(1)
                    st = inspect_x_state(page)
                    if st["hasProfileNav"] or st["tweetCount"] > 0:
                        need_login = False
                        print(f"✅ Verified: Already logged in (@Pulup302) after {wait_sec}s! state={st}")
                        break
                    if st["isLoginFlow"] and wait_sec >= 10:
                        print(f"Redirected to login flow after {wait_sec}s.")
                        break
            except Exception as e:
                print(f"Session check notice: {e}")

        if need_login:
            print("Starting login flow at https://x.com/i/flow/login...")
            send_telegram("🔑 Membuka halaman login resmi X.com untuk akun Pulup302...")
            page.goto("https://x.com/i/flow/login", timeout=45000, wait_until="domcontentloaded")
            time.sleep(6)

            try:
                page.wait_for_selector("input[autocomplete='username'], input", timeout=15000)
            except Exception:
                pass

            user_input = page.locator("input[autocomplete='username'], input").first
            if user_input.count() > 0:
                print(f"Filling username {X_USERNAME}...")
                user_input.click()
                user_input.fill("")
                user_input.fill(X_USERNAME)
                time.sleep(1)
                page.keyboard.press("Enter")
                time.sleep(5)
            else:
                send_telegram("❌ Gagal menemukan kolom input username!")
                page.screenshot(path="no_user_input.png")
                send_telegram_photo("no_user_input.png", "Kolom input username tidak ada")
                sys.exit(1)

            try:
                page.wait_for_selector("input[name='password'], input[type='password']", timeout=12000)
            except Exception:
                pass

            pwd_input = page.locator("input[name='password'], input[type='password']").first
            if pwd_input.count() > 0:
                print("Filling password...")
                pwd_input.click(force=True)
                pwd_input.fill("")
                pwd_input.fill(X_PASSWORD)
                time.sleep(1)
                page.keyboard.press("Enter")
                time.sleep(8)
            else:
                send_telegram("❌ Kolom input password belum muncul!")
                page.screenshot(path="pwd_missing.png")
                send_telegram_photo("pwd_missing.png", "Password field missing")
                sys.exit(1)

            cookies = context.cookies()
            auth_token = next((c for c in cookies if c.get("name") == "auth_token"), None)
            if not auth_token:
                page.screenshot(path="login_failed.png")
                send_telegram_photo("login_failed.png", "❌ Login belum berhasil, auth_token belum ditemukan.")
                sys.exit(1)

            with open(SESSION_FILE, "w") as f:
                json.dump(cookies, f, indent=2)
            page.screenshot(path="login_success.png")
            send_telegram_photo("login_success.png", "🎉 Berhasil Login X.com! Sesi tersimpan permanen.")

        # 2. JALANKAN PENCARIAN LIVE DENGAN QUERY TER-ENCODE
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://x.com/search?q={encoded_query}&f=live"
        send_telegram(f"🔍 Sesi Login Aktif! Menjalankan pencarian Live untuk query: '{query}'...")
        print(f"Navigating to search URL: {search_url}")
        page.goto(search_url, timeout=45000, wait_until="domcontentloaded")

        try:
            page.wait_for_selector("article[data-testid='tweet']", timeout=20000)
        except Exception:
            pass

        print("Progressively scrolling to load up to 30 live tweets...")
        seen_tweets = set()
        tweet_records = []

        for _ in range(8):
            elements = page.locator("article[data-testid='tweet']").all()
            for el in elements:
                try:
                    text_content = el.locator("div[data-testid='tweetText']").first.inner_text().strip()
                except Exception:
                    text_content = ""
                try:
                    user_info = el.locator("div[data-testid='User-Name']").first.inner_text().replace("\n", " ")
                except Exception:
                    user_info = "Unknown User"

                item_key = f"{user_info}_{text_content[:40]}"
                if item_key not in seen_tweets:
                    seen_tweets.add(item_key)
                    tweet_records.append((user_info, text_content if text_content else "(Media/No text)"))

            if len(tweet_records) >= 30:
                break

            page.mouse.wheel(0, 1000)
            time.sleep(1.8)

        print(f"Total unique tweets collected: {len(tweet_records)}")
        page.screenshot(path="search_live.png")

        # Update session cookies jika valid
        cookies_now = context.cookies()
        if any(c.get("name") == "auth_token" for c in cookies_now):
            with open(SESSION_FILE, "w") as f:
                json.dump(cookies_now, f, indent=2)

        results = [f"👤 {u}\n💬 {t}" for u, t in tweet_records[:30]]

        if results:
            header = f"🔥 Postingan Terbaru di X untuk '{query}' (Live - {len(results)} Tweet):\n\n"
            current_chunk = header
            chunk_num = 1

            for item in results:
                entry = item + "\n\n───────────────────\n\n"
                if len(current_chunk) + len(entry) > 3800:
                    send_telegram(current_chunk.strip())
                    time.sleep(0.6)
                    chunk_num += 1
                    current_chunk = f"🔥 Lanjutan {query} (Bagian {chunk_num}):\n\n" + entry
                else:
                    current_chunk += entry

            if current_chunk.strip():
                send_telegram(current_chunk.strip())

            send_telegram_photo("search_live.png", f"📸 Bukti Live Search X: {query}")
        else:
            send_telegram(f"⚠️ Tidak ada tweet yang ditarik untuk '{query}', lihat screenshot.")
            send_telegram_photo("search_live.png", f"Live Search Result: {query}")

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else "Barca"
    login_and_search(q)
