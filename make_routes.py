#!/usr/bin/env python3
"""Write game-routes.txt: every AWS EC2 prefix in the region(s) that host your Tibia world,
plus Cloudflare 172.65.0.0/16. Only these addresses go through the tunnel.
Usage: python3 make_routes.py              (be logged into a world: detects its region)
       python3 make_routes.py sa-east-1    (or name the AWS region(s) yourself)"""
import ipaddress, json, os, subprocess, sys, urllib.request

# closest Oracle Cloud region to each AWS region (where your server should live)
ORACLE = {"sa-east-1": "sa-saopaulo-1", "us-east-1": "us-ashburn-1", "us-east-2": "us-ashburn-1",
          "us-west-1": "us-sanjose-1", "us-west-2": "us-phoenix-1", "ca-central-1": "ca-toronto-1",
          "eu-central-1": "eu-frankfurt-1", "eu-west-1": "uk-london-1", "eu-west-2": "uk-london-1",
          "eu-west-3": "eu-paris-1", "eu-north-1": "eu-stockholm-1", "eu-south-1": "eu-milan-1",
          "ap-southeast-2": "ap-sydney-1", "ap-southeast-1": "ap-singapore-1", "ap-northeast-1": "ap-tokyo-1",
          "mx-central-1": "mx-queretaro-1"}

data = json.load(urllib.request.urlopen("https://ip-ranges.amazonaws.com/ip-ranges.json"))
ec2 = [(ipaddress.ip_network(p["ip_prefix"]), p["region"]) for p in data["prefixes"] if p["service"] == "EC2"]

regions = sys.argv[1:]
if not regions:
    # the macOS Tibia game process is called "client"
    out = subprocess.run(["lsof", "-nP", "-a", "-iTCP", "-sTCP:ESTABLISHED", "-c", "client", "-c", "Tibia"],
                         capture_output=True, text=True).stdout
    ips = set()
    for line in out.splitlines()[1:]:
        if "->" in line:
            ip = line.split("->")[1].split()[0].rsplit(":", 1)[0].strip("[]")
            ips.add(ipaddress.ip_address(ip))
    regions = sorted({reg for ip in ips for net, reg in ec2 if ip in net})
    if not regions:
        sys.exit("No Tibia game connection found. Log into a world and rerun, "
                 "or pass the AWS region yourself, e.g.: python3 make_routes.py sa-east-1")

nets = sorted({str(n) for n, reg in ec2 if reg in regions}) + ["172.65.0.0/16"]
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "game-routes.txt"), "w") as f:
    f.write("\n".join(nets) + "\n")
print(f"Wrote game-routes.txt ({len(nets)} ranges) for: {' '.join(regions)}")
for r in regions:
    print(f"  {r} -> pick Oracle home region: {ORACLE.get(r, 'the Oracle region closest to ' + r)}")
