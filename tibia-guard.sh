#!/bin/bash
# Tibia multi-internet: Tibia game traffic goes through a WireGuard tunnel to your own server,
# and every tunnel packet is sent over Wi-Fi AND iPhone at the same time (like ExitLag multi-internet).
# If one connection dies, the other copy is already arriving: no switch, no reconnect.
# Started by the Multi-Internet app (or by hand: sudo ./tibia-guard.sh, stop with Ctrl+C)
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER=$(cat "$DIR/server.ip")
LOCAL=51830
[ "$(id -u)" = 0 ] || { echo "Run with sudo"; exit 1; }
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH  # Homebrew on Apple Silicon / Intel

cleanup() {
  echo; echo "Stopping..."
  kill "$DUP" 2>/dev/null
  while read -r n; do route -q -n delete -net "$n" >/dev/null 2>&1; done < "$DIR/game-routes.txt"
  rm -f "/var/run/wireguard/$TUN.sock" /var/run/wireguard/tibia.name  # wireguard-go exits when its socket goes
  for s in "Wi-Fi" "iPhone USB"; do networksetup -setv6automatic "$s"; done 2>/dev/null
  echo "Normal internet restored."; exit 0
}
trap cleanup INT TERM

# 1. duplicator: listens on 127.0.0.1:$LOCAL, sends each packet out every live interface
python3 -u "$DIR/dup_client.py" "$SERVER" 51821 $LOCAL wifi iphone &
DUP=$!

# 2. tunnel, pointed at the duplicator
mkdir -p /var/run/wireguard
WG_TUN_NAME_FILE=/var/run/wireguard/tibia.name wireguard-go utun >/dev/null 2>&1
TUN=$(cat /var/run/wireguard/tibia.name)
wg set "$TUN" private-key "$DIR/mac.key" peer "$(cat "$DIR/server.pub")" \
  endpoint "127.0.0.1:$LOCAL" allowed-ips 0.0.0.0/0 persistent-keepalive 1
ifconfig "$TUN" inet 10.66.0.2 10.66.0.2 netmask 255.255.255.255 mtu 1280 up

# 3. only Tibia game servers go through the tunnel; Cloudflare blocks the login from datacenter IPs
# shortcut: game-routes.txt = AWS sa-east-1 EC2 + Cloudflare 172.65/16; add a prefix if a world IP isn't covered
while read -r n; do route -q -n add -net "$n" -interface "$TUN" >/dev/null; done < "$DIR/game-routes.txt"
# IPv6 would let the game bypass the tunnel
for s in "Wi-Fi" "iPhone USB"; do networksetup -setv6off "$s"; done 2>/dev/null
echo "Multi-internet up."
notify() { launchctl asuser "$(id -u "${SUDO_USER:-root}")" osascript -e "display notification \"$1\" with title \"Multi-Internet\"" 2>/dev/null; }
# server silent on every path for 8s (age >= 8) while normal internet works -> server problem: fall back to normal internet
server_dead() {
  python3 -c 'import json,sys; p=json.load(open("/var/run/tibia-mi.json"))["paths"]; sys.exit(0 if p and min(p.values()) >= 8 else 1)' 2>/dev/null \
    && ping -c1 -t2 -q 1.1.1.1 >/dev/null 2>&1
}
sleep 4
# run only while the app is open: app quit/crash -> tunnel goes down too
while kill -0 "$DUP" 2>/dev/null && pgrep -axq MultiInternet; do
  if server_dead; then
    notify "Server unreachable - switched to your normal internet (no backup now)"
    break
  fi
  sleep 2
done
cleanup
