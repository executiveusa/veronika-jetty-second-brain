# JETTY™ — Wipe for delivery
# Empties all personal data so Veronika starts with a clean galaxy.
# Run before handing off. Does NOT touch .env or source code.
#
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\wipe-for-delivery.ps1

$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "Wiping JETTY personal data for fresh delivery..." -ForegroundColor Cyan

# 1. Chat history (JSONL)
$chatLog = Join-Path $root "data\chat-history.jsonl"
if (Test-Path $chatLog) {
    Remove-Item $chatLog -Force
    Write-Host "  [x] Removed chat-history.jsonl" -ForegroundColor Green
}

# 2. Server-side memory / tasks
foreach ($f in @("data\jetty-memory.md", "data\jetty-tasks.json", "data\jetty-inbox.json")) {
    $p = Join-Path $root $f
    if (Test-Path $p) { Remove-Item $p -Force; Write-Host "  [x] Removed $f" -ForegroundColor Green }
}

# 3. Captured notes (keep the folder, empty contents)
$captures = Join-Path $root "notes\captures"
if (Test-Path $captures) {
    Get-ChildItem $captures -File | Remove-Item -Force
    Write-Host "  [x] Emptied notes\captures\" -ForegroundColor Green
}

# 4. Duplex / session state files
foreach ($f in @("jetty-duplex.json", "jetty-proactive.json", "jetty-dnd.json", "jetty-episodes.jsonl")) {
    $p = Join-Path $root $f
    if (Test-Path $p) { Remove-Item $p -Force; Write-Host "  [x] Removed $f" -ForegroundColor Green }
}

# 5. Postgres history (if server running)
try {
    $health = Invoke-RestMethod "http://127.0.0.1:4700/api/health" -TimeoutSec 3
    if ($health.ok) {
        try {
            Invoke-RestMethod -Method POST "http://127.0.0.1:4700/api/sessions/clear" -TimeoutSec 5 | Out-Null
            Write-Host "  [x] Cleared server-side sessions" -ForegroundColor Green
        } catch { Write-Host "  [!] Server reachable but /api/sessions/clear failed" -ForegroundColor Yellow }
    }
} catch {
    Write-Host "  [i] Server not running — skipped session clear (will be clean on first boot)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Delivery wipe complete." -ForegroundColor Cyan
Write-Host "Browser note: Veronika should clear localStorage keys starting with 'jetty_' in her browser," -ForegroundColor DarkGray
Write-Host "              or open the app in a fresh/incognito window for the cleanest first run." -ForegroundColor DarkGray
Write-Host "              The onboarding overlay will show automatically on first visit." -ForegroundColor DarkGray
