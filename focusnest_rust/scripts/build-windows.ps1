<#
.SYNOPSIS
Build FocusNest NSIS installers for Windows x64 and/or ARM64.
.EXAMPLE
.\scripts\build-windows.ps1
.EXAMPLE
.\scripts\build-windows.ps1 -Architecture arm64 -SkipInstall
.EXAMPLE
.\scripts\build-windows.ps1 -Architecture both -DryRun
.DESCRIPTION
Requires Windows, Node.js 20.19+ or 22+, Rust MSVC, the Windows SDK and Visual
Studio C++ build tools for EACH requested architecture. An x64 Windows host
can cross-build ARM64 with the ARM64 MSVC tools installed. Tests run only
for the host; run the ARM64 app on an ARM64 device separately. NSIS setup
uses x86 emulation on ARM64 while the application binary is native ARM64.
#>
[CmdletBinding()]
param(
    [ValidateSet('x64', 'arm64', 'both')]
    [string]$Architecture = 'both',
    [switch]$SkipInstall,
    [switch]$SkipTests,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
$previousCargoHome = $env:CARGO_HOME
$previousRustupHome = $env:RUSTUP_HOME
$previousTargetDir = $env:CARGO_TARGET_DIR
$previousPath = $env:PATH

function Invoke-Step {
    param([string]$Command, [string[]]$Arguments)
    Write-Host ('+ ' + $Command + ' ' + ($Arguments -join ' '))
    if (-not $DryRun) {
        & $Command @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$Command failed with exit code $LASTEXITCODE. Build stopped."
        }
    }
}

Push-Location $appRoot
try {
    if (-not $DryRun -and $env:OS -ne 'Windows_NT') {
        throw 'Run this script on Windows. -DryRun can be used on any OS with PowerShell.'
    }
    $localCargo = Join-Path $appRoot '.toolchain/cargo'
    $localRustup = Join-Path $appRoot '.toolchain/rustup'
    if ((Test-Path (Join-Path $localCargo 'bin/cargo.exe')) -and (Test-Path $localRustup)) {
        $env:CARGO_HOME = $localCargo
        $env:RUSTUP_HOME = $localRustup
        $env:PATH = (Join-Path $localCargo 'bin') + [IO.Path]::PathSeparator + $env:PATH
    }
    $env:CARGO_TARGET_DIR = Join-Path $appRoot 'src-tauri/target'
    if (-not $DryRun) {
        foreach ($tool in @('node', 'npm.cmd', 'cargo', 'rustup', 'rustc')) {
            if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
                throw "Missing $tool. Install the prerequisites from BUILD.md."
            }
        }
        $nodeVersionText = & node --version
        if ($LASTEXITCODE -ne 0) { throw 'Could not read Node.js version.' }
        $nodeVersion = [version]($nodeVersionText.Trim().TrimStart('v'))
        if (-not ($nodeVersion.Major -ge 22 -or ($nodeVersion.Major -eq 20 -and $nodeVersion.Minor -ge 19))) {
            throw 'Use Node.js 20.19+ or 22+.'
        }
        $hostDescription = (& rustc -vV) -join "`n"
        if ($LASTEXITCODE -ne 0 -or $hostDescription -notmatch 'host: (x86_64|aarch64)-pc-windows-msvc') {
            throw 'Use a native Windows x64 or ARM64 MSVC Rust toolchain (not GNU).'
        }
        if ($SkipInstall -and -not (Test-Path 'node_modules/@tauri-apps/cli/tauri.js')) {
            throw 'Run npm ci before using -SkipInstall.'
        }
    }
    $targets = switch ($Architecture) {
        'x64'   { 'x86_64-pc-windows-msvc' }
        'arm64' { 'aarch64-pc-windows-msvc' }
        'both'  { 'x86_64-pc-windows-msvc'; 'aarch64-pc-windows-msvc' }
    }
    Write-Host "Building FocusNest Windows installers: $Architecture"
    if (-not $SkipInstall) { Invoke-Step 'npm.cmd' @('ci') }
    foreach ($target in $targets) { Invoke-Step 'rustup' @('target', 'add', $target) }
    if (-not $SkipTests) {
        Invoke-Step 'npm.cmd' @('test')
        Invoke-Step 'cargo' @('test', '--manifest-path', 'src-tauri/Cargo.toml', '--locked')
    }
    foreach ($target in $targets) {
        Invoke-Step 'node' @('scripts/tauri.mjs', 'build', '--target', $target, '--bundles', 'nsis', '--', '--locked')
        Write-Host "Installer output: $($env:CARGO_TARGET_DIR)/$target/release/bundle/nsis/"
    }
    Write-Host 'Signing is not configured by this script. Test each installer on its target architecture.'
}
finally {
    Pop-Location
    $env:CARGO_HOME = $previousCargoHome
    $env:RUSTUP_HOME = $previousRustupHome
    $env:CARGO_TARGET_DIR = $previousTargetDir
    $env:PATH = $previousPath
}
