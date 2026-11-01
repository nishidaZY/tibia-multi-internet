# One-time setup on Windows: tools, keys, game routes, your free Oracle Cloud server, and a desktop shortcut.
# Usage (PowerShell, in the project folder):
#   powershell -ExecutionPolicy Bypass -File windows\setup.ps1 sa-saopaulo-1     (your Oracle *home* region)
# Already have a server from the Mac version? Copy server.ip, server.pub, mac.key and game-routes.txt
# into the project folder and run it without a region: Oracle is skipped.
# Safe to rerun: every step skips what is already done.
param([string]$Region)
$ErrorActionPreference = "Continue"  # native tools write to stderr; we check $LASTEXITCODE instead
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
function Save($name, $text) { [IO.File]::WriteAllText((Join-Path $Root $name), $text) }  # UTF-8, no BOM
function Has($name) { (Test-Path $name) -and (Get-Item $name).Length -gt 0 }
function Fail($msg) { Write-Host $msg -ForegroundColor Red; exit 1 }
function WingetInstall($id) {
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { Fail "Install $id by hand (winget not found), then rerun." }
  winget install -e --id $id --accept-source-agreements --accept-package-agreements
}

# 1. tools: Python (runs the app), WireGuard (the tunnel), OpenSSH (built into Windows 10/11)
$py = (Get-Command py -ErrorAction SilentlyContinue).Source
if (-not $py) { WingetInstall Python.Python.3.12; Fail "Python installed. Close PowerShell, open it again and rerun this." }
$wgDir = Join-Path $env:ProgramFiles "WireGuard"
if (-not (Test-Path "$wgDir\wg.exe")) { WingetInstall WireGuard.WireGuard }
if (-not (Test-Path "$wgDir\wg.exe")) { Fail "WireGuard not found in $wgDir. Install it from https://www.wireguard.com/install/ and rerun." }
$wg = "$wgDir\wg.exe"

# 2. which game servers go through the tunnel
if (-not (Has game-routes.txt)) {
  & $py windows\make_routes_win.py
  if ($LASTEXITCODE) { exit 1 }
}

# 3. WireGuard keys for this PC (mac.key: same file name as the Mac version, so the server needs no change)
if (-not (Has mac.key)) {
  $k = (& $wg genkey).Trim(); Save mac.key "$k`n"; Save mac.pub ((($k | & $wg pubkey) | Out-String).Trim() + "`n")
}

