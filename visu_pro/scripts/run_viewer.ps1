# Launches the standalone BMW Studio viewer (UnrealEditor.exe in -game mode) manually.
# The backend normally launches it for you when you click "Visualize".
param(
    [string]$Model = "bmw-m4-competition-2021",
    [int]$Port = $(if ($env:VIEWER_CONTROL_PORT) { [int]$env:VIEWER_CONTROL_PORT } else { 30777 }),
    [string]$EngineDir = $(if ($env:UE_ENGINE_DIR) { $env:UE_ENGINE_DIR } else { "C:\Program Files\Epic Games\UE_5.8" }),
    [int]$ResX = 1600,
    [int]$ResY = 900
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root "unreal\BMWVisualizer\BMWVisualizer.uproject"
$exe = Join-Path $EngineDir "Engine\Binaries\Win64\UnrealEditor.exe"
$argList = @("`"$project`"", "-game", "-windowed", "-ResX=$ResX", "-ResY=$ResY", "-nosplash",
          "-BMWViewer", "-BMWControlPort=$Port", "-BMWModel=$Model", "-log")
if ($env:VIEWER_TOKEN) { $argList += "-BMWToken=$($env:VIEWER_TOKEN)" }
Start-Process -FilePath $exe -ArgumentList $argList
Write-Host "Viewer starting (control port $Port). First launch compiles shaders and can take several minutes."
