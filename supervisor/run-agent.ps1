[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,

    [Parameter(Mandatory = $false)]
    [int]$MaxSessionsOverride = 0
)

$ErrorActionPreference = "Stop"

$SupervisorRoot = $PSScriptRoot
$FrameworkRoot = Resolve-Path (Join-Path $SupervisorRoot "..")

$ConfigPath = Join-Path $SupervisorRoot "config.yaml"
$PromptPath = Join-Path $SupervisorRoot "prompts\session.md"
$SessionScript = Join-Path $SupervisorRoot "session.ps1"

$ResolvedProjectPath = Resolve-Path $ProjectPath

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "      Claude Agent Framework Supervisor       " -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Framework : $FrameworkRoot"
Write-Host "Project   : $ResolvedProjectPath"
Write-Host ""

# Basic validation
if (-not (Test-Path $ConfigPath)) {
    throw "Supervisor configuration not found: $ConfigPath"
}

if (-not (Test-Path $PromptPath)) {
    throw "Session prompt not found: $PromptPath"
}

if (-not (Test-Path $SessionScript)) {
    throw "Session script not found: $SessionScript"
}

$GitDirectory = Join-Path $ResolvedProjectPath ".git"

if (-not (Test-Path $GitDirectory)) {
    throw "Target project is not a Git repository."
}

$ClaudeDirectory = Join-Path $ResolvedProjectPath ".claude"

if (-not (Test-Path $ClaudeDirectory)) {
    throw "Target project does not contain .claude. Run install.ps1 first."
}

$StateDirectory = Join-Path $ClaudeDirectory "state"

if (-not (Test-Path $StateDirectory)) {
    throw "Target project does not contain .claude\state."
}



# a very small YAML parser because the configuration shape is simple and fixed.
# Later can replace this with a proper configuration loader if needed
function Get-SimpleYamlValue {
    param(
        [string]$Path,
        [string]$Key
    )

    $Lines = Get-Content $Path

    foreach ($Line in $Lines) {

        $Trimmed = $Line.Trim()

        if (
            $Trimmed.StartsWith("#") -or
            $Trimmed -eq "" -or
            -not $Trimmed.Contains(":")
        ) {
            continue
        }

        $Parts = $Trimmed.Split(":", 2)

        $FoundKey = $Parts[0].Trim()
        $Value = $Parts[1].Trim()

        if ($FoundKey -eq $Key) {

            $Value = $Value.Trim('"').Trim("'")

            return $Value
        }
    }

    return $null
}


# Read the configuration
$MaxSessions = Get-SimpleYamlValue `
    -Path $ConfigPath `
    -Key "max_sessions"

$MaxTurns = Get-SimpleYamlValue `
    -Path $ConfigPath `
    -Key "max_turns"

$MaxBudgetUsd = Get-SimpleYamlValue `
    -Path $ConfigPath `
    -Key "max_budget_usd"

$Model = Get-SimpleYamlValue `
    -Path $ConfigPath `
    -Key "model"

$PermissionMode = Get-SimpleYamlValue `
    -Path $ConfigPath `
    -Key "permission_mode"

$RestartDelaySeconds = Get-SimpleYamlValue `
    -Path $ConfigPath `
    -Key "restart_delay_seconds"

if ($MaxSessionsOverride -gt 0) {
    $MaxSessions = $MaxSessionsOverride
}

# Basic validation
if (-not $MaxSessions) {
    throw "max_sessions is missing from config.yaml"
}

if (-not $MaxTurns) {
    throw "max_turns is missing from config.yaml"
}

if (-not $MaxBudgetUsd) {
    throw "max_budget_usd is missing from config.yaml"
}

if (-not $Model) {
    throw "model is missing from config.yaml"
}

if (-not $PermissionMode) {
    $PermissionMode = "default"
}

if (-not $RestartDelaySeconds) {
    $RestartDelaySeconds = 3
}


