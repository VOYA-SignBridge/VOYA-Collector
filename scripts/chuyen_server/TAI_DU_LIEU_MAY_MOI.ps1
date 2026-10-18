<#
Tai lai tren MAY MOI nhung du lieu KHONG mang theo goi vi tai lai duoc.

1_KHOI_PHUC_MAY_MOI.bat tu goi script nay o cuoi. Chay rieng duoc (chay lai bao nhieu lan cung duoc,
moi buoc chi tai thu con thieu):
  chuot phai 3_TAI_DU_LIEU_MAY_MOI.bat -> Run as administrator

Hai nguon:
  1. Google Drive: moi mau (.npz) va video tho co trong database ma thieu tep tren dia.
     Goi tac vu co san `app.sync_tasks.download_missing_files_to_local` trong container worker
     (doc storage_url cua tung dong, tai ve dung file_path). Goi chuyen server da mang theo
     dataset/, nen thuong khong thieu gi; buoc nay de phong goi bi bo dataset hoac tep loi.
  2. Video mau QIPEDC (qipedc.moet.gov.vn, 4.362 video, ~2,7 GB): scripts/tai_mau_qipedc.py,
     tai vao thu muc `qipedc_mau` CANH ung dung - dung cho cu ma cac script do dac va test tim.
     Bo qua bang -BoQuaQipedc. Lan sau chay lai se bo qua video da tai.

Khong tai ve: ban sao Drive (may moi dung chung Drive, cung file ID), anh Docker (dung tu ma nguon),
lich su git (clone tu GitHub khi can).
#>
param(
    [string]$AppRoot = "D:\SignBridge\app",
    [switch]$BoQuaQipedc,
    [switch]$BoQuaDrive,
    [int]$QipedcGioiHanMb = 2800
)
$ErrorActionPreference = "Stop"
if (-not $PSBoundParameters.ContainsKey('AppRoot') -and -not (Test-Path 'D:\')) { $AppRoot = 'C:\SignBridge\app' }
if (-not (Test-Path -LiteralPath (Join-Path $AppRoot ".env"))) {
    Write-Host "DUNG LAI: khong thay ung dung o $AppRoot. Chay 1_KHOI_PHUC_MAY_MOI.bat truoc, hoac dua -AppRoot." -ForegroundColor Red
    exit 1
}

function Step([string]$n, [string]$text) { Write-Host ""; Write-Host "[$n] $text" -ForegroundColor Cyan }
function Warn([string]$text) { Write-Host "  CANH BAO: $text" -ForegroundColor Yellow }

$python = $null
foreach ($candidate in @("python", "py")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        & $candidate -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { $python = $candidate; break }
    }
}

# ------------------------------------------------------------------ 1
Step "1/2" "Tai tu Google Drive cac mau va video con thieu tren dia"
if ($BoQuaDrive) {
    Write-Host "  Bo qua (-BoQuaDrive)."
} else {
    # `docker compose` trong thu muc ung dung: .env mang COMPOSE_PROJECT_NAME/COMPOSE_FILE
    # cua chinh lan khoi phuc nay, nen khong can biet ten container.
    Push-Location $AppRoot
    try {
        $code = "from app.sync_tasks import download_missing_files_to_local as t; print(t.apply().get())"
        & docker compose exec -T -w /app worker python -c $code
        if ($LASTEXITCODE -ne 0) { Warn "tai tu Drive loi (xem dong tren). Chay lai script nay sau khi kiem tra mang/Drive." }
        else { Write-Host "  Xong. Dong cuoi ben tren la so tep da tai / bo qua / loi." }
    } finally {
        Pop-Location
    }
}

# ------------------------------------------------------------------ 2
Step "2/2" "Tai video mau QIPEDC vao thu muc qipedc_mau canh ung dung"
if ($BoQuaQipedc) {
    Write-Host "  Bo qua (-BoQuaQipedc)."
} elseif (-not $python) {
    Warn "khong co Python 3.11+, bo qua QIPEDC. Cai Python roi chay lai 3_TAI_DU_LIEU_MAY_MOI.bat."
} else {
    $dich = Join-Path (Split-Path $AppRoot -Parent) "qipedc_mau"
    New-Item -ItemType Directory -Force -Path $dich | Out-Null
    & $python (Join-Path $AppRoot "scripts\tai_mau_qipedc.py") --thu-muc $dich --gioi-han-mb $QipedcGioiHanMb
    if ($LASTEXITCODE -ne 0) { Warn "tai QIPEDC dung giua chung (mang hoac may chu QIPEDC). Chay lai de tai tiep." }
    else { Write-Host "  Xong: $dich" }
}

Write-Host ""
Write-Host "XONG buoc tai du lieu." -ForegroundColor Green
