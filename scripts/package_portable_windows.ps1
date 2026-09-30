$ErrorActionPreference = "Stop"

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$exe = Join-Path $repo "dist\StatGuardDesktop.exe"
$python = Join-Path $repo ".venv\Scripts\python.exe"
$releaseRoot = Join-Path $repo "release"
$packageName = "StatGuard-Desktop-0.1.0-windows-x64"
$package = Join-Path $releaseRoot $packageName
$zipPath = Join-Path $releaseRoot "$packageName.zip"
$zipHashPath = "$zipPath.sha256"
$work = Join-Path $env:TEMP ("statguard-desktop-portable-smoke-" + [guid]::NewGuid().ToString("N"))
$expectedRules = @("ML001", "ML002", "ML003", "ML004", "ML005", "ML006", "ML007", "ML008", "ML009", "ST001", "ST002")

function Invoke-PortableExecutable([string[]]$Arguments) {
    $quoted = @($Arguments | ForEach-Object { '"' + $_.Replace('"', '\"') + '"' })
    $process = Start-Process -FilePath $extracted -ArgumentList ($quoted -join " ") -Wait -PassThru
    return $process.ExitCode
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "Portable Windows packaging must run on Windows."
}
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Build dist\StatGuardDesktop.exe before packaging."
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Portable smoke verification requires .venv\Scripts\python.exe."
}
New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
foreach ($target in @($package, $zipPath, $zipHashPath)) {
    $full = [System.IO.Path]::GetFullPath($target)
    $prefix = [System.IO.Path]::GetFullPath($releaseRoot).TrimEnd('\') + '\'
    if (-not $full.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to write outside the release directory."
    }
}
$tempPrefix = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
if (-not [System.IO.Path]::GetFullPath($work).StartsWith($tempPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to create extracted smoke files outside the system temporary directory."
}
if (Test-Path -LiteralPath $package) { Remove-Item -LiteralPath $package -Recurse -Force }
if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
if (Test-Path -LiteralPath $zipHashPath) { Remove-Item -LiteralPath $zipHashPath -Force }
New-Item -ItemType Directory -Path $package -Force | Out-Null
New-Item -ItemType Directory -Path $work -Force | Out-Null

try {
    Copy-Item -LiteralPath $exe -Destination (Join-Path $package "StatGuardDesktop.exe")
    Copy-Item -LiteralPath (Join-Path $repo "LICENSE") -Destination (Join-Path $package "LICENSE.txt")
    $readme = @'
StatGuard Desktop
Version 0.1.0 — first public Alpha release

Start: Double-click StatGuardDesktop.exe.
Scans Python .py files, Jupyter .ipynb files, and project folders.
Static analysis only: submitted Python and Notebook code is not executed.
Notebook output is not analyzed.
Reports: HTML, JSON, and SARIF.
Engine: StatGuard 1.0.0.
Requirements: Windows 10/11, 64-bit. No Python installation is required.
This executable is not code-signed; Windows SmartScreen may show an unknown-publisher warning.
No auto-update or telemetry is included.
'@
    [System.IO.File]::WriteAllText((Join-Path $package "README.txt"), $readme.Trim() + "`r`n", [System.Text.UTF8Encoding]::new($false))

    $checksums = @()
    foreach ($name in @("StatGuardDesktop.exe", "README.txt", "LICENSE.txt")) {
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $package $name)).Hash.ToLowerInvariant()
        $checksums += "$hash  $name"
    }
    [System.IO.File]::WriteAllText((Join-Path $package "SHA256SUMS.txt"), ($checksums -join "`r`n") + "`r`n", [System.Text.UTF8Encoding]::new($false))

    Compress-Archive -LiteralPath $package -DestinationPath $zipPath -CompressionLevel Optimal
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        $entries = @($archive.Entries | Where-Object { $_.Name -ne "" } | ForEach-Object { $_.FullName.Replace('\', '/') } | Sort-Object)
        $expected = @(
            "$packageName/StatGuardDesktop.exe",
            "$packageName/README.txt",
            "$packageName/LICENSE.txt",
            "$packageName/SHA256SUMS.txt"
        ) | Sort-Object
        if (($entries -join "`n") -cne ($expected -join "`n")) {
            throw "Portable ZIP contains unexpected files or paths."
        }
        foreach ($entry in $archive.Entries) {
            $stream = $entry.Open()
            try {
                $buffer = [System.IO.MemoryStream]::new()
                try { $stream.CopyTo($buffer) } finally { $buffer.Dispose() }
            } finally { $stream.Dispose() }
        }
    } finally { $archive.Dispose() }

    $zipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash.ToLowerInvariant()
    [System.IO.File]::WriteAllText($zipHashPath, "$zipHash  $packageName.zip`r`n", [System.Text.UTF8Encoding]::new($false))
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zipPath, $work)
    $extracted = Join-Path (Join-Path $work $packageName) "StatGuardDesktop.exe"
    $oldPath = $env:PATH
    try {
        $env:PATH = "$env:WINDIR\System32;$env:WINDIR;$env:WINDIR\System32\Wbem"
        Push-Location $env:TEMP
        if ((Invoke-PortableExecutable @("--smoke-test", (Join-Path $work "smoke.json"))) -ne 0) {
            throw "Extracted executable smoke test failed."
        }
        $enginePath = Join-Path $work "engine-info.json"
        if ((Invoke-PortableExecutable @("--engine-info", $enginePath)) -ne 0) {
            throw "Extracted engine inventory failed."
        }
        $engine = Get-Content -LiteralPath $enginePath -Raw | ConvertFrom-Json
        if (($engine.enabled_rule_ids -join ",") -cne ($expectedRules -join ",")) {
            throw "Extracted executable does not contain the expected engine rule inventory."
        }
        if ((Invoke-PortableExecutable @("--gui-smoke-test", (Join-Path $work "gui-smoke.json"))) -ne 0) {
            throw "Extracted GUI launch smoke failed."
        }

        $unicodeFolderName = ([string][char]0x9879) + [char]0x76ee + " " + [char]0x6d4b + [char]0x8bd5
        $unicodeRoot = Join-Path (Join-Path $work "inputs with spaces (1)") $unicodeFolderName
        New-Item -ItemType Directory -Path $unicodeRoot -Force | Out-Null
        $marker = Join-Path $unicodeRoot "must-not-exist.marker"
        $pythonLiteral = "'" + $marker.Replace('\', '\\').Replace("'", "\'") + "'"
        [System.IO.File]::WriteAllText((Join-Path $unicodeRoot "side-effect.py"), "from pathlib import Path`nPath($pythonLiteral).write_text('executed')`n", [System.Text.UTF8Encoding]::new($false))
        if ((Invoke-PortableExecutable @("--scan-smoke", (Join-Path $unicodeRoot "side-effect.py"), (Join-Path $work "no-execution.json"))) -ne 0) {
            throw "Extracted Python scan smoke failed."
        }
        if (Test-Path -LiteralPath $marker) { throw "Scanning executed the submitted Python fixture." }

        $risky = Join-Path $unicodeRoot "leakage.py"
        $riskySource = @'
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

scaler = StandardScaler()
scaled = scaler.fit_transform(X)
X_train, X_test = train_test_split(scaled)
'@
        [System.IO.File]::WriteAllText($risky, $riskySource + "`n", [System.Text.UTF8Encoding]::new($false))
        $riskPath = Join-Path $work "risk.json"
        if ((Invoke-PortableExecutable @("--scan-smoke", $risky, $riskPath)) -ne 0) {
            throw "Extracted risk scan smoke failed."
        }
        $safe = Join-Path $unicodeRoot "safe.py"
        [System.IO.File]::WriteAllText($safe, "print('safe')`n", [System.Text.UTF8Encoding]::new($false))
        $safePath = Join-Path $work "safe.json"
        if ((Invoke-PortableExecutable @("--scan-smoke", $safe, $safePath)) -ne 0) {
            throw "Extracted safe scan smoke failed."
        }

        $notebook = Join-Path $unicodeRoot "side-effect.ipynb"
        $cellSource = @($riskySource -split "`n" | ForEach-Object { $_ + "`n" })
        $cellSource += "from pathlib import Path`n"
        $cellSource += "Path($pythonLiteral).write_text('executed')"
        $notebookText = @{
            nbformat = 4
            nbformat_minor = 5
            metadata = @{ kernelspec = @{ language = "python" } }
            cells = @(@{ cell_type = "code"; metadata = @{}; execution_count = $null; outputs = @(@{ output_type = "stream"; text = @("PRIVATE_OUTPUT_SENTINEL") }); source = $cellSource })
        } | ConvertTo-Json -Depth 10
        [System.IO.File]::WriteAllText($notebook, $notebookText, [System.Text.UTF8Encoding]::new($false))
        $notebookReportPath = Join-Path $work "notebook.json"
        if ((Invoke-PortableExecutable @("--scan-smoke", $notebook, $notebookReportPath)) -ne 0) {
            throw "Extracted Notebook scan smoke failed."
        }
        if (Test-Path -LiteralPath $marker) { throw "Scanning executed Notebook code." }

        $reportsDir = Join-Path $work "reports"
        if ((Invoke-PortableExecutable @("--report-smoke", $risky, $reportsDir)) -ne 0) {
            throw "Packaged reporter smoke failed."
        }
        & $python (Join-Path $repo "scripts\verify_portable_smoke.py") --risk $riskPath --safe $safePath --no-execution (Join-Path $work "no-execution.json") --notebook $notebookReportPath --reports $reportsDir
        if ($LASTEXITCODE -ne 0) { throw "Portable scan or reporter output validation failed." }
    } finally {
        Pop-Location
        $env:PATH = $oldPath
    }
    Write-Host "Portable package: $package"
    Write-Host "Portable ZIP: $zipPath"
    Write-Host "ZIP SHA-256: $zipHash"
    Write-Host "Extracted executable, inventory, Unicode/no-execution and report smoke: passed"
} finally {
    if (Test-Path -LiteralPath $work) { Remove-Item -LiteralPath $work -Recurse -Force }
}
