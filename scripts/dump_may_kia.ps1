<#
Gom dữ liệu của MÁY NÀY để hợp nhất sang máy khác — một thư mục, một file zip.

Dùng (PowerShell 5.1, chạy trong thư mục repo, Docker đang chạy):
    .\scripts\dump_may_kia.ps1
    .\scripts\dump_may_kia.ps1 -CoRoi D:\sample_uids_desktop.txt   # chỉ chép mẫu máy kia CHƯA có

Gom gì:
  1. dump Postgres (pg_dump -Fc)                        ~ vài MB
  2. samples/labels/signers.csv, consent_snapshot, manifests, mapping người ký
  3. bảng khoá (class_uid, sample_uid, signer, consent) để đối chiếu chỉ-điền
  4. npz + sidecar .json: TẤT CẢ, hoặc chỉ những sample_uid không có trong -CoRoi
  5. checkpoints realtime + models.json
Không gom: processed/splits, ảnh Docker, .env, video thô (bật -KemVideo nếu cần).
#>
param(
    [string]$CoRoi = "",          # tệp .txt, mỗi dòng một sample_uid máy kia đã có
    [switch]$KemVideo,            # chép cả dataset/raw_videos (lớn)
    [string]$Ra = ""              # thư mục đích; mặc định ..\voya_dump_<ngày giờ>
)
$ErrorActionPreference = "Stop"
$repo = (Get-Location).Path
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
if (-not $Ra) { $Ra = Join-Path (Split-Path $repo -Parent) "voya_dump_$stamp" }
New-Item -ItemType Directory -Force $Ra | Out-Null
function Say($m) { Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $m) }

# 1. Postgres
Say "1/5 dump Postgres"
docker exec voya_postgres pg_dump -U admin -d signdb -Fc -f /tmp/signdb_$stamp.dump
docker cp "voya_postgres:/tmp/signdb_$stamp.dump" (Join-Path $Ra "signdb_$stamp.dump")

# 2. Tệp nguồn sự thật
Say "2/5 CSV, manifest, mapping"
$csvDir = Join-Path $Ra "dataset"
New-Item -ItemType Directory -Force $csvDir | Out-Null
foreach ($f in "samples.csv","labels.csv","signers.csv","consent_snapshot.json") {
    $p = Join-Path $repo "dataset\$f"; if (Test-Path $p) { Copy-Item $p $csvDir }
}
if (Test-Path "$repo\dataset\manifests") { Copy-Item "$repo\dataset\manifests" $csvDir -Recurse }
New-Item -ItemType Directory -Force "$Ra\config" | Out-Null
foreach ($f in "config\legacy_signer_mapping.json","backend\app\sot\authorized_keys.json") {
    $p = Join-Path $repo $f; if (Test-Path $p) { Copy-Item $p "$Ra\config" }
}

# 3. Bảng khoá để đối chiếu
Say "3/5 bang khoa"
function Q($sql, $out) {
    docker exec voya_postgres psql -U admin -d signdb -At -F "," -c $sql | Out-File -Encoding utf8 (Join-Path $Ra $out)
}
Q "SELECT class_uid, slug, language, dialect, region, class_idx, deleted_at FROM classes ORDER BY 1" "classes_keys.csv"
Q "SELECT sample_uid, class_uid, user_id, signer_id, auth_user_id, review_status, file_path, created_at, deleted_at FROM samples ORDER BY 1" "samples_keys.csv"
Q "SELECT signer_id, display_name, external_user_id, is_active FROM signers ORDER BY 1" "signers_db.csv"
Q "SELECT signer_id, scope, kind, granted_at, withdrawn_at FROM signer_consents ORDER BY 1,2" "consents.csv"
Q "SELECT version, applied_at FROM schema_migrations ORDER BY applied_at DESC LIMIT 1" "schema_version.txt"
"$(git rev-parse --short HEAD)  $(git branch --show-current)" | Out-File -Encoding utf8 (Join-Path $Ra "git.txt")

# 4. npz + sidecar (chỉ phần thiếu nếu có -CoRoi)
Say "4/5 npz + sidecar"
$rows = Import-Csv (Join-Path $repo "dataset\samples.csv")
$da_co = @{}
if ($CoRoi -and (Test-Path $CoRoi)) {
    foreach ($u in Get-Content $CoRoi) { if ($u.Trim()) { $da_co[$u.Trim()] = $true } }
    Say ("   may kia da co {0} mau; chi chep phan con lai" -f $da_co.Count)
}
$featDir = Join-Path $Ra "features"; New-Item -ItemType Directory -Force $featDir | Out-Null
$n = 0; $thieu = 0
foreach ($r in $rows) {
    if ($da_co.ContainsKey($r.sample_uid)) { continue }
    $rel = ($r.file_path -replace '\\','/') -replace '^/?dataset/',''
    $src = Join-Path $repo ("dataset\" + ($rel -replace '/','\'))
    if (-not (Test-Path $src)) { $thieu++; continue }
    $dst = Join-Path $featDir ($rel -replace '/','\')
    New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
    Copy-Item $src $dst
    $side = [IO.Path]::ChangeExtension($src, ".json")
    if (Test-Path $side) { Copy-Item $side ([IO.Path]::ChangeExtension($dst, ".json")) }
    $n++
}
Say ("   da chep {0} mau, {1} mau khong co tep npz tren dia" -f $n, $thieu)
if ($KemVideo -and (Test-Path "$repo\dataset\raw_videos")) {
    Say "   kem video tho"; Copy-Item "$repo\dataset\raw_videos" "$Ra\raw_videos" -Recurse
}

# 5. Mô hình realtime
Say "5/5 checkpoints"
$ck = "$repo\backend\realtime_service\config"
New-Item -ItemType Directory -Force "$Ra\realtime" | Out-Null
if (Test-Path "$ck\checkpoints") { Copy-Item "$ck\checkpoints" "$Ra\realtime" -Recurse }
if (Test-Path "$ck\models.json") { Copy-Item "$ck\models.json" "$Ra\realtime" }

# Nén + mã băm
Say "nen"
$zip = "$Ra.zip"
Compress-Archive -Path "$Ra\*" -DestinationPath $zip -CompressionLevel Optimal -Force
$h = (Get-FileHash $zip -Algorithm SHA256).Hash
"$h  $(Split-Path $zip -Leaf)" | Out-File -Encoding ascii "$zip.sha256"
Say ("XONG: {0}  ({1:N1} MB)  sha256={2}" -f $zip, ((Get-Item $zip).Length/1MB), $h.Substring(0,16))
