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
WEBSHARE_PROXY = os.getenv("WEBSHARE_ROTATING_PROXY", "")
SESSION_FILE = "session_x.json"

def get_proxy_config(use_webshare=False):
    if use_webshare and WEBSHARE_PROXY:
        try:
            p = urllib.parse.urlparse(WEBSHARE_PROXY)
            if p.hostname and p.port:
                cfg = {"server": f"http://{p.hostname}:{p.port}"}
                if p.username:
                    cfg["username"] = urllib.parse.unquote(p.username)
                if p.password:
                    cfg["password"] = urllib.parse.unquote(p.password)
                return cfg
        except Exception as e:
            print(f"Proxy parse error: {e}")
    return None

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
    send_telegram(f"⏳ {prompt_message}\n\n👉 Kirim balasannya (kode angka/email) ke chat bot ini dalam {timeout_sec} detik.")
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

def handle_cloudflare_turnstile_if_present(page):
    """
    Mendeteksi jika X.com menampilkan 'Performing security verification' (Cloudflare Turnstile)
    dan mengklik checkbox verifikasi secara manusiawi lalu menunggu sampai halaman terbuka.
    """
    for attempt in range(1, 6):
        body_text = page.evaluate("() => document.body ? document.body.innerText : ''").lower()
        if "performing security verification" not in body_text and "verify you are human" not in body_text:
            return True

        print(f"⚠️ [CLOUDFLARE TURNSTILE] Terdeteksi tantangan keamanan X.com (Attempt {attempt}/5), menyelesaikan...")
        time.sleep(3)

        # Cari iframe turnstile atau posisi widget lalu klik
        clicked = False
        for frame in page.frames:
            if "challenges.cloudflare.com" in frame.url:
                try:
                    box = frame.locator("body").bounding_box()
                    if box:
                        # Checkbox Turnstile berada di sisi kiri widget (~x + 30, y + height/2)
                        click_x = box["x"] + 30
                        click_y = box["y"] + (box["height"] / 2)
                        print(f"Clicking Turnstile iframe checkbox at ({click_x}, {click_y})...")
                        page.mouse.move(click_x, click_y, steps=5)
                        time.sleep(0.2)
                        page.mouse.click(click_x, click_y)
                        clicked = True
                        break
                except Exception as e:
                    print(f"Frame click notice: {e}")

        if not clicked:
            # Fallback koordinat berdasarkan screenshot standar (1280x900)
            # Di screenshot tampak kotak 'Verify you are human' berada di sekitar (260, 325)
            try:
                page.mouse.move(260, 325, steps=5)
                page.mouse.click(260, 325)
            except Exception:
                pass

        time.sleep(6)

    body_after = page.evaluate("() => document.body ? document.body.innerText : ''").lower()
    return "performing security verification" not in body_after

def inspect_x_state(page):
    """
    Memeriksa kondisi nyata halaman X.com (Anti-Halu):
    Apakah sedang di halaman Cloudflare, sedang loading hydration, sudah login (@Pulup302), atau benar-benar terlempar ke /login.
    """
    return page.evaluate("""() => {
        const url = location.href;
        const body = document.body ? document.body.innerText : '';
        const bodyLower = body.toLowerCase();
        const isCloudflare = bodyLower.includes('performing security verification') || bodyLower.includes('verify you are human');
        const hasProfileNav = !!document.querySelector("a[data-testid='AppTabBar_Profile_Link'], [data-testid='SideNav_AccountSwitcher_Button'], a[aria-label='Profile']");
        const tweetCount = document.querySelectorAll("article[data-testid='tweet']").length;
        const isLoginFlow = url.includes('/i/flow/login') || url.includes('/login');
        return {
            url,
            isCloudflare,
            hasProfileNav,
            tweetCount,
            isLoginFlow
        };
    }""")

