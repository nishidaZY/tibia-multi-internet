#!/bin/bash
# One-time setup on your Mac: tools, keys, game routes, and your free Oracle Cloud server.
# Usage: ./setup.sh ORACLE_REGION     e.g. ./setup.sh sa-saopaulo-1   (must be your Oracle *home* region)
# Safe to rerun: every step skips what is already done. Then: sudo ./install.sh
set -eu
cd "$(dirname "$0")"
REGION=${1:?"usage: ./setup.sh ORACLE_REGION  (your Oracle home region, e.g. sa-saopaulo-1, eu-frankfurt-1, us-ashburn-1)"}

command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
for p in wireguard-tools oci-cli; do brew list "$p" >/dev/null 2>&1 || brew install "$p"; done

# 1. which game servers go through the tunnel
[ -s game-routes.txt ] || python3 make_routes.py

# 2. WireGuard keys (Mac + server) and an SSH key to log into the server if you ever need to
for k in mac server; do
  [ -s $k.key ] || { (umask 077; wg genkey > $k.key); wg pubkey < $k.key > $k.pub; }
done
[ -s oracle_ssh ] || ssh-keygen -q -t ed25519 -N '' -C tibia-mi -f oracle_ssh

# 3. log into Oracle (opens your browser). Sessions last up to 24h; rerun this script after that.
export OCI_CLI_PROFILE=tibia OCI_CLI_AUTH=security_token SUPPRESS_LABEL_WARNING=True OCI_CLI_REGION=$REGION
oci session validate </dev/null >/dev/null 2>&1 || oci session authenticate --profile-name tibia --region "$REGION"
C=$(awk -F= '/^\[/{f=($0=="[tibia]")} f && $1~/^tenancy/{gsub(/ /,"",$2); print $2}' ~/.oci/config)
[ -n "$C" ] || { echo "Could not read your tenancy from ~/.oci/config"; exit 1; }
q() { oci "$@" --query data.id --raw-output; }

# 4. network: public subnet that only lets in SSH and the tunnel port (UDP 51821)
if [ ! -s oci.subnet ]; then
  echo "Creating network..."
  VCN=$(q network vcn create -c "$C" --cidr-block 10.0.0.0/16 --display-name tibia-mi --wait-for-state AVAILABLE)
  IGW=$(q network internet-gateway create -c "$C" --vcn-id "$VCN" --is-enabled true --display-name tibia-mi --wait-for-state AVAILABLE)
  RT=$(oci network vcn get --vcn-id "$VCN" --query 'data."default-route-table-id"' --raw-output)
  SL=$(oci network vcn get --vcn-id "$VCN" --query 'data."default-security-list-id"' --raw-output)
  oci network route-table update --rt-id "$RT" --force \
    --route-rules "[{\"destination\":\"0.0.0.0/0\",\"destinationType\":\"CIDR_BLOCK\",\"networkEntityId\":\"$IGW\"}]" >/dev/null
  oci network security-list update --security-list-id "$SL" --force --ingress-security-rules '[
    {"source":"0.0.0.0/0","protocol":"6","tcpOptions":{"destinationPortRange":{"min":22,"max":22}}},
    {"source":"0.0.0.0/0","protocol":"17","udpOptions":{"destinationPortRange":{"min":51821,"max":51821}}}]' >/dev/null
  q network subnet create -c "$C" --vcn-id "$VCN" --cidr-block 10.0.0.0/24 --display-name tibia-mi --wait-for-state AVAILABLE > oci.subnet
fi

# 5. server: try every Always Free shape in every availability domain until Oracle has capacity
if [ ! -s oci.instance ]; then
  awk -v f=server/dup_server.py '/__DUP_SERVER__/{while((getline l<f)>0)print l; next} 1' server/userdata.sh \
    | sed -e "s|__SERVER_KEY__|$(cat server.key)|" -e "s|__MAC_PUB__|$(cat mac.pub)|" | base64 > "${TMPDIR:-/tmp}/tibia-mi-userdata.b64"
  ADS=$(oci iam availability-domain list -c "$C" --query 'data[].name' --raw-output | tr -d '[]", ' | grep .)
  img() { oci compute image list -c "$C" --operating-system "Canonical Ubuntu" --operating-system-version 22.04 \
            --shape "$1" --sort-by TIMECREATED --sort-order DESC --query 'data[0].id' --raw-output; }
  IMG_ARM=$(img VM.Standard.A1.Flex); IMG_AMD=$(img VM.Standard.E2.1.Micro)
  launch() { q compute instance launch -c "$C" --availability-domain "$AD" --subnet-id "$(cat oci.subnet)" \
    --assign-public-ip true --display-name tibia-mi --ssh-authorized-keys-file oracle_ssh.pub \
    --metadata "{\"user_data\":\"$(cat "${TMPDIR:-/tmp}/tibia-mi-userdata.b64")\"}" "$@" 2>/dev/null | grep '^ocid1.instance' || true; }
  n=0
  while [ ! -s oci.instance ]; do
    n=$((n+1))
    for AD in $ADS; do
      ID=$(launch --shape VM.Standard.A1.Flex --shape-config '{"ocpus":1,"memoryInGBs":6}' --image-id "$IMG_ARM")
      [ -n "$ID" ] || ID=$(launch --shape VM.Standard.E2.1.Micro --image-id "$IMG_AMD")
      [ -n "$ID" ] && { echo "$ID" > oci.instance; break; }
    done
    [ -s oci.instance ] && break
    echo "$(date +%T) try $n: Oracle has no free capacity right now, retrying in 2 min (leave this open)"
    [ $((n % 20)) = 0 ] && { oci session refresh >/dev/null 2>&1 || true; }
    sleep 120
  done
  osascript -e 'display notification "Your Oracle server was created" with title "Multi-Internet"' 2>/dev/null || true
fi

# 6. its public IP
ID=$(cat oci.instance)
oci compute instance get --instance-id "$ID" --wait-for-state RUNNING >/dev/null
oci compute instance list-vnics --instance-id "$ID" --query 'data[0]."public-ip"' --raw-output > server.ip
echo "Server ready at $(cat server.ip). It finishes installing itself in ~3 minutes."
echo "Next: sudo ./install.sh"
