$ErrorActionPreference = "Stop"

if (-not $env:VIRTUAL_ENV) {
    throw "Activate this project's virtual environment before building."
}
if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "The standalone Windows executable must be built on Windows."
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$buildDir = Join-Path $repo "build"
$distDir = Join-Path $repo "dist"
foreach ($target in @($buildDir, $distDir)) {
    $resolvedParent = (Resolve-Path $repo).Path.TrimEnd('\') + '\'
    $fullTarget = [System.IO.Path]::GetFullPath($target)
    if (-not $fullTarget.StartsWith($resolvedParent, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean a path outside this desktop project."
    }
    if (Test-Path -LiteralPath $fullTarget) {
        Remove-Item -LiteralPath $fullTarget -Recurse -Force
    }
}

Push-Location $repo
try {
python -m PyInstaller --noconfirm --clean packaging\statguard_desktop.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller exited with code $LASTEXITCODE."
}
$exe = Join-Path $distDir "StatGuardDesktop.exe"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "PyInstaller completed without creating dist\StatGuardDesktop.exe."
}
Write-Host "Built $exe"
}
finally {
    Pop-Location
}
