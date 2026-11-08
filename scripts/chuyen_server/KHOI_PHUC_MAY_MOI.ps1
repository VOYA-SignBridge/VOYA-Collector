<#
Khoi phuc SignBridge tren MAY MOI tu goi chuyen server, mot lan chay.

Script nay duoc chep vao GOC moi goi (SignBridge_ChuyenServer_<ngay>_<gio>/). Cach chay:
  (lan dau tren may trang) chuot phai 0_CHUAN_BI_MAY_MOI.bat -> Run as administrator -> khoi dong lai
  giai nen file .zip -> mo thu muc goi -> chuot phai 1_KHOI_PHUC_MAY_MOI.bat -> Run as administrator

No KHONG bat domain. Domain chi bat bang 2_BAT_DOMAIN_MAY_MOI.bat, SAU KHI trang chay
dung tren http://localhost va may cu da tat ket noi tunnel.

Neu may nay DA CO mot ban trien khai cu (container voya_*), buoc 3 sao luu TOAN BO DB cu
(pg_dumpall), ghi lai thong tin, roi DUNG ban cu de nhuong cong. Khong xoa container, volume
hay thu muc nao cua ban cu: quay lai duoc (xem QUAY_LAI_BAN_CU.txt trong thu muc du phong).

Moi buoc dung ngay khi loi; nhat ky ghi ra file .log canh thu muc goi.
#>
param(
    [string]$AppRoot = "D:\SignBridge\app",
    [string]$Project = "signbridge-ctu",
    [string]$PublicUrl = "",
    [switch]$NoGpu,
    [switch]$BoQuaQipedc
)
$ErrorActionPreference = "Stop"
# May khong co o D: dat ung dung o C (chi khi nguoi chay khong tu chon -AppRoot).
if (-not $PSBoundParameters.ContainsKey('AppRoot') -and -not (Test-Path 'D:\')) { $AppRoot = 'C:\SignBridge\app' }
$Pack = $PSScriptRoot
$Tools = Join-Path $Pack "00_cong-cu"
$Log = Join-Path (Split-Path $Pack -Parent) ("khoi-phuc_" + (Split-Path $Pack -Leaf) + ".log")
Start-Transcript -Path $Log -Append | Out-Null

function Step([string]$n, [string]$text) { Write-Host ""; Write-Host "[$n] $text" -ForegroundColor Cyan }
function Warn([string]$text) { Write-Host "  CANH BAO: $text" -ForegroundColor Yellow }
function Fail([string]$text) {
    Write-Host ""; Write-Host "DUNG LAI: $text" -ForegroundColor Red
    Write-Host "Nhat ky: $Log"; Stop-Transcript | Out-Null; exit 1
}
function Invoke-Py {
    & $script:Python @args
    if ($LASTEXITCODE -ne 0) { Fail "Lenh python that bai: $($args -join ' ')" }
}

# ------------------------------------------------------------------ 1
Step "1/9" "Kiem tra may moi"
$script:Python = $null
foreach ($candidate in @("python", "py")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        & $candidate -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { $script:Python = $candidate; break }
    }
}
if (-not $script:Python) { Fail "Can Python 3.11 tro len. Chay 0_CHUAN_BI_MAY_MOI.bat truoc (hoac cai tu python.org, tick 'Add to PATH')." }
Write-Host "  Python: OK ($script:Python)"
$osType = (& docker info --format "{{.OSType}}" 2>$null)
if ($LASTEXITCODE -ne 0 -or $osType -ne "linux") { Fail "Docker Desktop chua chay (hoac khong o che do Linux containers). Mo Docker Desktop, doi bieu tuong xanh, chay lai." }
Write-Host "  Docker: OK (linux)"
if (Test-Path -LiteralPath $AppRoot) { Fail "$AppRoot da ton tai. Chon -AppRoot moi; script khong ghi de." }
$parent = Split-Path $AppRoot -Parent
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$tunnel = Test-NetConnection region1.v2.argotunnel.com -Port 7844 -WarningAction SilentlyContinue
if ($tunnel.TcpTestSucceeded) { Write-Host "  Ra mang Cloudflare Tunnel (7844): OK" }
else { Warn "khong ra duoc cong 7844 - domain se khong bat duoc tu may nay." }
# Server ngu hoac mat Wi-Fi = site sap (16-17/10/2026 tung bi nham la loi DNS cua Docker).
$route = Get-NetRoute -DestinationPrefix 0.0.0.0/0 -ErrorAction SilentlyContinue | Sort-Object RouteMetric | Select-Object -First 1
$nic = if ($route) { Get-NetAdapter -InterfaceIndex $route.ifIndex -ErrorAction SilentlyContinue }
if ($nic -and $nic.MediaType -match '802.11') { Warn "may dang dung Wi-Fi; server nen cam day mang." }
if ($route -and $route.NextHop -match '^(172\.20\.10\.|192\.168\.43\.)') { Warn "gateway $($route.NextHop) la diem phat tu dien thoai." }
if (Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue) {
    Warn "day la laptop. 0_CHUAN_BI_MAY_MOI.bat da hoi ve che do nguon; neu bo qua, chay voi quyen admin:"
    Write-Host "    powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0"
    Write-Host "    powercfg /change standby-timeout-ac 0"
    Write-Host "    powercfg /change hibernate-timeout-ac 0"
    Write-Host "    powercfg /setactive SCHEME_CURRENT"
}

# ------------------------------------------------------------------ 2
Step "2/9" "Kiem tra SHA-256 moi file trong goi"
Invoke-Py (Join-Path $Tools "migration_pack.py") verify $Pack
$manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $Pack "PACK_MANIFEST.json") | ConvertFrom-Json
if (-not $PublicUrl) { $PublicUrl = $manifest.source.public_url }
if (-not $PublicUrl) { Fail "Khong biet domain; chay lai voi -PublicUrl https://..." }
Write-Host "  Domain: $PublicUrl"

