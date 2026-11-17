param(
    [string]$PythonPath = "",
    [string]$PyInstallerPath = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = if ($PythonPath) { $PythonPath } else { Join-Path $projectRoot ".venv\Scripts\python.exe" }
$pyinstaller = if ($PyInstallerPath) { $PyInstallerPath } else { Join-Path $projectRoot ".venv\Scripts\pyinstaller.exe" }
$installerDist = Join-Path $projectRoot "dist-installer"
$installerBuild = Join-Path $projectRoot "build-installer"
$issFile = Join-Path $projectRoot "installer\Eslestirici.iss"
$setupPath = Join-Path $projectRoot "release\Eslestirici-v2.3.1-Setup-Windows-x64.exe"
$isccCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
)
$iscc = $isccCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python ortamı bulunamadı. Önce README'deki Windows kurulum adımlarını uygulayın veya -PythonPath verin."
}
if (-not (Test-Path -LiteralPath $pyinstaller)) {
    throw "PyInstaller bulunamadı. Bağımlılıkları kurun veya -PyInstallerPath verin."
}
if (-not $iscc) {
    throw "Inno Setup 6 bulunamadı. 'winget install --id JRSoftware.InnoSetup -e' komutuyla kurun."
}

Push-Location $projectRoot
try {
    & $python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Testler başarısız oldu." }

    & $pyinstaller --noconfirm --clean --distpath $installerDist --workpath $installerBuild Eslestirici-Installer.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller kurulum uygulamasını oluşturamadı." }

    & $iscc $issFile
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup paketi oluşturamadı." }
    if (-not (Test-Path -LiteralPath $setupPath)) { throw "Setup EXE beklenen konumda oluşmadı." }

    Write-Host "Windows kurulum paketi hazır: $setupPath"
}
finally {
    Pop-Location
}
