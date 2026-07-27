<#
.SYNOPSIS
    Point the backend's link-building at whatever hostname ngrok is serving now.

.DESCRIPTION
    Reads the local ngrok agent's API (127.0.0.1:4040) and writes the tunnel
    hostnames into deploy/public_hosts.txt, which the backend re-reads on the
    next request. No container restart, no .env edit — that is the entire point:
    a free ngrok tunnel gets a NEW hostname every time it is restarted, and the
    reset-password email has to follow it.

    Everything above the auto marker in the file is left alone, so hand-added
    entries (localhost, a campus hostname) survive a resync.

.PARAMETER Watch
    Keep running and resync every -IntervalSeconds, so restarting ngrok needs no
    action at all. Leave it in a spare terminal next to the ngrok window.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\sync-public-host.ps1
    powershell -ExecutionPolicy Bypass -File scripts\sync-public-host.ps1 -Watch
#>
[CmdletBinding()]
param(
    [string]$File = (Join-Path $PSScriptRoot "..\deploy\public_hosts.txt"),
    [string]$AgentApi = "http://127.0.0.1:4040/api/tunnels",
    [switch]$Watch,
    [int]$IntervalSeconds = 20
)

$ErrorActionPreference = "Stop"
$marker = "# >>> ngrok (auto - rewritten by scripts/sync-public-host.ps1)"

function Get-TunnelHosts {
    try {
        $tunnels = (Invoke-RestMethod -Uri $AgentApi -TimeoutSec 8).tunnels
    } catch {
        Write-Warning "Khong doc duoc ngrok agent tai $AgentApi (agent chua chay?): $($_.Exception.Message)"
        return @()
    }
    # https://<host>/... -> <host>. Only https tunnels: the http twin is the same
    # hostname and would just duplicate the entry.
    $tunnels |
        Where-Object { $_.public_url -like "https://*" } |
        ForEach-Object { ([Uri]$_.public_url).Host } |
        Sort-Object -Unique
}

function Sync-Once {
    $hosts = @(Get-TunnelHosts)
    if (-not $hosts) { return $false }

    if (Test-Path $File) {
        $existing = @(Get-Content $File)
        $cut = $existing.IndexOf($marker)
        # Tolerate an older marker text so re-running never duplicates the block.
        if ($cut -lt 0) { $cut = ($existing | Select-String -Pattern '^# >>> ngrok' | Select-Object -First 1).LineNumber - 1 }
        if ($cut -ge 0) { $existing = $existing[0..([Math]::Max($cut - 1, 0))] }
    } else {
        $existing = @(
            "# Hosts allowed to define the links this backend emails. Per-machine",
            "# file - see public_hosts.example.txt. Live on the next request.",
            "",
            "localhost",
            "127.0.0.1",
            ""
        )
    }

    $new = @($existing) + @($marker) + @($hosts)
    $current = if (Test-Path $File) { (Get-Content $File -Raw) } else { "" }
    $next = ($new -join "`n") + "`n"
    if ($current -eq $next) { return $false }

    # UTF8 without BOM: the file is read by Python inside the container, and a
    # BOM would ride along on the first hostname and never match.
    [System.IO.File]::WriteAllText((Resolve-Path -LiteralPath (Split-Path $File -Parent)).Path + "\" + (Split-Path $File -Leaf), $next, (New-Object System.Text.UTF8Encoding($false)))
    Write-Output ("[{0}] cap nhat: {1}" -f (Get-Date -Format "HH:mm:ss"), ($hosts -join ", "))
    return $true
}

if (-not (Test-Path (Split-Path $File -Parent))) {
    New-Item -ItemType Directory -Path (Split-Path $File -Parent) | Out-Null
}

if ($Watch) {
    Write-Output "Theo doi ngrok moi $IntervalSeconds giay. Ctrl+C de dung."
    while ($true) {
        try { Sync-Once | Out-Null } catch { Write-Warning $_.Exception.Message }
        Start-Sleep -Seconds $IntervalSeconds
    }
} else {
    if (-not (Sync-Once)) { Write-Output "Khong co gi thay doi." }
    Get-Content $File
}
