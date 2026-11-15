param([switch]$SelfContained)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$out = Join-Path $here "..\sowanna\_bridge"

Write-Host "[Sowanna] publish Bridge.exe -> $out"

# Очистка старых артефактов сборки
if (Test-Path "$here\bin") { Remove-Item -Recurse -Force "$here\bin" }
if (Test-Path "$here\obj") { Remove-Item -Recurse -Force "$here\obj" }
if (Test-Path $out) { Remove-Item -Recurse -Force $out }

New-Item -ItemType Directory -Force -Path $out | Out-Null

Push-Location $here
try {
    $args = @("publish", "Sowanna.Bridge.csproj", "-c", "Release", "-o", $out, "-r", "win-x64")
    if ($SelfContained) { $args += "--self-contained"; $args += "true" }
    else { $args += "--self-contained"; $args += "false" }
    
    dotnet @args
} finally {
    Pop-Location
}

Write-Host "[Sowanna] готово: $out"
Get-ChildItem $out | Format-Table Name, Length