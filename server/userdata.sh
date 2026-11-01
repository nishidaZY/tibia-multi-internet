#!/bin/bash
# Runs once on the Oracle server at first boot (cloud-init). setup.sh fills in the __PLACEHOLDERS__.
set -e
apt-get update -y && DEBIAN_FRONTEND=noninteractive apt-get install -y wireguard iptables
echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-wg.conf && sysctl -p /etc/sysctl.d/99-wg.conf
NIC=$(ip route show default | awk '{print $5; exit}')
cat > /etc/wireguard/wg0.conf <<WG
[Interface]
Address = 10.66.0.1/24
ListenPort = 51820
PrivateKey = __SERVER_KEY__
PostUp = iptables -t nat -A POSTROUTING -o $NIC -j MASQUERADE; iptables -A FORWARD -i wg0 -j ACCEPT; iptables -A FORWARD -o wg0 -j ACCEPT
PostDown = iptables -t nat -D POSTROUTING -o $NIC -j MASQUERADE; iptables -D FORWARD -i wg0 -j ACCEPT; iptables -D FORWARD -o wg0 -j ACCEPT

[Peer]
PublicKey = __MAC_PUB__
AllowedIPs = 10.66.0.2/32
PersistentKeepalive = 1
WG
chmod 600 /etc/wireguard/wg0.conf
systemctl enable --now wg-quick@wg0

# Oracle Ubuntu images ship an iptables REJECT rule; open WireGuard + relay ports
iptables -I INPUT -p udp --dport 51820:51821 -j ACCEPT
iptables -I FORWARD 1 -i wg0 -j ACCEPT; iptables -I FORWARD 1 -o wg0 -j ACCEPT
netfilter-persistent save || true
cat > /usr/local/bin/dup_server.py <<'PY'
__DUP_SERVER__
PY
cat > /etc/systemd/system/dup.service <<'UNIT'
[Unit]
After=wg-quick@wg0.service
[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/dup_server.py
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload && systemctl enable --now dup
# auto-recover: kernel/system freeze -> hardware-style watchdog reboots; services come back on boot
echo softdog > /etc/modules-load.d/softdog.conf; modprobe softdog
mkdir -p /etc/systemd/system.conf.d && printf "[Manager]\nRuntimeWatchdogSec=30s\nRebootWatchdogSec=2min\n" > /etc/systemd/system.conf.d/watchdog.conf
systemctl daemon-reexec
