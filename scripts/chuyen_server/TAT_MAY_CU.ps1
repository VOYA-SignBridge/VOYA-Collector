<#
Chay tren MAY CU, SAU KHI da tao goi cuoi (migration_pack.py create ... --keep-stopped):
tat connector Cloudflare Tunnel va dung stack cu, de may moi nhan domain.

  TAT_MAY_CU.bat            tat (service Cloudflared -> Disabled, docker compose stop)
  TAT_MAY_CU.bat -HoanTac   bat lai may cu (quay ve neu may moi loi TRUOC KHI no co du lieu moi)

Khong xoa gi: khong `down`, khong xoa volume, khong go tunnel/DNS, khong doi token.
#>
param([switch]$HoanTac)
$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
function Fail([string]$text) { Write-Host ""; Write-Host "DUNG LAI: $text" -ForegroundColor Red; exit 1 }

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Fail "Can quyen Administrator (chuot phai -> Run as administrator)." }

if ($HoanTac) {
    Write-Host "Bat lai may cu..."
    Set-Service -Name Cloudflared -StartupType Automatic
    Start-Service -Name Cloudflared
    Push-Location $Repo
    & docker compose up -d   # COMPOSE_FILE trong .env giu dung overlay prod/gpu
    Pop-Location
    Write-Host "May cu da chay lai. NHO: may moi phai tat connector truoc (cloudflared service uninstall)." -ForegroundColor Yellow
    exit 0
}

Write-Host "Se TAT may cu: service Cloudflared (Disabled, khong tu bat lai khi reboot) va toan bo container."
$answer = Read-Host "Go chinh xac: TAT MAY CU"
if ($answer -ne "TAT MAY CU") { Fail "Chua xac nhan. Khong lam gi." }

Stop-Service -Name Cloudflared
Set-Service -Name Cloudflared -StartupType Disabled
Write-Host "  Cloudflared: da dung, Disabled"
Push-Location $Repo
& docker compose stop --timeout 300
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { Fail "docker compose stop loi; kiem tra Docker Desktop." }
Write-Host "  Stack cu: da dung (du lieu va volume con nguyen)"
Write-Host "XONG. Tren may moi chay 2_BAT_DOMAIN_MAY_MOI.bat." -ForegroundColor Green
