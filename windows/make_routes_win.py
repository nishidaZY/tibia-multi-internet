#!/usr/bin/env python3
"""Windows: find which AWS region your Tibia world runs in (be logged into a world),
then let ../make_routes.py write game-routes.txt for it.
Usage: py windows\\make_routes_win.py              (detects the region)
       py windows\\make_routes_win.py sa-east-1    (or name the AWS region(s) yourself)"""
import ipaddress, json, os, subprocess, sys, urllib.request

MAKE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "make_routes.py")
regions = sys.argv[1:]
if not regions:
    # the Windows Tibia game process is client.exe
    ps = ("Get-Process client,Tibia -ErrorAction SilentlyContinue | % { Get-NetTCPConnection -State Established "
          "-OwningProcess $_.Id -ErrorAction SilentlyContinue } | % RemoteAddress")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    ips = {ipaddress.ip_address(l.strip()) for l in out.splitlines() if l.strip()}
    data = json.load(urllib.request.urlopen("https://ip-ranges.amazonaws.com/ip-ranges.json"))
    regions = sorted({p["region"] for p in data["prefixes"] if p["service"] == "EC2"
                      for ip in ips if ip.version == 4 and ip in ipaddress.ip_network(p["ip_prefix"])})
    if not regions:
        sys.exit("No Tibia game connection found. Log into a world and rerun, "
                 "or pass the AWS region yourself, e.g.: py windows\\make_routes_win.py sa-east-1")
sys.exit(subprocess.run([sys.executable, MAKE] + regions).returncode)
