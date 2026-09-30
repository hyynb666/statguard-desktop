$ErrorActionPreference = "Stop"

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "The standalone Windows executable must be built on Windows."
}
if ($env:PROCESSOR_ARCHITECTURE -ne "AMD64") {
    throw "The supported Desktop executable target is 64-bit AMD64 Windows."
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Expected the project virtual environment at .venv\Scripts\python.exe."
}
$buildDir = Join-Path $repo "build"
$workDir = Join-Path $buildDir "pyinstaller"
$distDir = Join-Path $repo "dist"
$exe = Join-Path $distDir "StatGuardDesktop.exe"

function Invoke-DesktopExecutable([string[]]$Arguments) {
    $quoted = @($Arguments | ForEach-Object { '"' + $_.Replace('"', '\"') + '"' })
    $process = Start-Process -FilePath $exe -ArgumentList ($quoted -join " ") -Wait -PassThru
    return $process.ExitCode
}

foreach ($target in @($workDir, $exe)) {
    $full = [System.IO.Path]::GetFullPath($target)
    $repoPrefix = [System.IO.Path]::GetFullPath($repo).TrimEnd('\') + '\'
    if (-not $full.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean a path outside this desktop project."
    }
}

Write-Host "Python: $(& $python --version 2>&1)"
Write-Host "PySide6: $(& $python -c 'import PySide6; print(PySide6.__version__)')"
Write-Host "PyInstaller: $(& $python -m PyInstaller --version)"
Write-Host "Platform: $([System.Environment]::OSVersion.VersionString) / $env:PROCESSOR_ARCHITECTURE"
if ($LASTEXITCODE -ne 0) { throw "Could not query required build tool versions." }

if (Test-Path -LiteralPath $workDir) { Remove-Item -LiteralPath $workDir -Recurse -Force }
if (Test-Path -LiteralPath $exe) { Remove-Item -LiteralPath $exe -Force }
New-Item -ItemType Directory -Path $workDir -Force | Out-Null
New-Item -ItemType Directory -Path $distDir -Force | Out-Null

Push-Location $repo
try {
    & $python -m PyInstaller --noconfirm --workpath $workDir --distpath $distDir packaging\statguard_desktop.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller exited with code $LASTEXITCODE." }
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        throw "PyInstaller completed without creating dist\StatGuardDesktop.exe."
    }
    $versionInfo = (Get-Item -LiteralPath $exe).VersionInfo
    foreach ($pair in @(
        @{ Name = "FileDescription"; Value = "StatGuard Desktop" },
        @{ Name = "ProductName"; Value = "StatGuard Desktop" },
        @{ Name = "InternalName"; Value = "StatGuardDesktop" },
        @{ Name = "OriginalFilename"; Value = "StatGuardDesktop.exe" },
        @{ Name = "CompanyName"; Value = "StatGuard contributors" },
        @{ Name = "FileVersion"; Value = "0.1.0.0" },
        @{ Name = "ProductVersion"; Value = "0.1.0.0" }
    )) {
        if ($versionInfo.($pair.Name) -ne $pair.Value) {
            throw "Executable version resource mismatch for $($pair.Name)."
        }
    }

    if ((Invoke-DesktopExecutable @("--smoke-test", (Join-Path $buildDir "desktop-smoke.json"))) -ne 0) {
        throw "Executable metadata smoke test failed."
    }
    if ((Invoke-DesktopExecutable @("--engine-info", (Join-Path $buildDir "engine-info.json"))) -ne 0) {
        throw "Executable engine inventory failed."
    }
    $inventory = Get-Content -LiteralPath (Join-Path $buildDir "engine-info.json") -Raw | ConvertFrom-Json
    $expectedRules = @("ML001", "ML002", "ML003", "ML004", "ML005", "ML006", "ML007", "ML008", "ML009", "ST001", "ST002")
    if ($inventory.statguard_version -ne "1.0.0" -or ($inventory.enabled_rule_ids -join ",") -cne ($expectedRules -join ",")) {
        throw "Executable engine version or rule inventory does not match the release baseline."
    }

    $buildInfoPath = Join-Path $buildDir "build-info.json"
    & $python scripts\write_build_info.py $exe $buildInfoPath
    if ($LASTEXITCODE -ne 0) { throw "Could not write build metadata." }
    $buildInfo = Get-Content -LiteralPath $buildInfoPath -Raw | ConvertFrom-Json
    if ($buildInfo.desktop_version -ne "0.1.0" -or $buildInfo.statguard_version -ne "1.0.0") {
        throw "Build metadata version does not match the release baseline."
    }
    $length = (Get-Item -LiteralPath $exe).Length
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $exe).Hash.ToLowerInvariant()
    Write-Host "Built: $exe"
    Write-Host "Size: $length bytes"
    Write-Host "SHA-256: $hash"
} finally {
    Pop-Location
}
