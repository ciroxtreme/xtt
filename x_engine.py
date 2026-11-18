import sys
import os
import json
import time
import socket
import urllib.parse
import requests
from camoufox.sync_api import Camoufox

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1936436999")
X_USERNAME = os.getenv("X_USERNAME", "Pulup302")
X_PASSWORD = os.getenv("X_PASSWORD", "ciroxtreme0703")
SESSION_FILE = "session_x.json"

def get_browser_proxy():
    """Cek apakah Cloudflare WARP SOCKS5 proxy aktif di port 40000 (seperti di ciro-cctv-stealth)"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect(("127.0.0.1", 40000))
        s.close()
        print("✅ Detected Cloudflare WARP SOCKS5 proxy on 127.0.0.1:40000")
        return {"server": "socks5://127.0.0.1:40000"}
    except Exception:
        pass
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

def inspect_real_x_state(page):
    """
    Inspektor Anti-Halu untuk X.com:
    Membaca secara jujur apakah layar sedang di:
    - STATE_SECURITY_GATE (Performing security verification / Just a moment)
    - STATE_LOGGED_IN_VERIFIED (Ada navigasi profil @Pulup302 atau tweet ter-render)
    - STATE_LOGIN_MODAL_OR_FLOW (Muncul dialog 'See what's happening' / 'Sign in to X' / '/i/flow/login')
    - STATE_HYDRATING (Sedang loading splash screen X)
    """
    info = page.evaluate("""() => {
        const url = location.href;
        const title = document.title || '';
        const body = document.body ? document.body.innerText : '';
        const bodyLower = body.toLowerCase();
        const titleLower = title.toLowerCase();

        const isSecurityGate = (
            bodyLower.includes('performing security verification') ||
            bodyLower.includes('verify you are human') ||
            titleLower.includes('just a moment') ||
            titleLower.includes('security verification')
        );

        const hasProfileNav = !!document.querySelector(
            "a[data-testid='AppTabBar_Profile_Link'], [data-testid='SideNav_AccountSwitcher_Button'], a[aria-label='Profile']"
        );
        const tweetCount = document.querySelectorAll("article[data-testid='tweet']").length;
        const hasLoginDialog = (
            url.includes('/i/flow/login') ||
            url.includes('/login') ||
            bodyLower.includes("see what's happening") ||
            bodyLower.includes("sign in to x")
        );

        let state = 'STATE_HYDRATING';
        if (isSecurityGate) {
            state = 'STATE_SECURITY_GATE';
        } else if (hasProfileNav || tweetCount > 0) {
            state = 'STATE_LOGGED_IN_VERIFIED';
        } else if (hasLoginDialog) {
            state = 'STATE_LOGIN_MODAL_OR_FLOW';
        }

        return {
            state,
            url,
            title,
            isSecurityGate,
            hasProfileNav,
            tweetCount,
            hasLoginDialog
        };
    }""")
    print(f"🧭 [X STATE INSPECTOR] Posisi Nyata: {info['state']} | URL: {info['url']} | Profile={info['hasProfileNav']} | Tweets={info['tweetCount']}")
    return info

def wait_for_x_ready(page, max_wait_sec=25):
    """
    Menunggu dengan sabar hingga SPA X.com selesai memproses cookie atau melewati gerbang verifikasi.
    Jika terdeteksi iframe verifikasi, klik secara natural seperti di capture_camoufox.py (ciro-cctv-stealth).
    """
    for sec in range(1, max_wait_sec + 1):
        time.sleep(1)
        st = inspect_real_x_state(page)
        if st["state"] == "STATE_LOGGED_IN_VERIFIED":
            return st
        if st["state"] == "STATE_SECURITY_GATE":
            try:
                for frame in page.frames:
                    if "challenges.cloudflare.com" in frame.url:
                        cb = frame.query_selector("input[type='checkbox'], #challenge-stage, .ctp-checkbox-label")
                        if cb:
                            print("[*] Mengklik checkbox verifikasi di iframe...")
                            cb.click()
            except Exception:
                pass
    return inspect_real_x_state(page)

def login_and_search(query="Barca"):
    proxy_cfg = get_browser_proxy()
    proxy_label = "WARP SOCKS5 Tunnel (127.0.0.1:40000)" if proxy_cfg else "Direct IP"
    send_telegram(f"🐦 [X Runner] Memulai eksekusi X Engine via {proxy_label} (Mode: Strict State Anti-Halu)...")

    with Camoufox(headless=True, i_know_what_im_doing=True, proxy=proxy_cfg) as browser:
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

        encoded_query = urllib.parse.quote(query)
        search_url = f"https://x.com/search?q={encoded_query}&f=live"

        # 1. Buka langsung halaman Search (atau Home) dan cek State Nyata
        print(f"Navigating to {search_url}...")
        page.goto(search_url, timeout=50000, wait_until="domcontentloaded")
        st = wait_for_x_ready(page, max_wait_sec=25)

        # ATURAN MUTLAK ANTI-HALU:
        # Jika masih tertahan di STATE_SECURITY_GATE, DILARANG KERAS mengetik username/password atau lanjut!
        if st["state"] == "STATE_SECURITY_GATE":
            page.screenshot(path="x_security_gate.png")
            send_telegram_photo(
                "x_security_gate.png",
                f"❌ [ANTI-HALU STOP] Posisi nyata masih tertahan di STATE_SECURITY_GATE ({st['title']}). Bot berhenti jujur & tidak akan mengetik login buta!"
            )
            sys.exit(1)

        # Jika belum login (benar-benar di STATE_LOGIN_MODAL_OR_FLOW dan bukan karena cookie lambat dimuat)
        if st["state"] != "STATE_LOGGED_IN_VERIFIED":
            send_telegram(f"⚠️ Posisi nyata: {st['state']}. Mencoba login resmi untuk akun {X_USERNAME}...")
            page.goto("https://x.com/i/flow/login", timeout=45000, wait_until="domcontentloaded")
            time.sleep(6)

            st_login = inspect_real_x_state(page)
            if st_login["state"] == "STATE_SECURITY_GATE":
                page.screenshot(path="x_login_gate.png")
                send_telegram_photo("x_login_gate.png", "❌ [ANTI-HALU STOP] Halaman login dihadang STATE_SECURITY_GATE.")
                sys.exit(1)

            user_input = page.locator("input[autocomplete='username']").first
            if user_input.count() == 0:
                user_input = page.locator("input").first

            if user_input.count() > 0:
                user_input.click()
                user_input.fill("")
                user_input.fill(X_USERNAME)
                time.sleep(1)
                page.keyboard.press("Enter")
                time.sleep(5)
            else:
                page.screenshot(path="no_user_input.png")
                send_telegram_photo("no_user_input.png", "❌ [ANTI-HALU STOP] Kolom input username tidak ditemukan.")
                sys.exit(1)

            # Wajib pastikan kolom input[type='password'] benar-benar muncul sebelum mengetik password!
            # (Mencegah bug mengetik Pulup302ciroxtreme0703 di kolom username yang sama!)
            pwd_input = page.locator("input[name='password'], input[type='password']").first
            try:
                pwd_input.wait_for(state="visible", timeout=12000)
            except Exception:
                pass

            if pwd_input.count() == 0 or not pwd_input.is_visible():
                page.screenshot(path="pwd_not_visible.png")
                send_telegram_photo(
                    "pwd_not_visible.png",
                    "❌ [ANTI-HALU STOP] Kolom password belum muncul setelah isi username! Bot berhenti agar tidak mengetik password di kolom username."
                )
                sys.exit(1)

            pwd_input.click()
            pwd_input.fill("")
            pwd_input.fill(X_PASSWORD)
            time.sleep(1)
            page.keyboard.press("Enter")
            time.sleep(8)

            page.goto(search_url, timeout=45000, wait_until="domcontentloaded")
            st = wait_for_x_ready(page, max_wait_sec=20)
            if st["state"] != "STATE_LOGGED_IN_VERIFIED":
                page.screenshot(path="login_not_verified.png")
                send_telegram_photo("login_not_verified.png", f"❌ [ANTI-HALU STOP] Setelah submit login, posisi masih di {st['state']}.")
                sys.exit(1)

        # 2. Sekarang dijamin 100% berada di STATE_LOGGED_IN_VERIFIED!
        print(f"✅ Posisi terkonfirmasi: {st['state']} (Profile={st['hasProfileNav']}, Tweets={st['tweetCount']})")

        try:
            page.wait_for_selector("article[data-testid='tweet']", timeout=15000)
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

        # Simpan session_x.json terbaru hanya saat sudah terverifikasi login
        cookies_now = context.cookies()
        if any(c.get("name") == "auth_token" for c in cookies_now):
            with open(SESSION_FILE, "w") as f:
                json.dump(cookies_now, f, indent=2)

        results = [f"👤 {u}\n💬 {t}" for u, t in tweet_records[:30]]

        if results:
            header = f"🔥 Postingan Terbaru di X untuk '{query}' (Live - {len(results)} Tweet | State: {st['state']}):\n\n"
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

            send_telegram_photo("search_live.png", f"📸 Bukti Nyata Live Search X: {query} ({st['state']})")
        else:
            send_telegram_photo("search_live.png", f"⚠️ Posisi: {st['state']} | Tidak ada tweet yang ditemukan untuk '{query}'.")

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else "Barca"
    login_and_search(q)
