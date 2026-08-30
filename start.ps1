<#
.SYNOPSIS
    Thin launcher for the Claude Agent Framework supervisor.

.DESCRIPTION
    Locates a usable Python interpreter and hands off to the supervisor package.
    All real logic lives in Python so it behaves identically on every platform.

.EXAMPLE
    .\start.ps1 -Project C:\path\to\project
    .\start.ps1 -Project C:\path\to\project -MaxSessions 3
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Project,

    [Parameter(Mandatory = $false)]
    [int]$MaxSessions = 0,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = "Stop"

$FrameworkRoot = $PSScriptRoot

function Find-Python {
    foreach ($candidate in @("python", "python3", "py")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $command) { continue }
        # The Windows Store alias resolves but fails to run; probe it.
        try {
            $version = & $candidate -c "import sys; print(sys.version_info[0])" 2>$null
            if ($LASTEXITCODE -eq 0 -and $version -match "^3") { return $candidate }
        }
        catch { continue }
    }
    return $null
}

$Python = Find-Python

if (-not $Python) {
    Write-Error "Python 3 is required but was not found on PATH. Install Python 3.9 or newer."
}

$Arguments = @("-m", "supervisor", "--project", $Project)

if ($MaxSessions -gt 0) {
    $Arguments += @("--max-sessions", "$MaxSessions")
}

if ($Rest) {
    $Arguments += $Rest
}

Push-Location $FrameworkRoot
try {
    # Windows PowerShell 5.1 turns native stderr into ErrorRecords, which under
    # 'Stop' aborts on output the supervisor writes deliberately. Let the child
    # process own its own streams and report through its exit code.
    $ErrorActionPreference = "Continue"
    & $Python @Arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
