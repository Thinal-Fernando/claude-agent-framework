[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath
)

$ErrorActionPreference = "Stop"

# Resolve paths
$FrameworkRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$TemplateRoot = Join-Path $FrameworkRoot "templates\project"
$ResolvedProjectPath = Resolve-Path $ProjectPath

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Claude Agent Framework - Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Framework:" $FrameworkRoot
Write-Host "Project:  " $ResolvedProjectPath
Write-Host ""

# Verify the target is a Git repository
$GitPath = Join-Path $ResolvedProjectPath ".git"

if (-not (Test-Path $GitPath)) {
    Write-Error "Target project is not a Git repository."
}

# Prevent accidentally installing into the framework repository itself
if ($ResolvedProjectPath.Path -eq $FrameworkRoot.Path) {
    Write-Error "Refusing to install the framework into itself."
}

# Create destination directories
$DestinationClaude = Join-Path $ResolvedProjectPath ".claude"
$DestinationState = Join-Path $DestinationClaude "state"

New-Item -ItemType Directory -Path $DestinationClaude -Force | Out-Null
New-Item -ItemType Directory -Path $DestinationState -Force | Out-Null

# Files to install
$Files = @(
    "MISSION.md",

    ".claude\framework-version",

    "CLAUDE.md",

    ".claude\state\ACTIVE.md",
    ".claude\state\COMPLETED.md",
    ".claude\state\NEXT_STEPS.md",
    ".claude\state\DECISIONS.md",
    ".claude\state\BLOCKERS.md",
    ".claude\state\FAILED_APPROACHES.md",

    ".claude\skills\long-running-agent\SKILL.md",
    ".claude\skills\long-running-agent\state-protocol.md",
    ".claude\skills\long-running-agent\checkpoint-template.md",
    ".claude\skills\long-running-agent\completion-rules.md"
)

foreach ($RelativePath in $Files) {

    $Source = Join-Path $TemplateRoot $RelativePath
    $Destination = Join-Path $ResolvedProjectPath $RelativePath

    if (-not (Test-Path $Source)) {
        Write-Error "Template file not found: $Source"
    }

    # Do not silently overwrite an existing file. (mainly to prevent overwriting MISSION.md)
    if (Test-Path $Destination) {
        Write-Host "SKIP   $RelativePath (already exists)" -ForegroundColor Yellow
        continue
    }

    $Parent = Split-Path $Destination -Parent

    if (-not (Test-Path $Parent)) {
        New-Item -ItemType Directory -Path $Parent -Force | Out-Null
    }

    Copy-Item $Source $Destination

    Write-Host "CREATE $RelativePath" -ForegroundColor Green
}

Write-Host ""
Write-Host "Installation complete." -ForegroundColor Green
Write-Host ""

Write-Host "Next:"
Write-Host "  1. Edit MISSION.md"
Write-Host "  2. Review .claude/state/"
Write-Host "  3. Commit the generated framework files"
Write-Host ""