def run_x_search_attempt(query, use_proxy=False):
    proxy_cfg = get_proxy_config(use_webshare=use_proxy)
    mode_label = f"Residential Proxy ({proxy_cfg['server']})" if proxy_cfg else "Direct IP"
    print(f"Starting Camoufox with {mode_label}...")

    with Camoufox(headless=True, proxy=proxy_cfg, geoip=True if proxy_cfg else False, i_know_what_im_doing=True) as browser:
        context = browser.new_context(viewport={"width": 1280, "height": 900})

        has_auth_cookie = False
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r") as f:
                    cookies = json.load(f)
                    # Bersihkan cf_clearance / __cf_bm lama yang terikat IP sebelumnya agar tidak memicu konflik Cloudflare!
                    clean_cookies = [
                        c for c in cookies
                        if c.get("name") not in ("cf_clearance", "__cf_bm")
                    ]
                    if clean_cookies:
                        context.add_cookies(clean_cookies)
                        has_auth_cookie = any(c.get("name") == "auth_token" for c in clean_cookies)
                        print(f"Loaded {len(clean_cookies)} clean session cookies (has_auth_token={has_auth_cookie})")
            except Exception as e:
                print(f"Failed to load cookies: {e}")

        page = context.new_page()

        encoded_query = urllib.parse.quote(query)
        search_url = f"https://x.com/search?q={encoded_query}&f=live"

        # Jika sudah punya auth_token di session_x.json, LANGSUNG buka halaman Search
        # dan tunggu sampai React SPA selesai memproses cookie (jangan buru-buru vonis cookie mati!)
        if has_auth_cookie:
            print(f"Navigating directly to search URL with existing auth_token ({mode_label}): {search_url}")
            page.goto(search_url, timeout=50000, wait_until="domcontentloaded")

            # Cek apakah dihadang Cloudflare Turnstile
            if not handle_cloudflare_turnstile_if_present(page):
                print(f"⚠️ Cloudflare Turnstile belum tembus di {mode_label}.")
                return "CLOUDFLARE_BLOCKED"

            # Tunggu hingga 25 detik sampai elemen profil ATAU tweet muncul (hydration React X.com)
            print("Menunggu X.com selesai memproses cookie & merender DOM (maks 25 detik)...")
            for wait_i in range(25):
                state = inspect_x_state(page)
                if state["isCloudflare"]:
                    handle_cloudflare_turnstile_if_present(page)
                if state["tweetCount"] > 0 or state["hasProfileNav"]:
                    print(f"✅ [ANTI-HALU VERIFIED] Cookie aktif! hasProfileNav={state['hasProfileNav']}, tweetCount={state['tweetCount']} (setelah {wait_i+1}s)")
                    break
                if state["isLoginFlow"] and wait_i >= 8:
                    print("⚠️ X.com me-redirect ke /i/flow/login, artinya auth_token benar-benar expired.")
                    break
                time.sleep(1)

            state = inspect_x_state(page)
            print(f"🧭 [X STATE INSPECTOR] {state}")

            if state["isCloudflare"]:
                return "CLOUDFLARE_BLOCKED"

        # Hanya jalankan login manual jika benar-benar TIDAK punya auth_token atau terlempar ke /i/flow/login
        state = inspect_x_state(page)
        if not has_auth_cookie or (state["isLoginFlow"] and not state["hasProfileNav"]):
            send_telegram(f"⚠️ Cookie auth_token belum ada / terdeteksi redirect ke /login. Membuka login resmi X.com untuk {X_USERNAME}...")
            page.goto("https://x.com/i/flow/login", timeout=45000, wait_until="domcontentloaded")
            time.sleep(6)
            handle_cloudflare_turnstile_if_present(page)

            try:
                page.wait_for_selector("input[autocomplete='username'], input", timeout=15000)
            except Exception:
                pass

            user_input = page.locator("input[autocomplete='username'], input").first
            if user_input.count() > 0:
                user_input.click()
                user_input.fill("")
                user_input.fill(X_USERNAME)
                time.sleep(1)
                page.keyboard.press("Enter")
                time.sleep(5)
            else:
                page.screenshot(path="no_user_input.png")
                send_telegram_photo("no_user_input.png", "❌ Gagal menemukan kolom input username X.com")
                return "LOGIN_FAILED"

            try:
                page.wait_for_selector("input[name='password'], input[type='password']", timeout=12000)
            except Exception:
                pass

            pwd_input = page.locator("input[name='password'], input[type='password']").first
            if pwd_input.count() > 0:
                pwd_input.click(force=True)
                pwd_input.fill("")
                pwd_input.fill(X_PASSWORD)
                time.sleep(1)
                page.keyboard.press("Enter")
                time.sleep(8)
            else:
                page.screenshot(path="pwd_missing.png")
                send_telegram_photo("pwd_missing.png", "❌ Kolom input password tidak muncul (mungkin butuh verifikasi tambahan)")
                return "LOGIN_FAILED"

            # Navigasi ke search setelah login berhasil
            page.goto(search_url, timeout=50000, wait_until="domcontentloaded")
            time.sleep(6)

        # Pastikan tweet sudah mulai ter-render
        try:
            page.wait_for_selector("article[data-testid='tweet']", timeout=18000)
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

        # Simpan kembali cookies bersih (tanpa cf_clearance/__cf_bm agar tidak merusak run berikutnya di IP berbeda!)
        cookies_now = context.cookies()
        if any(c.get("name") == "auth_token" for c in cookies_now):
            clean_save = [c for c in cookies_now if c.get("name") not in ("cf_clearance", "__cf_bm")]
            with open(SESSION_FILE, "w") as f:
                json.dump(clean_save, f, indent=2)

        if tweet_records:
            results = [f"👤 {u}\n💬 {t}" for u, t in tweet_records[:30]]
            header = f"🔥 Postingan Terbaru di X untuk '{query}' (Live - {len(results)} Tweet | {mode_label}):\n\n"
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

            send_telegram_photo("search_live.png", f"📸 Bukti Live Search X: {query} (@Pulup302 Verified)")
            return "SUCCESS"
        else:
            final_st = inspect_x_state(page)
            if final_st["isCloudflare"]:
                return "CLOUDFLARE_BLOCKED"
            send_telegram(f"⚠️ Tidak ada tweet yang ditemukan untuk '{query}' (Posisi: {final_st}).")
            send_telegram_photo("search_live.png", f"Live Search Result: {query}")
            return "NO_TWEETS"

def login_and_search(query="Barca"):
    send_telegram(f"🐦 [X Runner] Menjalankan Live Search X.com untuk: '{query}'...")
    # Coba Direct IP dulu dengan cookies bersih (tanpa cf_clearance lama yang bikin bentrok IP!)
    res = run_x_search_attempt(query, use_proxy=False)
    if res == "CLOUDFLARE_BLOCKED" and WEBSHARE_PROXY:
        send_telegram("🔄 Terdeteksi Cloudflare Turnstile di Direct IP, mengalihkan otomatis ke Residential Proxy...")
        run_x_search_attempt(query, use_proxy=True)

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else "Barca"
    login_and_search(q)
