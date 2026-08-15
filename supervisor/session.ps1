[CmdletBinding()]
param(
    # Path to the project where Claude Code should run.
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,

    # Path to the file containing the prompt/instructions for Claude.
    [Parameter(Mandatory = $true)]
    [string]$PromptPath,

    # Number identifying which supervisor session this is.
    [Parameter(Mandatory = $true)]
    [int]$SessionNumber,

    # Maximum number of turns Claude is allowed to perform.
    [Parameter(Mandatory = $true)]
    [int]$MaxTurns,

    # Maximum amount of money Claude is allowed to spend on this session.
    [Parameter(Mandatory = $true)]
    [double]$MaxBudgetUsd,

    # Claude model that should be used for this session.
    [Parameter(Mandatory = $true)]
    [string]$Model,

    # Permission mode to pass to Claude Code.
    [Parameter(Mandatory = $true)]
    [string]$PermissionMode
)

# Makes PowerShell stop execution when a command encounters an error.
$ErrorActionPreference = "Stop"

# Switches the current working directory to the project directory.
Set-Location $ProjectPath

# Defines where persistent supervisor/session state files are stored.
$StateDirectory = Join-Path $ProjectPath ".agent\state"

# Make sure the project was initialized with the required supervisor state directory.
if (-not (Test-Path $StateDirectory)) {
    throw "Project does not contain .agent\state. Run the framework installer first."
}

# Generates a unique ID for this particular Claude session.
$SessionId = [guid]::NewGuid().ToString()

# Records the exact time when the session starts.
$StartedAt = Get-Date

# Defines the file used to store the current session's state.
$SessionStatePath = Join-Path $StateDirectory "current-session.json"

# Creates an object containing the initial state and configuration of the session.
$SessionState = @{
    session_id      = $SessionId
    session_number  = $SessionNumber
    started_at      = $StartedAt.ToString("o")
    status          = "RUNNING"
    model           = $Model
    max_turns       = $MaxTurns
    max_budget_usd  = $MaxBudgetUsd
    permission_mode = $PermissionMode
}

# Converts the session state object into JSON and saves it to the state file.
$SessionState |
    ConvertTo-Json -Depth 5 |
    Set-Content -Path $SessionStatePath -Encoding UTF8



# showing that a new supervisor session is starting.
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Claude Agent Session #$SessionNumber" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Displays the unique ID assigned to this session.
Write-Host "Session ID : $SessionId"

# Displays the project in which Claude will operate.
Write-Host "Project    : $ProjectPath"

# Displays the Claude model being used.
Write-Host "Model      : $Model"

# Displays the maximum number of allowed turns.
Write-Host "Max Turns  : $MaxTurns"

# Displays the maximum allowed budget in USD.
Write-Host "Max Budget : `$$MaxBudgetUsd"

Write-Host "Permission Mode : $PermissionMode"
Write-Host ""

# Reads the entire prompt file into a single string.
$Prompt = Get-Content $PromptPath -Raw

# Defines the file where Claude's complete output will be stored.
$OutputFile = Join-Path `
    $ProjectPath `
    ".agent\state\last-session-output.txt"


$SupervisorSessionDirectory = Join-Path `
    $ProjectPath `
    ".agent\sessions"

New-Item `
    -ItemType Directory `
    -Path $SupervisorSessionDirectory `
    -Force |
    Out-Null

$SessionLogFile = Join-Path `
    $SupervisorSessionDirectory `
    "session-$SessionNumber-$SessionId.txt"


# Lets the user know that Claude Code is about to start.
Write-Host "Starting Claude Code..." -ForegroundColor Yellow

try {
    $ClaudeArguments = @(
        "-p"
        "--model"
        $Model
        "--max-turns"
        $MaxTurns
        "--max-budget-usd"
        $MaxBudgetUsd
        "--permission-mode"
        $PermissionMode
        $Prompt
    )

    & claude @ClaudeArguments 2>&1 |
        Tee-Object -FilePath $OutputFile |
        Tee-Object -FilePath $SessionLogFile

    $ExitCode = $LASTEXITCODE
}
catch {
    $ExitCode = 1

    "Supervisor exception: $($_.Exception.Message)" |
        Out-File $OutputFile -Encoding UTF8
}

# Records the time at which the Claude session finished.
$FinishedAt = Get-Date

# Initializes an empty variable that will hold Claude's final output.
$Output = ""

# Check whether Claude produced an output file.
if (Test-Path $OutputFile) {

    # Read the complete output so the supervisor can determine what state Claude reported at the end of the session.
    $Output = Get-Content $OutputFile -Raw
}

# Look for the explicit completion marker produced by Claude.
if ($Output -match "SESSION_STATUS:\s*COMPLETE") {

    # Claude explicitly reported that the overall task is complete.
    $SessionStatus = "COMPLETE"
}
elseif ($Output -match "SESSION_STATUS:\s*BLOCKED") {

    # Claude reported that it cannot continue without external input, permissions, information, or another dependency.
    $SessionStatus = "BLOCKED"
}
elseif ($Output -match "SESSION_STATUS:\s*FAILED") {

    # Claude explicitly reported that the task failed.
    $SessionStatus = "FAILED"
}
else {

    # No final status marker was found. The supervisor assumes another session should continue the work.
    $SessionStatus = "CONTINUE"
}

# Creates the final state object containing both the original session information and the results of the completed Claude run.
$SessionState = @{
    session_id      = $SessionId
    session_number  = $SessionNumber
    started_at      = $StartedAt.ToString("o")
    finished_at     = $FinishedAt.ToString("o")
    status          = $SessionStatus
    exit_code       = $ExitCode
    model           = $Model
    max_turns       = $MaxTurns
    max_budget_usd  = $MaxBudgetUsd
}

# Converts the final session state to JSON and overwrites the previous RUNNING state with the final result.
$SessionState |
    ConvertTo-Json -Depth 5 |
    Set-Content -Path $SessionStatePath -Encoding UTF8

# Prints a summary of the completed Claude session.
Write-Host ""
Write-Host "Claude session finished." -ForegroundColor Green
Write-Host "Exit code : $ExitCode"
Write-Host "Status    : $SessionStatus"
Write-Host ""

# Return Claude's exit code to whatever script/process launched this supervisor script.
exit $ExitCode