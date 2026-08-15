# Supervisor

The supervisor is the external lifecycle controller for the Claude Agent Framework.

## Responsibilities

The supervisor:

1. starts Claude Code
2. gives it the long-running-agent session instructions
3. limits session turns
4. limits per-session budget
5. records session metadata
6. records Claude output
7. checks the reported session status
8. starts another session when continuation is requested
9. stops when the mission reports COMPLETE, BLOCKED, or FAILED
10. stops at the configured maximum session count

## Current Limitations

- automatic verification
- Git checkpoint commits
- regression detection
- no-progress detection
- automatic recovery
- hooks
- notifications
- subagent orchestration
- structured JSON session status

These will be added in later phases.

## Running

```powershell id="kyl6dc"
.\run-agent.ps1 `
    -ProjectPath "C:\path\to\project"