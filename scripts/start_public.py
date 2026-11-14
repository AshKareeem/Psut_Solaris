r"""Public demo in one command: the local server, a Cloudflare quick tunnel to it, and the GitHub Pages site pointed
at that tunnel for "Plan your own mission" (web/api.json, committed and pushed). Ctrl+C stops both.

The quick tunnel needs no Cloudflare account; its address changes on every start, which is why api.json is rewritten.
Visitors of https://ashkareeem.github.io/Psut_Solaris/ only see that address; the tunnel is used behind the page.

Usage:
  python scripts/start_public.py [--cloudflared C:\Users\user\tools\cloudflared.exe]
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_FILE = ROOT / "web" / "api.json"


def tunnel_url(proc, timeout=60):
    """The https://....trycloudflare.com address cloudflared prints on startup."""
    end = time.time() + timeout
    for line in proc.stderr:
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
        if m:
            return m.group(0)
        if time.time() > end:
            break
    raise SystemExit("cloudflared did not print a tunnel address")


def publish(url):
    API_FILE.write_text(json.dumps({"mission_api": url + "/api/mission",
                                    "note": "set by scripts/start_public.py while the laptop serves missions"}) + "\n")
    subprocess.run(["git", "commit", "-m", "Public demo: mission API through the current tunnel", "--", str(API_FILE)],
                   cwd=ROOT, check=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=ROOT, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cloudflared", default=r"C:\Users\user\tools\cloudflared.exe")
    a = ap.parse_args()
    server = subprocess.Popen([sys.executable, str(ROOT / "scripts" / "serve.py")], cwd=ROOT)
    tunnel = subprocess.Popen([a.cloudflared, "tunnel", "--no-autoupdate", "--url", "http://localhost:8765"],
                              stderr=subprocess.PIPE, text=True)
    try:
        url = tunnel_url(tunnel)
        publish(url)
        print(f"\nPublic app: {url}/#site=210&mast=10")
        print("GitHub Pages uses it for 'Plan your own mission' in about a minute. Ctrl+C stops everything.\n")
        tunnel.wait()
    except KeyboardInterrupt:
        pass
    finally:
        tunnel.terminate()
        server.terminate()


if __name__ == "__main__":
    main()
