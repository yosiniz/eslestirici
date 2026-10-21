$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pyinstaller = Join-Path $projectRoot ".venv\Scripts\pyinstaller.exe"
$portableDist = Join-Path $projectRoot "dist-portable"
$portableBuild = Join-Path $projectRoot "build-portable"
$packageDir = Join-Path $portableDist "OtoparkPlakaKontrol"
$releaseDir = Join-Path $projectRoot "release"
$archivePath = Join-Path $releaseDir "OtoparkPlakaKontrol-Windows-x64-Portable.zip"

if (-not (Test-Path -LiteralPath $python)) {
    throw ".venv bulunamadı. Önce README'deki Windows kurulum adımlarını uygulayın."
}

Push-Location $projectRoot
try {
    & $python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Testler başarısız oldu." }

    & $pyinstaller --noconfirm --clean --distpath $portableDist --workpath $portableBuild OtoparkPlakaKontrol.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller paketi oluşturamadı." }

    Copy-Item -LiteralPath (Join-Path $projectRoot "portable.mode") -Destination $packageDir -Force
    Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination $packageDir -Force
    New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
    if (Test-Path -LiteralPath $archivePath) {
        Remove-Item -LiteralPath $archivePath -Force
    }
    Compress-Archive -LiteralPath $packageDir -DestinationPath $archivePath -CompressionLevel Optimal
    Write-Host "Portable paket hazır: $archivePath"
}
finally {
    Pop-Location
}
