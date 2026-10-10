# Copies the source ZIP to assets\source (if needed) and extracts it to assets\extracted.
# The original ZIP is never modified.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$zipName = "2021-bmw-m4-competition.zip"
$srcZip = Join-Path $root "assets\source\$zipName"
if (-not (Test-Path $srcZip)) {
    $orig = Join-Path $root $zipName
    if (-not (Test-Path $orig)) { throw "Cannot find $zipName in project root or assets\source" }
    New-Item -ItemType Directory -Force (Split-Path $srcZip) | Out-Null
    Copy-Item $orig $srcZip
}
$dest = Join-Path $root "assets\extracted\bmw-m4-competition-2021"
if (Test-Path (Join-Path $dest "source")) { Write-Host "Already extracted: $dest"; return }
New-Item -ItemType Directory -Force $dest | Out-Null
Expand-Archive -Path $srcZip -DestinationPath $dest
Write-Host "Extracted to $dest"
