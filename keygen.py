"""
keygen.py — Developer Tool
Key Generator for Ruijie Smart Bypass
Author: @naymin126653 / @donebro100
"""

import json, random, string, os
from datetime import datetime, timedelta

KEY_FILE = "key.json"

PLANS = {
    "1": ("30m",       timedelta(minutes=30)),
    "2": ("7d",        timedelta(days=7)),
    "3": ("1m",        timedelta(days=30)),
    "4": ("unlimited", None),
}

PLAN_NAMES = {
    "30m":       "30 Minutes",
    "7d":        "7 Days",
    "1m":        "1 Month",
    "unlimited": "Unlimited",
}

# ── Colors ──────────────────────────────────────────────
g = "\033[1;32m"; y = "\033[1;33m"; r = "\033[1;31m"
b = "\033[1;34m"; w = "\033[0m";    c = "\033[1;36m"

def clear(): os.system('cls' if os.name == 'nt' else 'clear')

def logo():
    clear()
    print(f"{b}{'='*50}")
    print(f"   Ruijie Bypass — KEY MANAGER")
    print(f"   Telegram: @naymin126653 / @donebro100")
    print(f"{'='*50}{w}\n")

def gen_key():
    chars = string.ascii_uppercase + string.digits
    parts = [''.join(random.choices(chars, k=4)) for _ in range(4)]
    return "STAR-" + "-".join(parts)

def load_db():
    if not os.path.exists(KEY_FILE): return {}
    try:
        with open(KEY_FILE, 'r') as f: return json.load(f)
    except: return {}

def save_db(db):
    with open(KEY_FILE, 'w') as f:
        json.dump(db, f, indent=2)

# ── Menu 1: Generate New Key ────────────────────────────
def menu_generate():
    logo()
    print(f"{c}── Generate New Key ──{w}\n")

    hwid = input(f"{y}User HWID: {w}").strip().upper()
    if not hwid:
        print(f"{r}HWID required.{w}"); input("\nEnter to back..."); return

    note = input(f"{y}Note (username/telegram): {w}").strip()

    print(f"\n{c}Plans:{w}")
    for k, (name, _) in PLANS.items():
        print(f"  {k}. {PLAN_NAMES[name]}")
    plan_choice = input(f"\n{y}Select plan: {w}").strip()

    if plan_choice not in PLANS:
        print(f"{r}Invalid choice.{w}"); input("\nEnter to back..."); return

    plan_name, duration = PLANS[plan_choice]
    expires_str = None
    if duration:
        expires_dt  = datetime.now() + duration
        expires_str = expires_dt.strftime("%Y-%m-%d %H:%M")

    key = gen_key()
    db  = load_db()
    db[key] = {
        "hwid":    hwid,
        "plan":    plan_name,
        "expires": expires_str,
        "active":  True,
        "note":    note,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    save_db(db)

    print(f"\n{g}{'='*40}")
    print(f"  Key     : {y}{key}{g}")
    print(f"  Plan    : {PLAN_NAMES[plan_name]}")
    print(f"  Expires : {expires_str or 'Never'}")
    print(f"  HWID    : {hwid}")
    print(f"{'='*40}{w}")
    print(f"\n{y}➜ Upload key.json to GitHub to activate.{w}")
    input("\nEnter to continue...")

# ── Menu 2: List All Keys ───────────────────────────────
def menu_list():
    logo()
    print(f"{c}── All Keys ──{w}\n")
    db = load_db()
    if not db:
        print(f"{y}No keys yet.{w}")
        input("\nEnter to back..."); return

    now = datetime.now()
    for i, (key, entry) in enumerate(db.items(), 1):
        active  = entry.get("active", True)
        exp_str = entry.get("expires", "Never")
        expired = False
        if exp_str and exp_str != "Never":
            try:
                expired = datetime.strptime(exp_str, "%Y-%m-%d %H:%M") < now
            except: pass
        status = f"{g}ACTIVE{w}" if (active and not expired) else f"{r}INACTIVE{w}"
        print(f"{i:>3}. {y}{key}{w}")
        print(f"     Status  : {status}")
        print(f"     HWID    : {entry.get('hwid','?')}")
        print(f"     Plan    : {PLAN_NAMES.get(entry.get('plan','?'), '?')}")
        print(f"     Expires : {exp_str}")
        print(f"     Note    : {entry.get('note','')}\n")

    input("Enter to back...")

# ── Menu 3: Revoke Key ──────────────────────────────────
def menu_revoke():
    logo()
    print(f"{c}── Revoke Key ──{w}\n")
    db  = load_db()
    key = input(f"{y}Enter key to revoke: {w}").strip().upper()
    if key not in db:
        print(f"{r}Key not found.{w}"); input("\nEnter to back..."); return
    db[key]["active"] = False
    save_db(db)
    print(f"{g}[✓] Key revoked: {key}{w}")
    input("\nEnter to back...")

# ── Menu 4: Delete Key ──────────────────────────────────
def menu_delete():
    logo()
    print(f"{c}── Delete Key ──{w}\n")
    db  = load_db()
    key = input(f"{y}Enter key to delete: {w}").strip().upper()
    if key not in db:
        print(f"{r}Key not found.{w}"); input("\nEnter to back..."); return
    confirm = input(f"{r}Delete {key}? (yes/no): {w}").strip().lower()
    if confirm == "yes":
        del db[key]
        save_db(db)
        print(f"{g}[✓] Deleted.{w}")
    else:
        print(f"{y}Cancelled.{w}")
    input("\nEnter to back...")

# ── Main ────────────────────────────────────────────────
def main():
    while True:
        logo()
        print(f"1. {g}Generate New Key{w}")
        print(f"2. {c}List All Keys{w}")
        print(f"3. {y}Revoke Key{w}")
        print(f"4. {r}Delete Key{w}")
        print(f"5. ❌ Exit\n")
        choice = input(f"{y}Select: {w}").strip()
        if   choice == "1": menu_generate()
        elif choice == "2": menu_list()
        elif choice == "3": menu_revoke()
        elif choice == "4": menu_delete()
        elif choice == "5": break

if __name__ == "__main__":
    main()
