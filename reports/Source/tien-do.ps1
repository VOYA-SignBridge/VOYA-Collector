# Tiến độ các thí nghiệm đang chạy.
#
#   cd E:\VOYA\VOYA-Collector
#   .\reports\tien-do.ps1
#
# Đọc thẳng các file *_raw.txt nên không cần vào container, không cần Docker
# đang chạy. "IM LẶNG" nghĩa là file không được ghi thêm trong 10 phút — hoặc
# đã xong, hoặc đã chết.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# Tổng số lần chạy mong đợi của từng thí nghiệm. Không có trong bảng này thì
# chỉ hiện số đã xong, không hiện phần trăm.
$expected = @{
    'budget_grid_hoa_de_budget_v13_bigru_attention_raw.txt' = 1368
    'budget_grid_hoa_de_budget_v13_hdgcn_raw.txt'           = 1368
    'budget_grid_hoa_de_budget_v2_tcn_raw.txt'              = 936
    'loso_hoa_de_loso_v11_raw.txt'                          = 120
    'loso_alphabet_loso_v13_raw.txt'                        = 90
    'matched_hoa_de_matched_leak_v13_raw.txt'               = 240
    'matched_2x2_hoa_de_matched_leak_v13_raw.txt'           = 240
    'motion_ctl_v13_bigru_attention_raw.txt'                = 648
    'scaling_3d_v14_bigru_attention_raw.txt'                = 3402
}

$files = Get-ChildItem 'reports\*_raw.txt' -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime -Descending

if (-not $files) { Write-Output 'Khong tim thay file ket qua nao trong reports\'; exit }

Write-Output ''
Write-Output ('{0,-46} {1,13} {2,6}  {3}' -f 'THI NGHIEM', 'TIEN DO', 'LOI', 'TRANG THAI')
Write-Output ('-' * 92)

foreach ($f in $files) {
    $done = @(Select-String -Path $f.FullName -Pattern 'seed=\d+ [\d.]').Count
    if ($done -eq 0) { continue }
    $fail = @(Select-String -Path $f.FullName -Pattern 'FAILED').Count
    $mins = [math]::Round(((Get-Date) - $f.LastWriteTime).TotalMinutes, 0)

    $total = $expected[$f.Name]
    if ($total) {
        $prog = '{0}/{1} ({2}%)' -f $done, $total, [math]::Round(100 * $done / $total)
    } else {
        $prog = "$done"
    }

    if ($mins -lt 10) {
        $state = 'DANG CHAY'
    } elseif ($total -and $done -ge $total) {
        $state = 'XONG'
    } elseif ($total) {
        # Chua du so lan mong doi va khong ghi them: that su dang do dang.
        $state = "DANG DO $mins phut"
    } else {
        # Khong co trong bang $expected -> thi nghiem cu, khong phai dang treo.
        $state = 'cu (khong theo doi)'
    }

    $name = $f.Name -replace '_raw\.txt$', ''
    Write-Output ('{0,-46} {1,13} {2,6} {3}' -f $name, $prog, $fail, $state)
}

Write-Output ''
$os = Get-CimInstance Win32_OperatingSystem
$free = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
$warn = if ($free -lt 1.0) { '  <-- THAP, tranh mo Chrome' } else { '' }
Write-Output ("RAM kha dung: {0} GB{1}" -f $free, $warn)
Write-Output ''
