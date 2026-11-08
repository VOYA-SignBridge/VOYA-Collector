<#
Chuan bi MAY TRANG lam server SignBridge: cai nhung gi con thieu, mot lan chay.

Cach chay: chuot phai 0_CHUAN_BI_MAY_MOI.bat -> Run as administrator. Chay lai bao nhieu lan
cung duoc: thu nao da co thi bo qua.

Lam:
  1. Git, Python 3.12, Docker Desktop (qua winget) neu chua co
  2. Bat WSL2 (Docker Desktop can) neu chua co
  3. Kiem driver NVIDIA (KHONG tu cai - tai tu nvidia.com)
  4. HOI truoc khi dat che do nguon: khong ngu / khong ngu dong khi cam sac, gap nap khong lam gi
  5. Kiem o dia cho goi va ung dung
Khong dong vao du lieu, khong dong vao ban trien khai cu (neu co).
#>
$ErrorActionPreference = "Stop"
$Log = Join-Path $PSScriptRoot "chuan-bi-may-moi.log"
Start-Transcript -Path $Log -Append | Out-Null
function Step([string]$n, [string]$text) { Write-Host ""; Write-Host "[$n] $text" -ForegroundColor Cyan }
function Warn([string]$text) { Write-Host "  CANH BAO: $text" -ForegroundColor Yellow }
function Done([string]$text) { Write-Host "  $text" -ForegroundColor Green }
$needReboot = $false
$todo = @()

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Can chay voi quyen Administrator: chuot phai 0_CHUAN_BI_MAY_MOI.bat -> Run as administrator." -ForegroundColor Red
    Stop-Transcript | Out-Null; exit 1
}

# ------------------------------------------------------------------ 1
Step "1/5" "Phan mem: Git, Python, Docker Desktop"
$winget = Get-Command winget -ErrorAction SilentlyContinue
function Install-IfMissing([string]$label, [scriptblock]$present, [string]$id) {
    if (& $present) { Done "$label`: da co"; return }
    if (-not $winget) {
        Warn "$label chua co va may khong co winget -> cai tay ($id)."
        $script:todo += "Cai $label"
        return
    }
    Write-Host "  Cai $label ($id) ..."
    & winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0 -and -not (& $present)) { Warn "Cai $label that bai (ma $LASTEXITCODE) -> cai tay."; $script:todo += "Cai $label" }
    else { Done "$label`: da cai"; $script:needReboot = $true }
}
Install-IfMissing "Git" { [bool](Get-Command git -ErrorAction SilentlyContinue) -or (Test-Path "$env:ProgramFiles\Git\bin\git.exe") } "Git.Git"
Install-IfMissing "Python 3.12" {
    foreach ($c in @("python", "py")) {
        if (Get-Command $c -ErrorAction SilentlyContinue) {
            & $c -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) { return $true }
        }
    }
    return (Test-Path "$env:LocalAppData\Programs\Python\Python312\python.exe") -or (Test-Path "$env:ProgramFiles\Python312\python.exe")
} "Python.Python.3.12"
Install-IfMissing "Docker Desktop" { Test-Path "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe" } "Docker.DockerDesktop"

# ------------------------------------------------------------------ 2
Step "2/5" "WSL2 (Docker Desktop chay tren WSL2)"
& wsl.exe --status 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) { Done "WSL: da bat" }
else {
    Write-Host "  Bat WSL ..."
    & wsl.exe --install --no-distribution
    if ($LASTEXITCODE -eq 0) { Done "WSL: da bat (can khoi dong lai)"; $needReboot = $true }
    else { Warn "Khong bat duoc WSL (ma $LASTEXITCODE). Bat ao hoa (VT-x/SVM) trong BIOS roi chay lai."; $todo += "Bat WSL2" }
}

# ------------------------------------------------------------------ 3
Step "3/5" "Card do hoa NVIDIA"
$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($smi) {
    $gpu = (& nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader) -join "; "
    Done "GPU: $gpu"
} else {
    $card = (Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'NVIDIA' } | Select-Object -First 1).Name
    if ($card) { Warn "co card $card nhung chua co driver NVIDIA. Tai driver moi nhat cho card nay tai https://www.nvidia.com/Download/index.aspx roi cai."; $todo += "Cai driver NVIDIA" }
    else { Write-Host "  Khong thay card NVIDIA: huan luyen se chay CPU (cham hon nhieu)." }
}

# ------------------------------------------------------------------ 4
Step "4/5" "Che do nguon (server khong duoc ngu)"
$isLaptop = [bool](Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue)
Write-Host "  De nghi: khi CAM SAC thi khong bao gio ngu / ngu dong; gap nap may khong lam gi."
$answer = Read-Host "  Dat ngay? (c = co, Enter = bo qua)"
if ($answer.Trim().ToLower() -eq "c") {
    & powercfg /change standby-timeout-ac 0
    & powercfg /change hibernate-timeout-ac 0
    & powercfg /change monitor-timeout-ac 15
    if ($isLaptop) { & powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0 }
    & powercfg /setactive SCHEME_CURRENT
    Done "Da dat: khong ngu khi cam sac$(if ($isLaptop) { ', gap nap khong lam gi' })."
} else { Warn "Bo qua. Server ngu = site sap."; $todo += "Dat che do nguon khong ngu" }
$route = Get-NetRoute -DestinationPrefix 0.0.0.0/0 -ErrorAction SilentlyContinue | Sort-Object RouteMetric | Select-Object -First 1
$nic = if ($route) { Get-NetAdapter -InterfaceIndex $route.ifIndex -ErrorAction SilentlyContinue }
if ($nic -and $nic.MediaType -match '802.11') { Warn "may dang dung Wi-Fi; server nen cam day mang."; $todo += "Cam day mang" }

# ------------------------------------------------------------------ 5
Step "5/5" "O dia"
foreach ($d in Get-Volume | Where-Object { $_.DriveLetter -and $_.DriveType -eq 'Fixed' }) {
    Write-Host ("  {0}: trong {1:N0} GB / {2:N0} GB" -f $d.DriveLetter, ($d.SizeRemaining / 1GB), ($d.Size / 1GB))
}
Write-Host "  Can: ~60 GB trong cho goi (giai nen) + ung dung + Docker. Ung dung mac dinh dat o D:\SignBridge\app"
Write-Host "  (khong co o D thi dat o C:\SignBridge\app)."

Write-Host ""
if ($todo.Count) {
    Write-Host "CON PHAI LAM TAY:" -ForegroundColor Yellow
    $todo | Sort-Object -Unique | ForEach-Object { Write-Host "  - $_" }
}
Write-Host "TIEP THEO:" -ForegroundColor Green
if ($needReboot) { Write-Host "  1. KHOI DONG LAI MAY (vua cai phan mem / bat WSL)." }
Write-Host "  2. Mo Docker Desktop, dong y dieu khoan, doi bieu tuong cua no chuyen sang 'Engine running'."
Write-Host "     Trong Settings > Software updates: TAT tu dong tai/cai ban moi."
Write-Host "  3. Chuot phai 1_KHOI_PHUC_MAY_MOI.bat -> Run as administrator."
Stop-Transcript | Out-Null
