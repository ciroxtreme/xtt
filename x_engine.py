
def get_browser_proxy():
    # Cek apakah Cloudflare WARP SOCKS5 proxy aktif di port 40000
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect(("127.0.0.1", 40000))
        s.close()
        print("Detected Cloudflare WARP proxy on 127.0.0.1:40000")
        return {"server": "socks5://127.0.0.1:40000"}
    except Exception:
        pass
    return None

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

def wait_for_telegram_reply(prompt_message, timeout_sec=180):
    """Kirim pesan minta input kode/2FA ke Telegram dan tunggu balasan Tuan Ciro"""
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

def login_and_search(query="Barca"):
    send_telegram(f"🐦 [X Runner] Memulai eksekusi X Engine (Mode: Autentikasi Ketat)...")
    
    proxy_cfg = get_browser_proxy()
    with Camoufox(headless=True, i_know_what_im_doing=True, proxy=proxy_cfg) as browser:
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
            
            try:
                page.wait_for_selector("input", timeout=15000)
            except Exception:
                pass
            
            # Step 1: Input username
            user_input = page.locator("input").first
            if user_input.count() > 0:
                print(f"Filling username {X_USERNAME}...")
                user_input.click()
                user_input.fill(X_USERNAME)
                time.sleep(1)
                
                next_btn = page.locator("button:has-text('Next'), div[role='button']:has-text('Next')").first
                if next_btn.count() > 0:
                    next_btn.click()
                else:
                    page.keyboard.press("Enter")
                time.sleep(5)
            else:
                send_telegram("❌ Gagal menemukan kolom input username!")
                page.screenshot(path="no_user_input.png")
                send_telegram_photo("no_user_input.png", "Kolom input username tidak ada")
                sys.exit(1)
            
            # Step 1.5: Phone or alternate username verification jika diminta
            try:
                if page.locator("input[data-testid='ocfEnterTextTextInput']").count() > 0:
                    print("X asked for alternate identifier...")
                    page.locator("input[data-testid='ocfEnterTextTextInput']").first.fill(X_USERNAME)
                    time.sleep(1)
                    page.keyboard.press("Enter")
                    time.sleep(5)
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
                try:
                    pwd_input.click(force=True, timeout=5000)
                except Exception:
                    pass
                pwd_input.fill(X_PASSWORD)
                time.sleep(1)
                
                login_btn = page.locator("[data-testid='LoginForm_Login_Button'], button:has-text('Log in'), div[role='button']:has-text('Log in')").first
                if login_btn.count() > 0:
                    try:
                        login_btn.click(force=True)
                    except Exception:
                        page.keyboard.press("Enter")
                else:
                    page.keyboard.press("Enter")
                
                time.sleep(8)
            else:
                send_telegram("❌ Gagal menemukan kolom input password!")
                page.screenshot(path="pwd_missing.png")
                send_telegram_photo("pwd_missing.png", "Password field missing")
                sys.exit(1)

            # Step 3: Loop pemeriksaan tantangan / 2FA / verifikasi kode setelah password
            auth_token_found = False
            for attempt in range(8):
                cookies = context.cookies()
                auth_cookie = next((c for c in cookies if c.get("name") == "auth_token"), None)
                if auth_cookie:
                    auth_token_found = True
                    break

                body_text = page.locator("body").inner_text()
                print(f"[Check {attempt}] Body text preview:\n", body_text[:200])
                
                # Kasus A: Butuh Kode Verifikasi Email atau SMS atau TOTP
                # Deteksi "security code", "confirmation code", "verification code", "check your email"
                if any(k in body_text.lower() for k in ["security code", "confirmation code", "verification code", "check your email", "two-factor", "authentication code", "enter code"]):
                    page.screenshot(path="need_code.png")
                    send_telegram_photo("need_code.png", "⚠️ X mengirim Kode Keamanan (Security Code) ke Email!")
                    
                    code = wait_for_telegram_reply("X.com meminta Security Code dari email p***2@g***.com.", timeout_sec=180)
                    if code:
                        code_input = page.locator("input[data-testid='ocfEnterTextTextInput'], input[type='text'], input[name='text'], input").first
                        if code_input.count() > 0:
                            try:
                                code_input.click(force=True, timeout=5000)
                            except Exception:
                                pass
                            code_input.fill(code)
                            time.sleep(1)
                            # Klik Next atau Continue
                            cont_btn = page.locator("button:has-text('Next'), button:has-text('Continue'), div[role='button']:has-text('Next'), div[role='button']:has-text('Continue')").first
                            if cont_btn.count() > 0:
                                try:
                                    cont_btn.click(force=True)
                                except Exception:
                                    page.keyboard.press("Enter")
                            else:
                                page.keyboard.press("Enter")
                            time.sleep(10)
                    else:
                        send_telegram("❌ Login dibatalkan karena tidak ada kode yang dimasukkan.")
                        sys.exit(1)

                # Kasus B: Arkose Labs Captcha
                elif "arkose" in page.content().lower() or "challenge" in page.url:
                    page.screenshot(path="captcha.png")
                    send_telegram_photo("captcha.png", "⚠️ Terkena Captcha tantangan visual X.com")
                    send_telegram("Terdeteksi Captcha bot X.com, mencoba menunggu...")
                    time.sleep(10)
                else:
                    time.sleep(4)

            # Validasi Mutlak: Sesi login wajib sudah jadi sebelum lanjut
            cookies = context.cookies()
            auth_token = next((c for c in cookies if c.get("name") == "auth_token"), None)
            if not auth_token:
                page_text = page.locator("body").inner_text()
                page.screenshot(path="login_failed.png")
                send_telegram_photo("login_failed.png", f"❌ Login Gagal! Sesi auth_token belum terbentuk.\n\nDetail:\n{page_text[:180]}")
                send_telegram("🛑 Proses dihentikan sesuai instruksi: tidak akan melakukan pencarian sebelum login tuntas 100%.")
                sys.exit(1)

            print(f"🎉 SUCCESS! auth_token terverifikasi: {auth_token['value'][:8]}...")
            with open(SESSION_FILE, "w") as f:
                json.dump(cookies, f, indent=2)
            page.screenshot(path="login_success.png")
            send_telegram_photo("login_success.png", "🎉 Berhasil Login X.com! Sesi tersimpan permanen.")

        # 2. HANYA JALAN JIKA LOGIN SUDAH 100% SUKSES:
        send_telegram(f"🔍 Sesi Login Aktif! Menjalankan pencarian Live untuk query: '{query}'...")
        search_url = f"https://x.com/search?q={query}&f=live"
        print(f"Navigating to search URL: {search_url}")
        page.goto(search_url, timeout=45000, wait_until="load")
        
        # Tunggu sampai selector tweet muncul atau timeout 15 detik
        try:
            page.wait_for_selector("article[data-testid='tweet']", timeout=15000)
        except Exception:
            pass
        
        # Progressive scrolling untuk memuat minimal 30 tweet live
        print("Progressively scrolling to load up to 30 live tweets...")
        seen_tweets = set()
        tweet_records = []
        
        for scroll_i in range(8):
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
                
                # Gunakan user + cuplikan text sebagai unique key agar tidak duplikat saat scrolling
                item_key = f"{user_info}_{text_content[:40]}"
                if item_key not in seen_tweets:
                    seen_tweets.add(item_key)
                    tweet_records.append((user_info, text_content if text_content else "(Media/No text)"))
            
            if len(tweet_records) >= 30:
                break
                
            page.mouse.wheel(0, 1000)
            time.sleep(1.8)
        
        print(f"Total unique tweets collected: {len(tweet_records)}")
        
        # Take screenshot of live search results
        page.screenshot(path="search_live.png")
        
        results = []
        for user_info, text_content in tweet_records[:30]:
            results.append(f"👤 {user_info}\n💬 {text_content}")
        
        # Format report message (Auto-chunk jika mendekati batas 4096 karakter Telegram)
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