# ------------------------------------------------------------------ 3
Step "3/9" "Ban trien khai cu tren may nay (du phong)"
# Container cua ban cu mang ten voya_* (CONTAINER_PREFIX mac dinh). Ban moi dat ten theo
# project moi ($Project) va volume rieng, nen KHONG dung vao DB/volume cua ban cu - chi can
# dung ban cu de nhuong cong 80. Schema cu khac schema moi cung khong sao: hai DB tach han.
# Template KHONG chua dau ngoac kep: PowerShell 5.1 lam roi ngoac kep khi truyen cho docker.
# Thu muc cua ban cu doc tu nhan compose qua docker inspect (JSON).
$old = @(& docker ps -a --format "{{.Names}}|{{.State}}|{{.Image}}" 2>$null | Where-Object { $_ -match '^voya_' } |
         ForEach-Object {
             $name = ($_ -split '\|')[0]
             $labels = (& docker inspect --format "{{json .Config.Labels}}" $name) | ConvertFrom-Json
             "$_|" + $labels.'com.docker.compose.project.working_dir'
         })
if ($old.Count -eq 0) {
    Write-Host "  Khong co ban cu (khong co container voya_*)."
} else {
    Write-Host "  Tim thay ban trien khai cu:"
    $old | ForEach-Object { Write-Host "    $_" }
    $stamp = Get-Date -Format "yyyyMMdd_HHmm"
    $bk = Join-Path $parent ("du_phong_ban_cu_" + $stamp)
    Write-Host ""
    Write-Host "  Se lam: (1) sao luu toan bo DB cu vao $bk" -ForegroundColor Yellow
    Write-Host "          (2) ghi lai danh sach container/volume/thu muc cua ban cu" -ForegroundColor Yellow
    Write-Host "          (3) DUNG cac container cu (khong xoa container, volume hay thu muc nao)" -ForegroundColor Yellow
    $answer = Read-Host "  Go CAT BAN CU de tiep tuc (Enter = huy)"
    if ($answer.Trim().ToUpper() -ne "CAT BAN CU") { Fail "Da huy. Ban cu van chay nguyen ven." }
    New-Item -ItemType Directory -Force -Path $bk | Out-Null
    $old | Set-Content -Encoding UTF8 (Join-Path $bk "containers.txt")
    $pgs = @($old | ForEach-Object { ($_ -split '\|')[0] } | Where-Object { $_ -match 'postgres' -and $_ -notmatch 'backup' })
    foreach ($pg in $pgs) {
        & docker start $pg | Out-Null
        $ready = $false
        foreach ($i in 1..30) {
            & docker exec $pg sh -c 'pg_isready -q -U $POSTGRES_USER' 2>$null
            if ($LASTEXITCODE -eq 0) { $ready = $true; break }
            Start-Sleep -Seconds 2
        }
        if (-not $ready) { Fail "Postgres cu ($pg) khong len -> khong sao luu duoc, KHONG dung ban cu." }
        # So lieu de so voi goi (schema cu co the thieu bang: chi doc, loi thi bo qua).
        $sql = "select 'mau=' || count(*) || ' moi_nhat=' || coalesce(max(created_at)::text, '-') from samples;"
        $stats = $sql | & docker exec -i $pg sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB -tA' 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $stats) { $stats = "khong doc duoc bang samples (schema khac)" }
        Write-Host "  DB cu ($pg): $stats"
        "$pg : $stats" | Add-Content -Encoding UTF8 (Join-Path $bk "so_lieu_ban_cu.txt")
        & docker exec $pg sh -c 'pg_dumpall -U $POSTGRES_USER -f /tmp/voya_du_phong.sql'
        if ($LASTEXITCODE -ne 0) { Fail "pg_dumpall ban cu that bai -> KHONG dung ban cu." }
        $dump = Join-Path $bk ($pg + "_pg_dumpall.sql")
        & docker cp "${pg}:/tmp/voya_du_phong.sql" $dump
        if ($LASTEXITCODE -ne 0 -or (Get-Item $dump).Length -lt 1024) { Fail "Khong chep duoc ban sao luu DB cu -> KHONG dung ban cu." }
        & docker exec $pg rm -f /tmp/voya_du_phong.sql | Out-Null
        Write-Host ("  Sao luu DB cu: {0} ({1:N1} MB)" -f $dump, ((Get-Item $dump).Length / 1MB))
    }
    $projects = @($old | ForEach-Object { ($_ -split '\|')[3] } | Where-Object { $_ } | Sort-Object -Unique)
    foreach ($dir in $projects) {
        "thu muc ban cu: $dir" | Add-Content -Encoding UTF8 (Join-Path $bk "containers.txt")
        $envFile = Join-Path $dir ".env"
        if (Test-Path -LiteralPath $envFile) { Copy-Item -LiteralPath $envFile (Join-Path $bk "env_ban_cu.txt") }
    }
    & docker volume ls --format "{{.Name}}" | Set-Content -Encoding UTF8 (Join-Path $bk "volumes.txt")
    $names = @($old | ForEach-Object { ($_ -split '\|')[0] })
    & docker stop -t 120 @names | Out-Null
    @(
        "QUAY LAI BAN CU (neu ban moi khong chay duoc):",
        "  1. Dung ban moi: mo thu muc $AppRoot, chay: docker compose stop",
        "  2. Bat lai ban cu: docker start $($names -join ' ')",
        "     (hoac trong thu muc ban cu: docker compose up -d)",
        "Du lieu ban cu KHONG bi xoa: container, volume va thu muc van con nguyen.",
        "Ban sao luu DB cu: cac file *_pg_dumpall.sql trong thu muc nay.",
        "",
        "NEU ban cu co mau MOI hon ngay tao goi ($($manifest.created_at)): xem so_lieu_ban_cu.txt.",
        "Can hop nhat phan du lieu moi do vao ban moi - gui thu muc nay cho nguoi phu trach."
    ) | Set-Content -Encoding UTF8 (Join-Path $bk "QUAY_LAI_BAN_CU.txt")
    Write-Host "  Da dung ban cu. Du phong + cach quay lai: $bk" -ForegroundColor Green
}
if (Get-NetTCPConnection -LocalPort 80 -State Listen -ErrorAction SilentlyContinue) {
    Fail "Cong 80 van bi chiem (khong phai container voya_*). Tat IIS/Apache/nginx dang chay roi chay lai."
}
Write-Host "  Cong 80: trong"

