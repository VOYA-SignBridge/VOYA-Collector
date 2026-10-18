<#
Chuyen domain sang MAY MOI: cai connector Cloudflare Tunnel CU (cung tunnel, cung token).

DNS va route tren Cloudflare KHONG doi: domain -> tunnel -> http://localhost:80 cua may
dang chay connector. Vi vay chi can (1) tat connector may cu, (2) cai connector o day.
Hai may cung chay connector = Cloudflare chia request cho hai database rieng -> cam.

Chay: chuot phai 2_BAT_DOMAIN_MAY_MOI.bat -> Run as administrator.
#>
param([string]$PublicUrl = "")
$ErrorActionPreference = "Stop"
$Pack = $PSScriptRoot
function Fail([string]$text) { Write-Host ""; Write-Host "DUNG LAI: $text" -ForegroundColor Red; exit 1 }

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Fail "Can quyen Administrator (chuot phai -> Run as administrator)." }

if (-not $PublicUrl) {
    $manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $Pack "PACK_MANIFEST.json") | ConvertFrom-Json
    $PublicUrl = $manifest.source.public_url
}

Write-Host "[1/5] Ung dung tren may nay phai dang chay"
try { $local = Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 "http://127.0.0.1/api/v1/health" }
catch { Fail "http://127.0.0.1 chua chay. Chay 1_KHOI_PHUC_MAY_MOI.bat truoc." }
if ($local.StatusCode -ne 200) { Fail "Health check tra $($local.StatusCode)." }

Write-Host "[2/5] Xac nhan may cu da tat connector"
Write-Host "  Tren MAY CU phai chay TAT_MAY_CU.bat truoc (dung service Cloudflared + stack cu)."
$answer = Read-Host "  Go chinh xac: MAY CU DA TAT"
if ($answer -ne "MAY CU DA TAT") { Fail "Chua xac nhan. Khong lam gi." }

Write-Host "[3/5] Cloudflared"
if (Get-Service -Name Cloudflared -ErrorAction SilentlyContinue) {
    Fail "May nay da co service Cloudflared. Neu la cai cu: cloudflared service uninstall, roi chay lai."
}
$exe = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $exe -and (Test-Path "C:\Program Files (x86)\cloudflared\cloudflared.exe")) {
    $exe = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
}
if (-not $exe) {
    Write-Host "  Chua co cloudflared -> cai bang winget (Cloudflare.cloudflared)"
    & winget install --id Cloudflare.cloudflared -e
    $exe = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
    if (-not (Test-Path $exe)) { Fail "Cai cloudflared that bai; tai tu developers.cloudflare.com roi chay lai." }
}

Write-Host "[4/5] Cai connector cua tunnel hien co"
$tokenFile = Join-Path $Pack "10_cau-hinh-may-va-khoa\cloudflared\token"
if (Test-Path $tokenFile) { $token = (Get-Content -Raw $tokenFile).Trim() }
else {
    Write-Host "  Goi khong co token (may cu khong doc duoc). Lay o Cloudflare dashboard:"
    Write-Host "  Zero Trust -> Networks -> Tunnels -> tunnel hien co -> Configure -> Windows -> chep token."
    $token = (Read-Host "  Dan token vao day").Trim()
}
if ($token.Length -lt 50) { Fail "Token khong hop le." }
& $exe service install $token
if ($LASTEXITCODE -ne 0) { Fail "cloudflared service install that bai." }

Write-Host "[5/5] Doi tunnel ket noi va kiem tra domain"
$ready = $false
foreach ($i in 1..30) {
    try { if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "http://127.0.0.1:20241/ready").StatusCode -eq 200) { $ready = $true; break } } catch { }
    Start-Sleep -Seconds 2
}
if (-not $ready) { Write-Host "  CANH BAO: chua thay /ready; xem Services -> Cloudflared." -ForegroundColor Yellow }
$public = $false
foreach ($i in 1..12) {
    try { if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 15 $PublicUrl).StatusCode -eq 200) { $public = $true; break } } catch { }
    Start-Sleep -Seconds 5
}
if ($public) { Write-Host "XONG: $PublicUrl dang tro ve may nay." -ForegroundColor Green }
else { Fail "$PublicUrl chua tra 200. Kiem tra Cloudflare dashboard: tunnel phai Healthy, 1 connector." }
Write-Host "Kiem tra them qua 4G: dang nhap, du lieu cu, upload, camera, realtime, email dat lai mat khau."
