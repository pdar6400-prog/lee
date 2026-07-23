"""
setup.py — Auto installer for Ruijie Smart Bypass
Detects Python version and installs correct pyarmor runtime.
Run once before using faylooma.py
"""
import sys, os, shutil, subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RUNTIME_DIR = os.path.join(SCRIPT_DIR, "pyarmor_runtime_000000")

VER = f"cp{sys.version_info.major}{sys.version_info.minor}"
SO_SRC = os.path.join(SCRIPT_DIR, "runtimes", VER, "pyarmor_runtime.so")
SO_DST = os.path.join(RUNTIME_DIR, "pyarmor_runtime.so")

def color(text, code): return f"\033[{code}m{text}\033[0m"
def green(t): return color(t, "1;32")
def red(t):   return color(t, "1;31")
def yellow(t): return color(t, "1;33")

print(f"\n{'='*45}")
print(f"  Ruijie Bypass — Setup")
print(f"{'='*45}")
print(f"  Python version : {yellow(VER)}")

# ── Check supported version ──────────────────────
SUPPORTED = ["cp311", "cp312", "cp313"]
if VER not in SUPPORTED:
    print(red(f"\n[✗] Python {sys.version.split()[0]} is not supported."))
    print(yellow(f"    Supported: Python 3.11 / 3.12 / 3.13"))
    print(yellow(f"\n    Update Python in Termux:"))
    print(f"    pkg update && pkg install python -y")
    sys.exit(1)

# ── Install runtime ──────────────────────────────
if not os.path.exists(SO_SRC):
    print(red(f"\n[✗] Runtime not found: {SO_SRC}"))
    sys.exit(1)

os.makedirs(RUNTIME_DIR, exist_ok=True)
shutil.copy2(SO_SRC, SO_DST)
print(f"  Runtime        : {green('Installed ✓')}")

# ── Install Python dependencies ──────────────────
print(f"\n  Installing dependencies...")
deps = ["requests", "pycryptodome"]
for dep in deps:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", dep, "-q"],
            capture_output=True
        )
        status = green("✓") if r.returncode == 0 else red("✗")
        print(f"    {dep:20s} {status}")
    except Exception as e:
        print(f"    {dep:20s} {red('✗')} ({e})")

print(f"\n{green('[✓] Setup complete! Now run:')}")
print(f"    python faylooma.py\n")