# 4-6. the Oracle server, unless you already have one
if (-not ((Has server.ip) -and (Has server.pub))) {
  if (-not $Region) { Fail "Pass your Oracle home region, e.g.: powershell -ExecutionPolicy Bypass -File windows\setup.ps1 sa-saopaulo-1" }
  if (-not (Has server.key)) {
    $k = (& $wg genkey).Trim(); Save server.key "$k`n"; Save server.pub ((($k | & $wg pubkey) | Out-String).Trim() + "`n")
  }
  if (-not (Has oracle_ssh)) { Start-Process ssh-keygen -ArgumentList '-q -t ed25519 -N "" -C tibia-mi -f oracle_ssh' -Wait -NoNewWindow }
  if (-not (Has oracle_ssh)) { Fail "ssh-keygen missing: Settings > System > Optional features > add OpenSSH Client, then rerun." }

  # Oracle's command line tool, in its own folder so it can't clash with anything
  $oci = "$PSScriptRoot\.venv\Scripts\oci.exe"
  if (-not (Test-Path $oci)) {
    & $py -m venv "$PSScriptRoot\.venv"; & "$PSScriptRoot\.venv\Scripts\python.exe" -m pip install -q oci-cli
  }
  $env:OCI_CLI_PROFILE = "tibia"; $env:OCI_CLI_AUTH = "security_token"; $env:SUPPRESS_LABEL_WARNING = "True"; $env:OCI_CLI_REGION = $Region
  function Oci { $j = (& $oci @args 2>$null) -join "`n"; if ($LASTEXITCODE -or -not $j) { return $null }; $j | ConvertFrom-Json }
  function Json($obj) { $f = [IO.Path]::GetTempFileName(); [IO.File]::WriteAllText($f, (ConvertTo-Json -InputObject $obj -Depth 6 -Compress)); "file://$f" }

  # log into Oracle (opens your browser). Sessions last up to 24h; rerun this script after that.
  & $oci session validate 2>$null | Out-Null
  if ($LASTEXITCODE) { & $oci session authenticate --profile-name tibia --region $Region }
  $cfg = Get-Content "$HOME\.oci\config"; $in = $false; $C = $null
  foreach ($l in $cfg) { if ($l -match '^\[') { $in = ($l -eq '[tibia]') } elseif ($in -and $l -match '^tenancy\s*=\s*(\S+)') { $C = $Matches[1] } }
  if (-not $C) { Fail "Could not read your tenancy from $HOME\.oci\config" }

  # network: public subnet that only lets in SSH and the tunnel port (UDP 51821)
  if (-not (Has oci.subnet)) {
    Write-Host "Creating network..."
    $VCN = (Oci network vcn create -c $C --cidr-block 10.0.0.0/16 --display-name tibia-mi --wait-for-state AVAILABLE).data
    $IGW = (Oci network internet-gateway create -c $C --vcn-id $VCN.id --is-enabled true --display-name tibia-mi --wait-for-state AVAILABLE).data.id
    if (-not $IGW) { Fail "Could not create the network (Oracle login expired? rerun)" }
    Oci network route-table update --rt-id $VCN.'default-route-table-id' --force --route-rules (Json @(
      @{destination = "0.0.0.0/0"; destinationType = "CIDR_BLOCK"; networkEntityId = $IGW })) | Out-Null
    Oci network security-list update --security-list-id $VCN.'default-security-list-id' --force --ingress-security-rules (Json @(
      @{source = "0.0.0.0/0"; protocol = "6"; tcpOptions = @{destinationPortRange = @{min = 22; max = 22 } } },
      @{source = "0.0.0.0/0"; protocol = "17"; udpOptions = @{destinationPortRange = @{min = 51821; max = 51821 } } })) | Out-Null
    $sub = (Oci network subnet create -c $C --vcn-id $VCN.id --cidr-block 10.0.0.0/24 --display-name tibia-mi --wait-for-state AVAILABLE).data.id
    if (-not $sub) { Fail "Could not create the subnet" }
    Save oci.subnet "$sub`n"
  }

  # server: try every Always Free shape in every availability domain until Oracle has capacity
  if (-not (Has oci.instance)) {
    $lf = { param($f) ((Get-Content $f -Raw) -replace "`r`n", "`n") }  # git on Windows may check files out with CRLF
    $ud = (& $lf server\userdata.sh).Replace("__DUP_SERVER__", (& $lf server\dup_server.py).TrimEnd("`n"))
    $ud = $ud.Replace("__SERVER_KEY__", (Get-Content server.key -Raw).Trim()).Replace("__MAC_PUB__", (Get-Content mac.pub -Raw).Trim())
    $meta = Json @{user_data = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($ud)) }
    $ADs = (Oci iam availability-domain list -c $C).data.name
    function Img($shape) { (Oci compute image list -c $C --operating-system "Canonical Ubuntu" --operating-system-version 22.04 --shape $shape --sort-by TIMECREATED --sort-order DESC).data[0].id }
    $imgArm = Img VM.Standard.A1.Flex; $imgAmd = Img VM.Standard.E2.1.Micro
    $arm = Json @{ocpus = 1; memoryInGBs = 6 }
    $subnet = (Get-Content oci.subnet -Raw).Trim()
    $n = 0
    while (-not (Has oci.instance)) {
      $n++
      foreach ($AD in $ADs) {
        $common = @("compute", "instance", "launch", "-c", $C, "--availability-domain", $AD, "--subnet-id", $subnet, "--assign-public-ip", "true",
          "--display-name", "tibia-mi", "--ssh-authorized-keys-file", "oracle_ssh.pub", "--metadata", $meta)
        $r = Oci @common --shape VM.Standard.A1.Flex --shape-config $arm --image-id $imgArm
        if (-not $r) { $r = Oci @common --shape VM.Standard.E2.1.Micro --image-id $imgAmd }
        if ($r.data.id) { Save oci.instance "$($r.data.id)`n"; break }
      }
      if (Has oci.instance) { break }
      Write-Host "$(Get-Date -Format T) try ${n}: Oracle has no free capacity right now, retrying in 2 min (leave this open)"
      if ($n % 20 -eq 0) { & $oci session refresh 2>$null | Out-Null }
      Start-Sleep 120
    }
  }

  # its public IP
  $ID = (Get-Content oci.instance -Raw).Trim()
  Oci compute instance get --instance-id $ID --wait-for-state RUNNING | Out-Null
  $ip = (Oci compute instance list-vnics --instance-id $ID).data[0].'public-ip'
  if (-not $ip) { Fail "Could not read the server's IP; rerun in a minute" }
  Save server.ip "$ip`n"
  Write-Host "Server ready at $ip. It finishes installing itself in ~3 minutes."
}

# 7. desktop shortcut that starts the app without a console window
$pyw = Join-Path (Split-Path (& $py -c "import sys; print(sys.executable)")) "pythonw.exe"
$lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "Multi-Internet.lnk"))
$lnk.TargetPath = $pyw; $lnk.Arguments = "`"$PSScriptRoot\multi_internet.pyw`""; $lnk.WorkingDirectory = $PSScriptRoot
$lnk.IconLocation = "$wgDir\wireguard.exe,0"; $lnk.Save()
Write-Host "Done. Open Multi-Internet from your desktop." -ForegroundColor Green
