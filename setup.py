"""
setup.py — Installer for Ruijie Smart Bypass
Installs required Python packages.
Run once before using faylooma.py
"""
import sys
import subprocess

def color(text, code): return f"\033[{code}m{text}\033[0m"
def green(t): return color(t, "1;32")
def red(t):   return color(t, "1;31")
def yellow(t): return color(t, "1;33")

print(f"\n{'='*45}")
print(f"  Ruijie Bypass — Setup")
print(f"{'='*45}")
print(f"  Python : {yellow(sys.version.split()[0])}")

deps = ["requests", "pycryptodome"]
print(f"\n  Installing dependencies...")
all_ok = True
for dep in deps:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", dep, "-q"],
            capture_output=True
        )
        status = green("✓") if r.returncode == 0 else red("✗")
        if r.returncode != 0:
            all_ok = False
        print(f"    {dep:20s} {status}")
    except Exception as e:
        print(f"    {dep:20s} {red('✗')} ({e})")
        all_ok = False

if all_ok:
    print(f"\n{green('[✓] Setup complete! Now run:')}")
    print(f"    python faylooma.py\n")
else:
    print(f"\n{red('[!] Some packages failed. Try:')}")
    print(f"    pip install requests pycryptodome\n")