$SupervisorStateDirectory = Join-Path `
    $ClaudeDirectory `
    "supervisor"

$SupervisorSessionsDirectory = Join-Path `
    $SupervisorStateDirectory `
    "sessions"

$SupervisorLogsDirectory = Join-Path `
    $SupervisorStateDirectory `
    "logs"

New-Item `
    -ItemType Directory `
    -Path $SupervisorSessionsDirectory `
    -Force |
    Out-Null

New-Item `
    -ItemType Directory `
    -Path $SupervisorLogsDirectory `
    -Force |
    Out-Null

    

[int]$MaxSessions = $MaxSessions
[int]$MaxTurns = $MaxTurns
[double]$MaxBudgetUsd = $MaxBudgetUsd
[int]$RestartDelaySeconds = $RestartDelaySeconds

Write-Host "Configuration:"
Write-Host "  Max sessions : $MaxSessions"
Write-Host "  Max turns    : $MaxTurns"
Write-Host "  Max budget   : `$$MaxBudgetUsd"
Write-Host "  Model        : $Model"
Write-Host "  Permission   : $PermissionMode"
Write-Host ""

# The main supervisor loop
for ($SessionNumber = 1; $SessionNumber -le $MaxSessions; $SessionNumber++) {

    Write-Host ""
    Write-Host "==============================================" -ForegroundColor DarkCyan
    Write-Host " Starting session $SessionNumber / $MaxSessions" -ForegroundColor DarkCyan
    Write-Host "==============================================" -ForegroundColor DarkCyan
    Write-Host ""

    try {

        & $SessionScript `
            -ProjectPath $ResolvedProjectPath `
            -PromptPath $PromptPath `
            -SessionNumber $SessionNumber `
            -MaxTurns $MaxTurns `
            -MaxBudgetUsd $MaxBudgetUsd `
            -Model $Model `
            -PermissionMode $PermissionMode

        $SessionExitCode = $LASTEXITCODE

    }
    catch {

        Write-Host ""
        Write-Host "Supervisor encountered an error:" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red

        $SessionExitCode = 1
    }

    $SessionStatePath = Join-Path `
        $StateDirectory `
        "current-session.json"

    $SessionStatus = "UNKNOWN"

    if (Test-Path $SessionStatePath) {

        try {

            $SessionState = Get-Content `
                $SessionStatePath `
                -Raw |
                ConvertFrom-Json

            $SessionStatus = $SessionState.status

        }
        catch {

            Write-Host "Could not read session state." -ForegroundColor Yellow
        }
    }

    Write-Host ""
    Write-Host "Session result:"
    Write-Host "  Exit code : $SessionExitCode"
    Write-Host "  Status    : $SessionStatus"
    Write-Host ""


    # termination behavior
    if ($SessionStatus -eq "COMPLETE") {

        Write-Host ""
        Write-Host "Claude reported COMPLETE." -ForegroundColor Green
        Write-Host "Stopping supervisor." -ForegroundColor Green
        break
    }

    if ($SessionStatus -eq "BLOCKED") {

        Write-Host ""
        Write-Host "Claude reported BLOCKED." -ForegroundColor Yellow
        Write-Host "Stopping supervisor." -ForegroundColor Yellow
        break
    }

    if ($SessionStatus -eq "FAILED") {

        Write-Host ""
        Write-Host "Claude reported FAILED." -ForegroundColor Red
        Write-Host "Stopping supervisor." -ForegroundColor Red
        break
    }

    if ($SessionNumber -eq $MaxSessions) {

        Write-Host ""
        Write-Host "Maximum session count reached." -ForegroundColor Yellow
        break
    }

    # Starts another session
    Write-Host ""
    Write-Host "Session requested continuation." -ForegroundColor Cyan
    Write-Host "Waiting $RestartDelaySeconds second(s)..."

    Start-Sleep -Seconds $RestartDelaySeconds
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " Supervisor stopped." -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""