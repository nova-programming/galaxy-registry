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
$NovaZipUrl = "https://github.com/nova-programming/Nova/archive/refs/heads/develop.zip"
$ZipPrefix = "Nova-develop"
$InstallDir = Join-Path $env:LOCALAPPDATA "nova"
$AllowedFiles = @("main.py", "_galaxy.py")
$AllowedDirs = @("compiler", "parser", "lexer", "nova_ast", "vm", "stdlib", "modules", "tools", "galaxy")

function Info  { Write-Host "  [..]  $($args[0])" }
function Ok    { Write-Host "  [OK]   $($args[0])" -ForegroundColor Green }
function Warn  { Write-Host "  [WARN] $($args[0])" -ForegroundColor Yellow }
function Fail  { Write-Host "  [FAIL] $($args[0])" -ForegroundColor Red; exit 1 }

function Add-ToPath {
    try {
        $pathKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Environment", $true)
        $current = $pathKey.GetValue("PATH", "", "DoNotExpandEnvironmentNames")
        $parts = $current.Split(";", [StringSplitOptions]::RemoveEmptyEntries)
        $normed = [System.IO.Path]::GetFullPath($InstallDir).TrimEnd('\')
        if ($parts | Where-Object { [System.IO.Path]::GetFullPath($_).TrimEnd('\') -eq $normed }) {
            Info "Install directory already in PATH"
            return
        }
        $newPath = $current.TrimEnd(";") + ";" + $InstallDir
        $pathKey.SetValue("PATH", $newPath, "ExpandString")
        $pathKey.Close()
        # Notify Windows
        [Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";" + $InstallDir, "User")
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
        $normed = [System.IO.Path]::GetFullPath($InstallDir).TrimEnd('\')
        $parts = $current.Split(";", [StringSplitOptions]::RemoveEmptyEntries) | Where-Object {
            [System.IO.Path]::GetFullPath($_).TrimEnd('\') -ne $normed
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
python "%~dp0main.py" %*
'@
    $galaxyLauncher = @'
@echo off
python "%~dp0_galaxy.py" %*
'@
    $novaPath = Join-Path $InstallDir "nova.bat"
    $galaxyPath = Join-Path $InstallDir "galaxy.bat"
    Set-Content -Path $novaPath -Value $novaLauncher -Encoding ASCII
    Set-Content -Path $galaxyPath -Value $galaxyLauncher -Encoding ASCII
    Ok "Created launcher: $novaPath"
    Ok "Created launcher: $galaxyPath"
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

    New-Launchers
    Add-ToPath

    Write-Host ""
    Write-Host "  +------------------------------------------------+"
    Write-Host "  |  $okMsg successfully!                         |"
    Write-Host "  +------------------------------------------------+"
    Write-Host ""
    Info "Location: $InstallDir"
    Info "Open a NEW terminal, then:"
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
