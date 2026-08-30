# Supervisor

The external lifecycle controller for the Claude Agent Framework. It owns when
sessions start and stop, so the model cannot decide its own lifetime.

## Layout

| File | Role |
|---|---|
| `cli.py` | Command line entry point (`python -m supervisor`) |
| `loop.py` | Multi-session loop and stop conditions |
| `session.py` | Runs one Claude Code session and classifies the outcome |
| `config.py` | Loads and validates `config.yaml` before spending money |
| `yamlmini.py` | Dependency-free YAML-subset parser |
| `config.yaml` | Supervisor configuration |
| `prompts/session.md` | Instructions given to each session |

## Running

From the framework root:

```powershell
.\start.ps1 -Project "C:\path\to\project"
.\start.ps1 -Project "C:\path\to\project" -MaxSessions 3
```

```bash
./start.sh --project /path/to/project --max-sessions 3
```

Or directly:

```bash
python -m supervisor --project /path/to/project
```

The target project must be a Git repository with the framework installed
(`scripts/install.ps1`).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Mission reported COMPLETE |
| 1 | Supervisor or configuration error |
| 2 | Stopped without completing (session cap, stop file, interrupt) |
| 3 | Mission reported BLOCKED |
| 4 | Mission reported FAILED |

## Stopping a run

Create `.agent/STOP` in the target project. The supervisor checks for it before
each session and exits cleanly. State on disk is preserved, so rerunning
resumes.

## What this phase does not do yet

These are real gaps, not oversights. Each is scheduled:

- **The agent cannot run your tests.** `acceptEdits` permits edits but not Bash,
  so a session that tries to verify its own work reports BLOCKED. Phase 1 fixes
  this by declaring project commands and granting them via `--allowed-tools`.
- No independent verification of Claude's claims (Phase 4).
- No cumulative budget breaker across sessions; the practical ceiling is
  `max_sessions * max_budget_usd` (Phase 5).
- No metrics, history compaction, or notifications (Phase 6).

Status still comes from a `SESSION_STATUS:` marker in the final message. It is
read from that message only, not the whole transcript, but it remains a
self-report. Phase 2 replaces it with a validated JSON schema and Phase 4 stops
trusting it.
