[CmdletBinding()]
param(
    [ValidatePattern('^\d+\.\d+\.\d+(?:-[A-Za-z0-9][A-Za-z0-9.-]*)?$')]
    [string]$Version = '0.1.0-preview.1',
    [string]$Python = 'python',
    [string]$InnoCompiler = 'ISCC.exe'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonCommand = (Get-Command $Python -CommandType Application).Source
$compilerCommand = (Get-Command $InnoCompiler -CommandType Application).Source
# A fresh workspace keeps generated output separate from earlier builds.
$buildRoot = Join-Path $projectRoot ('build\windows-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $buildRoot | Out-Null
$icon = Join-Path $buildRoot 'RooPlan.ico'

Push-Location -LiteralPath $projectRoot
try {
    & $pythonCommand -c 'import struct, sys; from PySide6.QtGui import QImage; sys.exit(0 if sys.platform == "win32" and struct.calcsize("P") == 8 and QImage(sys.argv[1]).save(sys.argv[2]) else 1)' 'assets/rooplan-taskbar.png' $icon
    if ($LASTEXITCODE -ne 0) { throw 'Building RooPlan requires 64-bit Windows Python with PySide6.' }

    & $pythonCommand -m PyInstaller --onedir --windowed --noupx --name RooPlan --icon $icon `
        --distpath (Join-Path $buildRoot 'dist') --workpath (Join-Path $buildRoot 'work') `
        --specpath $buildRoot --add-data "${projectRoot}\qml:qml" --add-data "${projectRoot}\assets:assets" main.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

    $notices = Join-Path $buildRoot 'dist\RooPlan\third-party'
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'third-party') -Destination $notices -Recurse
    $pythonLicense = & $pythonCommand -c 'import sys; from pathlib import Path; print(Path(sys.base_prefix) / "LICENSE.txt")'
    $bootloaderLicense = & $pythonCommand -c 'from importlib.metadata import distribution; d = distribution("pyinstaller"); print(d.locate_file(next(p for p in d.files if p.name == "COPYING.txt")))'
    Copy-Item -LiteralPath $pythonLicense -Destination (Join-Path $notices 'Python.txt')
    Copy-Item -LiteralPath $bootloaderLicense -Destination (Join-Path $notices 'PyInstaller.txt')

    New-Item -ItemType Directory -Path (Join-Path $buildRoot 'release') | Out-Null
    & $compilerCommand "/DReleaseVersion=$Version" "/DBuildRoot=$buildRoot" (Join-Path $PSScriptRoot 'windows.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup build failed.' }

    Get-Item -LiteralPath (Join-Path $buildRoot "release\RooPlan-$Version-Windows-x64-Setup.exe")
} finally {
    Pop-Location
}
