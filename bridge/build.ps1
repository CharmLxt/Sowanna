param(
    [switch]$SelfContained,
    [switch]$SingleFile,
    [string]$Runtime = "win-x64"
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$out = Join-Path $here "..\sowanna\_bridge"

Write-Host "[Sowanna] publish Bridge.exe -> $out"
Write-Host "[Sowanna] SelfContained=$SelfContained SingleFile=$SingleFile Runtime=$Runtime"

if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force -Path $out | Out-Null

$dotnetArgs = @(
    "publish", "Sowanna.Bridge.csproj",
    "-c", "Release",
    "-o", $out,
    "-r", $Runtime
)
if ($SelfContained) { $dotnetArgs += "--self-contained"; $dotnetArgs += "true" }
else { $dotnetArgs += "--self-contained"; $dotnetArgs += "false" }
if ($SingleFile) { $dotnetArgs += "/p:PublishSingleFile=true" }
else { $dotnetArgs += "/p:PublishSingleFile=false" }

Push-Location $here
try {
    dotnet @dotnetArgs
} finally {
    Pop-Location
}

Write-Host "[Sowanna] готово: $out"
Get-ChildItem $out | Format-Table Name, Length