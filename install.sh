#!/bin/bash
# Run after ./setup.sh, and again after any change here (or if your server IP changes).
# Copies the root-run files where only root can edit them, lets the app start/stop the tunnel
# without a password, builds the app and puts it in /Applications.
set -e
[ "$(id -u)" = 0 ] || { echo "Run with sudo: sudo ./install.sh"; exit 1; }
SRC="$(cd "$(dirname "$0")" && pwd)"; DST=/usr/local/tibia-mi; U=${SUDO_USER:?run via sudo}
for f in server.ip server.pub mac.key game-routes.txt; do
  [ -s "$SRC/$f" ] || { echo "Missing $f: run ./setup.sh first"; exit 1; }
done
install -d -o root -g wheel -m 755 $DST
install -o root -g wheel -m 755 "$SRC/tibia-guard.sh" "$SRC/dup_client.py" $DST/
install -o root -g wheel -m 644 "$SRC/server.ip" "$SRC/server.pub" "$SRC/game-routes.txt" $DST/
install -o root -g wheel -m 600 "$SRC/mac.key" $DST/
echo "$U ALL=(root) NOPASSWD: $DST/tibia-guard.sh, /usr/bin/pkill -TERM -f tibia-guard.sh" > /tmp/tibia-mi.sudoers
visudo -cf /tmp/tibia-mi.sudoers >/dev/null && install -o root -g wheel -m 440 /tmp/tibia-mi.sudoers /etc/sudoers.d/tibia-mi
APP=$(mktemp -d)/Multi-Internet.app
mkdir -p "$APP/Contents/MacOS" && cp "$SRC/app/Info.plist" "$APP/Contents/"
swiftc -O "$SRC/app/MultiInternet.swift" -o "$APP/Contents/MacOS/MultiInternet"
codesign -s - "$APP" 2>/dev/null || true
rm -rf /Applications/Multi-Internet.app && cp -R "$APP" /Applications/
echo "Installed. Open Multi-Internet from Applications (or Spotlight)."
