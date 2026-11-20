#!/usr/bin/env python3
"""Windows: write game-routes.txt with only what you play on (be logged into a world):
the AWS block your Tibia world's game server is in, Tibia's Cloudflare game range, and your TeamSpeak 3 server if it's open.
Everything else (YouTube, Twitch, Discord...) stays on your normal internet and never uses phone data.
The pill keeps the list up to date by itself: a world you log into later gets added automatically.
Also prints which Oracle region your server should live in.
Usage: py windows\\make_routes_win.py              (detects everything)
       py windows\\make_routes_win.py sa-east-1    (old behaviour: every AWS range in that region)
Nothing here touches Tibia's process: it reads Windows' connection table by port, like netstat."""
import glob, ipaddress, json, os, re, subprocess, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLOUDFLARE = "172.65.0.0/16"  # Tibia's protected game addresses
GAME = ("Get-NetTCPConnection -State Established -RemotePort 7171,7172 -ErrorAction SilentlyContinue | "
        "% RemoteAddress")


_EC2 = []


def route_for(ip):
    """What to tunnel for a Tibia game server: the whole AWS block it sits in (e.g. 54.207.0.0/16), because
    Tibia gets a different address in its region on each login. Falls back to just the address."""
    a = ipaddress.ip_address(ip)
    if a in ipaddress.ip_network(CLOUDFLARE): return CLOUDFLARE
    if not _EC2:
        try:
            data = json.load(urllib.request.urlopen("https://ip-ranges.amazonaws.com/ip-ranges.json", timeout=10))
            _EC2[:] = [ipaddress.ip_network(p["ip_prefix"]) for p in data["prefixes"] if p["service"] == "EC2"]
        except (OSError, ValueError):
            return f"{ip}/32"
    nets = [n for n in _EC2 if a in n]
    return str(min(nets, key=lambda n: n.num_addresses)) if nets else f"{ip}/32"


def teamspeak_server():
    """The server TeamSpeak 3 last connected to, read from TeamSpeak's own log (TeamSpeak, not a game)."""
    logs = sorted(glob.glob(os.path.join(os.environ.get("APPDATA", ""), "TS3Client", "logs", "*.log")),
                  key=os.path.getmtime)
    if not logs: return None
    try:
        with open(logs[-1], "rb") as f:
            f.seek(max(0, os.path.getsize(logs[-1]) - 65536))
            hits = re.findall(rb"Initiating connection: (\d+\.\d+\.\d+\.\d+):\d+", f.read())
        return hits[-1].decode() if hits else None
    except OSError:
        return None


def main():
    if sys.argv[1:]:  # region(s) named: the old, broad list
        sys.exit(subprocess.run([sys.executable, os.path.join(ROOT, "make_routes.py")] + sys.argv[1:]).returncode)
    out = subprocess.run(["powershell", "-NoProfile", "-Command", GAME], capture_output=True, text=True).stdout
    ips = sorted({l.strip() for l in out.splitlines() if l.strip() and ":" not in l})
    if not ips:
        sys.exit("No Tibia game connection found. Log into a world and rerun, "
                 "or name the AWS region yourself, e.g.: py windows\\make_routes_win.py sa-east-1")
    sys.path.insert(0, ROOT)
    from make_routes import ORACLE
    data = json.load(urllib.request.urlopen("https://ip-ranges.amazonaws.com/ip-ranges.json"))
    ec2 = [(ipaddress.ip_network(p["ip_prefix"]), p["region"]) for p in data["prefixes"] if p["service"] == "EC2"]
    regions = sorted({reg for ip in ips for net, reg in ec2 if ipaddress.ip_address(ip) in net})
    routes = sorted({route_for(ip) for ip in ips} | {CLOUDFLARE})
    ts = teamspeak_server()
    if ts: routes.append(f"{ts}/32")
    with open(os.path.join(ROOT, "game-routes.txt"), "w") as f:
        f.write("\n".join(routes) + "\n")
    print(f"Wrote game-routes.txt: Tibia {' '.join(ips)}" + (f", TeamSpeak {ts}" if ts else ""))
    for r in regions:
        print(f"  {r} -> pick Oracle home region: {ORACLE.get(r, 'the Oracle region closest to ' + r)}")


if __name__ == "__main__":
    main()