# ------------------------------------------------------------------ 4
Step "4/9" "Do GPU"
$gpuArgs = @()
if (-not $NoGpu -and (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    & docker run --rm --gpus all alpine:3.20 true 2>$null
    if ($LASTEXITCODE -eq 0) { $gpuArgs = @("--gpu"); Write-Host "  GPU: Docker dung duoc card NVIDIA -> trainer chay GPU" }
    else { Warn "co card nhung Docker chua cap duoc -> chay CPU" }
} else { Write-Host "  GPU: khong dung" }

# ------------------------------------------------------------------ 5
Step "5/9" "Nap Docker images tu goi (khong can tai torch/CUDA tu mang)"
$images = Join-Path $Pack "06_docker-images\images.tar"
$useLocal = @()
if (Test-Path -LiteralPath $images) {
    & docker load -i $images
    if ($LASTEXITCODE -ne 0) { Warn "docker load loi -> buoc sau se dung lai image tu ma nguon (lau, can mang)." }
    else { $useLocal = @("--use-local-images"); Write-Host "  Da nap images tu goi." }
} else { Warn "goi khong co images.tar -> buoc sau se dung image tu ma nguon (lau, can mang)." }

# ------------------------------------------------------------------ 6
Step "6/9" "Khoi phuc database, file, volume va bat ung dung"
$bundle = Join-Path $Pack "01_ung-dung-va-database"
Invoke-Py (Join-Path $Tools "deploy.py") --restore $bundle --root $AppRoot --project $Project `
    --public-url $PublicUrl --allow-downtime --accept-external-storage @gpuArgs @useLocal

# ------------------------------------------------------------------ 7
Step "7/9" "Khoi phuc lich su Git, lich su backup, video canh repo, khoa SOT"
Invoke-Py (Join-Path $Tools "migration_pack.py") restore-extras $Pack --root $AppRoot --no-images

# ------------------------------------------------------------------ 8
Step "8/9" "Kiem tra trang chay tren may nay"
$ok = $false
foreach ($i in 1..30) {
    try {
        $home_ = Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 "http://127.0.0.1/"
        $api = Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 "http://127.0.0.1/api/v1/health"
        if ($home_.StatusCode -eq 200 -and $api.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
    Start-Sleep -Seconds 10
}
if (-not $ok) { Fail "Trang chua tra 200 tren http://127.0.0.1 sau 5 phut. Xem: docker compose ps (trong $AppRoot)" }
Write-Host "  http://127.0.0.1/ va /api/v1/health: 200"

# ------------------------------------------------------------------ 8b
Step "8b/9" "Tai lai du lieu khong mang theo goi (mau/video thieu tu Drive, video mau QIPEDC)"
# Loi o day khong dung khoi phuc: ung dung da chay; chay lai 3_TAI_DU_LIEU_MAY_MOI.bat sau.
$taiArgs = @{ AppRoot = $AppRoot }
if ($BoQuaQipedc) { $taiArgs.BoQuaQipedc = $true }
try { & (Join-Path $Pack "TAI_DU_LIEU_MAY_MOI.ps1") @taiArgs }
catch { Warn "tai du lieu loi: $($_.Exception.Message). Chay lai 3_TAI_DU_LIEU_MAY_MOI.bat." }

# ------------------------------------------------------------------ 9
Step "9/9" "Van hanh: tu bat sau khoi dong, canh gac 30 phut, loi tat tren Desktop"
$voya = Join-Path $AppRoot "scripts\voya.py"
# `start`: ghi moc image cho canh gac (may moi chua co lan trien khai nao de so)
# va xoa co "dung co chu y" neu con sot.
& $script:Python $voya start
$env:VOYA_CONFIRMED = "co"
& $script:Python $voya autostart install
Remove-Item Env:\VOYA_CONFIRMED -ErrorAction SilentlyContinue
$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell
foreach ($item in @(@("VOYA - Bang dieu khien", "VOYA_UI.bat"), @("VOYA - Menu lenh", "VOYA.bat"))) {
    $lnk = $shell.CreateShortcut((Join-Path $desktop ($item[0] + ".lnk")))
    $lnk.TargetPath = Join-Path $AppRoot $item[1]
    $lnk.WorkingDirectory = $AppRoot
    $lnk.Save()
}
Write-Host "  Da tao 2 loi tat tren Desktop va 2 tac vu Windows (tu bat stack, canh gac 30 phut)."

Write-Host ""
Write-Host "XONG: ung dung chay tren may nay, CHUA co domain." -ForegroundColor Green
Write-Host "Tiep theo:"
Write-Host "  1. Mo http://localhost , dang nhap, xem du lieu cu, video, model."
Write-Host "  2. Tren MAY CU: chay scripts\chuyen_server\TAT_MAY_CU.bat (tat tunnel + stack cu)."
Write-Host "  3. Tren may nay: chuot phai 2_BAT_DOMAIN_MAY_MOI.bat -> Run as administrator."
Write-Host "CAN LAM TAY (thiet lap Windows, script khong tu doi):" -ForegroundColor Yellow
Write-Host "  - Tu dang nhap sau khi khoi dong lai: chay netplwiz, bo dau 'Users must enter a user name...'"
Write-Host "  - Docker Desktop > Settings > Software updates: TAT tu dong tai/cai ban moi"
Stop-Transcript | Out-Null
