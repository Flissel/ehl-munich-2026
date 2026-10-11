# Builds the Unreal content headlessly: imports the BMW FBX, creates materials and the showroom map.
# Usage:  .\scripts\build_unreal.ps1                 (all stages)
#         .\scripts\build_unreal.ps1 -Stages import  (import | materials | showroom, comma separated)
param(
    [string]$Stages = "import,materials,showroom",
    [string]$EngineDir = $(if ($env:UE_ENGINE_DIR) { $env:UE_ENGINE_DIR } else { "C:\Program Files\Epic Games\UE_5.8" })
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root "unreal\BMWVisualizer\BMWVisualizer.uproject"
$script = Join-Path $root "unreal\BMWVisualizer\Content\Python\bmw_studio_build\build.py"
$cmd = Join-Path $EngineDir "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$fbx = Join-Path $root "assets\extracted\bmw-m4-competition-2021\source\BMW M4 2021 v1.fbx"

if (-not (Test-Path $cmd)) { throw "UnrealEditor-Cmd.exe not found at $cmd. Set UE_ENGINE_DIR." }
if (-not (Test-Path $fbx)) { & (Join-Path $PSScriptRoot "extract_assets.ps1") }

$logDir = Join-Path $root "unreal\BMWVisualizer\Saved\BuildLogs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ("build_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date))

$env:BMW_BUILD_STAGES = $Stages
Write-Host "Running Unreal build stages: $Stages (log: $log)"
& $cmd $project -run=pythonscript "-script=$script" -unattended -nosplash -nullrhi -stdout -FullStdOutLogOutput *> $log
$code = $LASTEXITCODE
Select-String -Path $log -Pattern "\[BMWBuild\]|Error:|Traceback|LogPython: Error" | ForEach-Object { $_.Line }
if (-not (Select-String -Path $log -Pattern "\[BMWBuild\] BUILD OK" -Quiet)) {
    throw "Unreal build failed (exit $code). See $log"
}
Write-Host "Unreal build succeeded."
