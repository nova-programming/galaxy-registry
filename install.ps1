#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Nova + Galaxy — Native Installer (PowerShell)
.DESCRIPTION
    Downloads and installs the Nova compiler and Galaxy package manager
    without requiring Python. Creates launchers and adds to user PATH.
.PARAMETER Uninstall
    Remove Nova and Galaxy from the system.
.EXAMPLE
    .\install.ps1
    .\install.ps1 -Uninstall
#>

param([switch]$Uninstall)

Add-Type -AssemblyName System.IO.Compression.FileSystem

$AppName = "Nova + Galaxy"
$NovaZipUrl = "https://github.com/nova-programming/Nova/archive/refs/heads/main.zip"
$ZipPrefix = "Nova-main"
$InstallDir = Join-Path $env:LOCALAPPDATA "nova"
$GccDir = Join-Path $InstallDir "gcc"
$AllowedFiles = @("_galaxy.py", "nova.nv")
$AllowedDirs = @("compiler", "parser", "lexer", "nova_ast", "vm", "stdlib", "modules", "tools", "galaxy")

# Portable GCC (winlibs) — only downloaded on Windows if 'gcc' not on PATH
$MINGW_ZIP_URL = "https://github.com/brechtsanders/winlibs_mingw/releases/download/16.1.0posix-14.0.0-msvcrt-r2/winlibs-x86_64-posix-seh-gcc-16.1.0-mingw-w64msvcrt-14.0.0-r2.zip"
$MINGW_ZIP_TOP = "mingw64"

function Info  { Write-Host "  [..]  $($args[0])" }
function Ok    { Write-Host "  [OK]   $($args[0])" -ForegroundColor Green }
function Warn  { Write-Host "  [WARN] $($args[0])" -ForegroundColor Yellow }
function Fail  { Write-Host "  [FAIL] $($args[0])" -ForegroundColor Red; exit 1 }

function Add-ToPath {
    try {
        $pathKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Environment", $true)
        $current = $pathKey.GetValue("PATH", "", "DoNotExpandEnvironmentNames")
        $parts = $current.Split(";", [StringSplitOptions]::RemoveEmptyEntries)
        $normed = [System.IO.Path]::GetFullPath([System.Environment]::ExpandEnvironmentVariables($InstallDir)).TrimEnd('\')
        $alreadyInPath = $false
        foreach ($p in $parts) {
            try {
                $expanded = [System.Environment]::ExpandEnvironmentVariables($p)
                $pNormed = [System.IO.Path]::GetFullPath($expanded).TrimEnd('\')
                if ($pNormed -eq $normed) { $alreadyInPath = $true; break }
            } catch { continue }
        }
        if ($alreadyInPath) {
            Info "Install directory already in PATH"
            $pathKey.Close()
            return
        }
        $newPath = $current.TrimEnd(";") + ";" + $InstallDir
        $pathKey.SetValue("PATH", $newPath, "ExpandString")
        $pathKey.Close()
        # Update current session only, registry already set above
        [Environment]::SetEnvironmentVariable("PATH", [Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $InstallDir, "Process")
        Ok "Added to PATH: $InstallDir"
        Info "Restart your terminal for the change to take effect."
    } catch {
        Warn "Could not update PATH: $_"
        Info "Add to PATH manually: $InstallDir"
    }
}

function Remove-FromPath {
    try {
        $pathKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Environment", $true)
        $current = $pathKey.GetValue("PATH", "", "DoNotExpandEnvironmentNames")
        $normed = [System.IO.Path]::GetFullPath([System.Environment]::ExpandEnvironmentVariables($InstallDir)).TrimEnd('\')
        $parts = $current.Split(";", [StringSplitOptions]::RemoveEmptyEntries) | Where-Object {
            try {
                $expanded = [System.Environment]::ExpandEnvironmentVariables($_)
                [System.IO.Path]::GetFullPath($expanded).TrimEnd('\') -ne $normed
            } catch { $true }
        }
        $newPath = $parts -join ";"
        $pathKey.SetValue("PATH", $newPath, "ExpandString")
        $pathKey.Close()
        Ok "Removed from PATH"
    } catch {
        Warn "Could not remove from PATH: $_"
    }
}

function New-Launchers {
    $novaLauncher = @'
@echo off
python "%~dp0bootstrap\main.py" %*
'@
    $galaxyLauncher = @'
@echo off
python "%~dp0_galaxy.py" %*
'@
    $useNovaLauncher = @'
@echo off
set "PATH=%~dp0;%PATH%"
echo Nova and Galaxy are now available in this terminal.
echo.
echo Try: nova --version
echo      galaxy --version
'@
    $novaPath = Join-Path $InstallDir "nova.bat"
    $galaxyPath = Join-Path $InstallDir "galaxy.bat"
    $useNovaPath = Join-Path $InstallDir "use_nova.bat"
    Set-Content -Path $novaPath -Value $novaLauncher -Encoding ASCII
    Set-Content -Path $galaxyPath -Value $galaxyLauncher -Encoding ASCII
    Set-Content -Path $useNovaPath -Value $useNovaLauncher -Encoding ASCII
    Ok "Created launcher: $novaPath"
    Ok "Created launcher: $galaxyPath"
    Ok "Created helper: $useNovaPath"
}

function Install-GccIfMissing {
    $hasGcc = $null -ne (Get-Command "gcc" -ErrorAction SilentlyContinue)
    if ($hasGcc) {
        Info "GCC found on PATH — skipping bundle."
        return
    }
    if (Test-Path (Join-Path $GccDir "bin\gcc.exe")) {
        Info "Bundled GCC found — skipping download."
        return
    }
    Info "GCC not found — downloading portable MinGW-w64 (~130MB)..."
    $tmpFile = Join-Path ([System.IO.Path]::GetTempPath()) "mingw-$(Get-Random).zip"
    try {
        $progressPreference = 'silentlyContinue'
        Invoke-WebRequest -Uri $MINGW_ZIP_URL -OutFile $tmpFile -TimeoutSec 300
        $progressPreference = 'continue'
    } catch {
        Warn "Could not download portable GCC: $_"
        Info "Install GCC manually, or use 'nova dev' (VM mode) instead."
        return
    }
    $size = (Get-Item $tmpFile).Length / 1MB
    Info "Downloaded $([math]::Round($size, 1)) MB — extracting..."
    try {
        $zip = [System.IO.Compression.ZipFile]::OpenRead($tmpFile)
        $prefix = "$MINGW_ZIP_TOP/"
        $count = 0
        foreach ($entry in $zip.Entries) {
            if ($entry.FullName -like "$prefix*" -and $entry.Length -gt 0) {
                $rel = $entry.FullName.Substring($prefix.Length)
                $dst = Join-Path $GccDir $rel.Replace("/", "\")
                $dstDir = Split-Path $dst -Parent
                if (-not (Test-Path $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }
                [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $dst, $true)
                $count++
            }
        }
        $zip.Dispose()
        Ok "Extracted $count GCC files to $GccDir"
    } catch {
        Warn "Could not extract GCC: $_"
    }
    Remove-Item $tmpFile -Force
}

function Should-Extract($relPath) {
    $parts = $relPath.Split("/")
    $top = $parts[0]
    if ($AllowedFiles -contains $top) { return $true }
    if ($AllowedDirs -contains $top) { return $true }
    return $false
}

function Install-NovaGalaxy {
    Write-Host ""
    Write-Host "  +========================================+"
    Write-Host "  |  Nova + Galaxy Installer (PowerShell)  |"
    Write-Host "  +========================================+"
    Write-Host ""
    Info "Install directory: $InstallDir"

    if (Test-Path $InstallDir) {
        Info "Directory already exists — will overwrite."
        $okMsg = "Reinstalled"
    } else {
        $okMsg = "Installed"
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }

    Info "Connecting to GitHub..."
    $tmpFile = Join-Path ([System.IO.Path]::GetTempPath()) "nova-install-$(Get-Random).zip"
    try {
        $progressPreference = 'silentlyContinue'
        Invoke-WebRequest -Uri $NovaZipUrl -OutFile $tmpFile -TimeoutSec 120
        $progressPreference = 'continue'
    } catch {
        Fail "Download failed: $_"
    }

    $size = (Get-Item $tmpFile).Length / 1MB
    Info "Downloaded $([math]::Round($size, 1)) MB — verifying..."

    try {
        $zip = [System.IO.Compression.ZipFile]::OpenRead($tmpFile)
        # Validate by checking entries
        $entries = $zip.Entries
        if ($entries.Count -eq 0) { throw "Empty archive" }
    } catch {
        Fail "Corrupted zip archive: $_"
    }

    Info "Extracting files..."
    $prefix = "$ZipPrefix/"
    $count = 0
    foreach ($entry in $zip.Entries) {
        if ($entry.FullName -like "$prefix*" -and $entry.Length -gt 0) {
            $rel = $entry.FullName.Substring($prefix.Length)
            if (Should-Extract $rel) {
                $dst = Join-Path $InstallDir $rel.Replace("/", "\")
                $dstDir = Split-Path $dst -Parent
                if (-not (Test-Path $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }
                [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $dst, $true)
                $count++
            }
        }
    }
    $zip.Dispose()
    Remove-Item $tmpFile -Force

    Ok "Extracted $count files"

    Install-GccIfMissing
    New-Launchers
    Add-ToPath

    Write-Host ""
    Write-Host "  +------------------------------------------------+"
    Write-Host "  |  $okMsg successfully!                         |"
    Write-Host "  +------------------------------------------------+"
    Write-Host ""
    Info "Location: $InstallDir"
    Info "To use nova/galaxy in THIS terminal:"
    Info '  cmd.exe:  call "%LOCALAPPDATA%\nova\use_nova.bat"'
    Info '  PowerShell: $env:PATH = "$env:LOCALAPPDATA\nova;$env:PATH"'
    Info "Or open a NEW terminal."
    Write-Host ""
    Info "  nova --version          Check Nova version"
    Info "  nova build hello.nv     Compile a Nova program"
    Info "  galaxy --version        Check Galaxy version"
    Info "  galaxy install pkg      Install a package"
    Info "  galaxy init my-lib      Create a library"
    Write-Host ""
}

function Uninstall-NovaGalaxy {
    Write-Host ""
    Write-Host "  Uninstalling $AppName..."
    Write-Host ""
    if (Test-Path $InstallDir) {
        Remove-Item -Path $InstallDir -Recurse -Force
        Ok "Removed: $InstallDir"
    } else {
        Info "Nothing to remove at $InstallDir"
    }
    Remove-FromPath
    Write-Host ""
    Ok "$AppName uninstalled."
    Write-Host ""
}

function Main {
    if ($Uninstall) {
        Uninstall-NovaGalaxy
    } else {
        Install-NovaGalaxy
    }
}

Main
