# CLAUDE AGENT FRAMEWORK — MASTER PLAN (v2)

You are continuing implementation of a reusable, installable framework for running
long-lived, persistent, open-ended Claude Code agent loops.

Treat this document as the authoritative project context.

Do not redesign the architecture from scratch.
Do not skip phases.
Do not implement future phases prematurely.
Implement one phase at a time, make it runnable and tested, then stop.

This is version 2 of the plan. Version 1 was written against assumptions about
Claude Code that are no longer accurate. Section 3 records what was verified
experimentally; prefer it over memory, and re-verify before contradicting it.

============================================================

## 1. OVERALL GOAL

A reusable repository that installs into any software project and lets Claude Code
work productively for far longer than a single context window, by:

1. Starting Claude Code with a clearly defined mission.
2. Running a controlled, resource-capped session.
3. Persisting state outside the LLM context.
4. Verifying progress independently of what the model claims.
5. Deciding, externally, whether to continue.
6. Starting a fresh session that recovers from durable state.
7. Stopping when the mission is complete, blocked, unsafe, or unproductive.

The LLM context is disposable.
The repository, Git history, persistent state, and verification results are durable.

This is an open-ended agent loop. It is not an agent that runs forever, and it is
not one enormous Claude context.

============================================================

## 2. CORE ARCHITECTURE

```
  GitHub framework
        |
        v
  install into project  -->  MISSION.md  +  .agent/  +  .claude/
        |
        v
  supervisor selects profile and grants capabilities
        |
        v
  Claude Code session  <-- in-session gates (hooks) --> forced to fix before ending
        |
        v
  structured JSON result   (+ file fallback for hard stops)
        |
        v
  deterministic verification   (tests, build, diff - ignores the model's claims)
        |
        v
  supervisor decision
        |
        +-- COMPLETE --> final verification --> STOP
        +-- BLOCKED  --> human --> STOP
        +-- FAILED   --> classified recovery
        +-- CONTINUE --> fresh session (state injected automatically)
```

Separation of concerns:

| Concept | Owns |
|---|---|
| `CLAUDE.md` | Permanent project instructions |
| Skills | Reusable procedures |
| Hooks | Automatic, deterministic, in-session enforcement |
| Supervisor | Session lifecycle, limits, decisions |
| State | Durable working memory |
| Verification | Independent evidence |
| Mission | The objective |

============================================================

## 3. VERIFIED FACTS ABOUT CLAUDE CODE

Established experimentally against **Claude Code 2.1.241**. Items marked *(docs)*
come from official documentation but were not run directly. Re-verify before
assuming any of this still holds, and pin a minimum CLI version.

### 3.1 CLI behaviour

- `--max-turns` **works** but is **absent from `claude --help`**. Exceeding it ends
  the session with `subtype: "error_max_turns"`, `terminal_reason: "max_turns"`.
- `--max-budget-usd` works: `subtype: "error_max_budget_usd"`,
  `terminal_reason: "budget_exhausted"`.
- **Both hard stops return `result: null` and no `structured_output`.** Anything
  depending on the model's final report needs a file-based fallback.
- Reported `num_turns` is larger than the `--max-turns` value; it appears to count
  tool-result messages too. Do not treat them as the same unit.
- `--output-format json` returns `subtype`, `terminal_reason`, `num_turns`,
  `total_cost_usd`, `session_id`, `is_error`, `stop_reason`, `permission_denials`,
  `result`, and `structured_output` when `--json-schema` is supplied.
- `--json-schema` produces a validated `structured_output` object and works
  alongside real tool use.
- **Unknown CLI options are silently accepted, not rejected.** A mistyped flag does
  nothing and reports nothing. Never infer support from the absence of an error.
- The prompt can be delivered on **stdin**, avoiding argv length limits.
- On Windows the executable resolves to `claude.CMD`; `shutil.which` plus
  `subprocess` handles it without a shell.

### 3.2 Permissions — the operational bottleneck

- `acceptEdits` permits file edits but **not Bash**. An agent in this mode writes
  code and then cannot run the tests, so it reports BLOCKED the moment it tries to
  verify itself. Reproduced directly.
- `dontAsk` auto-denies everything not explicitly granted. This is the right mode
  for unattended runs because it never hangs on a prompt, but only once capabilities
  are actually granted.
- **`permissions.allow` in `.claude/settings.json` is silently ignored until the
  workspace is trusted.** A freshly installed project therefore has *no* granted
  capabilities:
  `Ignoring N permissions.allow entries ... this workspace has not been trusted.`
  This breaks unattended use on exactly the path the framework is built for.
- **`--allowed-tools` passed on the command line is not subject to workspace
  trust.** Verified: zero denials, tests ran, reported results matched reality.
  This is how the supervisor grants capability.
- `deny` rules apply immediately, without trust, and outrank allow rules, hooks, and
  `bypassPermissions`. Safety belongs there.
- *(docs)* Only `Edit(path)` and `Read(path)` file rules are consulted.
  `Write(...)`, `NotebookEdit(...)` and `MultiEdit(...)` path rules are accepted and
  then **never used**. A protected-paths feature written the obvious way silently
  does nothing.
- *(docs)* A `Read` deny rule also blocks Edit and Write on that path.

**Rule: capability grants go on the command line; safety rules go in settings.json.**

### 3.3 Hooks — the largest architectural lever

- A **`Stop` hook exiting 2 forces the session to keep working.** Verified: the
  model was told not to create a file, the gate failed with a message on stderr, and
  the model created the file and continued. Deterministic verification can therefore
  be enforced *inside* a session, costing a few turns instead of a whole new session.
- A **`SessionStart` hook can inject `additionalContext` in `-p` mode.** Verified:
  injected content was known to the session with zero tool calls. State can be loaded
  automatically instead of relying on the model to read six files, which also removes
  most of the per-session re-orientation cost.
- *(docs)* `PreToolUse` exit 2 blocks a tool call and outranks allow rules.
- *(docs)* `PreCompact` / `PostCompact` exist for context-loss recovery.
- *(docs)* `StopFailure` matches on `error_type`: `rate_limit`, `overloaded`,
  `server_error`, `authentication_failed`, `billing_error`. Transient failures are
  distinguishable from fatal ones for free.
- A blocking gate must be **bounded** by a counter, or a gate that can never pass
  will burn the entire budget.

### 3.4 Features that are already native

Do not rebuild these:

- Subagents via `.claude/agents/` with `model`, `tools`, `maxTurns`, `memory`,
  `isolation: worktree` *(docs)*.
- Git worktrees via `--worktree`, plus `WorktreeCreate` / `WorktreeRemove` hooks.
- Context compaction via `--autocompact`.
- Cross-session project context via `CLAUDE.md` and skills.

============================================================

## 4. DESIGN PRINCIPLES

**A. Do not trust the model's self-report.** "I completed the task" is an input to
verification, never a conclusion.

**B. Context is disposable.** Anything a future session needs must be on disk.

**C. The repository is authoritative.** When state files and the repository
disagree, inspect the repository and correct the state.

**D. Never lose progress.** Persist before a session can end.

**E. Do not repeat failed approaches.** Record them with enough evidence that a
future session can tell whether conditions changed.

**F. Do not overwrite user project state.** Installs and upgrades must be additive.

**G. Keep components modular.** No single script containing the system.

**H. Human control always exists.** Limits, a kill switch, clean resumption.

**I. Grant capability explicitly.** The agent gets exactly the commands the project
declares, no more, and never by disabling safety.

**J. Prefer deterministic enforcement over instruction.** If a hook or a deny rule
can guarantee something, do not merely ask the model for it in a prompt.

**K. Optimise useful progress per dollar,** not turns taken.

============================================================

## 5. IMPLEMENTATION STATUS

| Phase | Status |
|---|---|
| 0 — Correct the foundation | **Complete** |
| 1 — Project contract and capability grants | Not started |
| 2 — Structured session runner | Not started |
| 3 — In-session gates (hooks) | Not started |
| 4 — Out-of-session verification | Not started |
| 5 — Decision loop and recovery | Not started |
| 6 — Observability and durable knowledge | Not started |
| 7 — Public release packaging | Not started |

Earlier work that survives into v2: the installer, `MISSION.md`, the six
`.agent/state/` templates, the project `CLAUDE.md`, and the `long-running-agent`
skill. These are sound and should not be rewritten.

Before starting any phase, inspect the actual repository. Do not assume a component
exists because this document describes it.

============================================================

## 6. PHASES

### Phase 0 — Correct the foundation  *(complete)*

Ported the supervisor from PowerShell to a dependency-free Python package and fixed
the defects that would otherwise have been built upon.

- `supervisor/` package: `cli`, `loop`, `session`, `config`, `yamlmini`.
- `yamlmini.py` — YAML-subset parser that preserves nesting. The previous reader
  matched on key name alone and returned the first hit, so every profile block in
  Phase 2 would have resolved to `planning`'s values.
- Status is read from the **final assistant message only**, taking the last marker.
  The previous reader regexed the whole transcript and checked COMPLETE first, so a
  sentence like "I am not ready to report SESSION_STATUS: COMPLETE" ended the mission.
- Hard stops are distinguished from failures via `subtype` / `terminal_reason`.
- Prompt delivered on stdin; configuration validated before any spend.
- `start.ps1` / `start.sh` launchers; 54 standard-library tests.

### Phase 1 — Project contract and capability grants

The missing prerequisite. Without it the agent cannot verify its own work (see 3.2).

- `.agent/project.yaml`: `test`, `build`, `lint`, `typecheck`, custom checks,
  protected paths.
- Install-time auto-detection (pytest, npm, cargo, go, dotnet) that writes a
  **commented draft for the user to confirm**, never a silent assumption.
- `supervisor/capabilities.py`: contract to `--allowed-tools` argv.
- Installer writes **deny rules only** into `.claude/settings.json`, using
  `Edit(...)` / `Read(...)` and never `Write(...)`.
- Detect and report workspace trust state; offer an explicit, opt-in `--trust`.
- Switch `permission_mode` to `dontAsk` **in this phase, not before**.

### Phase 2 — Structured session runner

- Versioned `supervisor/schemas/session-result.schema.json`, passed via
  `--json-schema`.
- Read `structured_output`; **fall back to `.agent/state/session-result.json`** when
  a hard stop produced none.
- Profiles (planning, implementing, testing, debugging, reviewing, blocked,
  final_verification) setting `model`, `effort`, `max_turns`, `max_budget_usd`.
- Retire the `SESSION_STATUS:` marker convention.

Result fields: `status`, `phase`, `summary`, `current_objective`, `next_action`,
`meaningful_progress`, `blocked`, `blocker`, `requirements_completed`,
`requirements_remaining`, `tests_run`, `tests_passed`, `tests_failed`,
`files_changed`, `important_decisions`, `failed_approaches`.

None of these fields are authoritative. They are inputs to Phase 4.

### Phase 3 — In-session gates (hooks)

The phase that makes everything after it cheaper.

- `SessionStart` — inject a pre-rendered state digest so sessions spend no turns
  re-reading state.
- `Stop` — run fast checks; exit 2 with the failure on stderr to force a fix.
  **Bounded by a counter file** so a permanently failing gate escalates instead of
  looping.
- `Stop` — also require that `session-result.json` was written, which is what makes
  Phase 2's fallback reliable.
- `PreToolUse` — block protected-path edits.
- `PostToolUse(Edit|Write)` — incremental checkpoint.
- `PreCompact` / `PostCompact` — persist across compaction.

### Phase 4 — Out-of-session verification

Authoritative and independent of anything the model said.

- Before/after Git snapshots; changed-file and churn analysis.
- Run the contract's commands; parse pass/fail counts.
- Regression detection (was passing, now failing).
- **No-progress detection**: empty diff, or the same failure signature N sessions
  running.
- Emit `verification-result.json`, and log every disagreement with the self-report.

### Phase 5 — Decision loop and recovery

- State machine driven by verification, not self-report.
- COMPLETE requires an independent final-verification session.
- Failure classification from `StopFailure` types: `rate_limit`, `overloaded` and
  `server_error` back off and retry; `authentication_failed` and `billing_error`
  stop immediately.
- Circuit breakers: consecutive failures, no-progress limit, `max_sessions`,
  `max_total_budget_usd`.
- Kill switch via `.agent/STOP`; resume from disk after interruption.

### Phase 6 — Observability and durable knowledge

- `.agent/metrics/sessions.jsonl`, one row per session.
- `.agent/history/` with summarisation; `DECISIONS.md` and `FAILED_APPROACHES.md`
  survive compression.
- Optional notifications through one configurable command. No hardcoded service.

### Phase 7 — Public release packaging

- README with a real quickstart; per-phase documentation.
- Supervisor test suite runnable without API spend.
- `install.ps1` and `install.sh`; `framework-version` migration logic.
- `examples/` with a working mission and contract.

### Deferred

**Specialised subagents** and **parallel worktrees** are thin layers over native
features (3.4). Parallel agents additionally require merge reconciliation, which is
a hard problem and belongs after the system is stable. Build either only when a real
mission demands it.

============================================================

## 7. DEVELOPMENT WORKFLOW

For each phase:

1. **Inspect** the repository as it actually is.
2. **Compare** against this phase's requirements.
3. **Plan**: what is missing, what changes, and why.
4. **Implement** only this phase.
5. **Test** — actually run it. "Should work" is not a result.
6. **Inspect results**: exit codes, generated files, Git diff, logs, real output.
7. **Fix** what testing found.
8. **Document** user-visible behaviour.
9. **Version**: update `VERSION`.
10. **Report**: phase, status, implemented, files created, files modified, tests run,
    results, known limitations, next phase.
11. **Stop** for review and commit before starting the next phase.

Never leave the framework in a state where a phase half-lands. If a change would
break the working system until a later phase completes, do not make it early. The
`acceptEdits` to `dontAsk` switch is the canonical example.

============================================================

## 8. CODING RULES

Python is the core runtime. PowerShell and shell launchers stay thin.

- No third-party dependencies. It must work from a bare `git clone` with no
  `pip install`. Use the standard library, or vendor a small module.
- No hardcoded user names, project paths, or machine assumptions.
- Robust paths; parameters over constants.
- Meaningful exit codes; fail safely and loudly.
- Never delete project files automatically.
- Every project-specific command comes from configuration. Never assume `npm test`,
  `pytest`, or `go test ./...`.
- Configurable: model, effort, turn limits, budgets, retry limits, protected paths,
  notifications, approval requirements.

============================================================

## 9. VERSION CONTROL RULES

The framework is a reusable repository; project state belongs in the target project.

Never commit secrets, API keys, tokens, credentials, or machine-specific paths.
Never blindly overwrite existing project files. Framework upgrades need migration
logic keyed on `framework-version`.

============================================================

## 10. DO NOT

1. Build one giant script.
2. Put all state in one enormous checkpoint file.
3. Trust the model's self-reported completion.
4. Loop without limits.
5. Retry failures forever.
6. Let parallel agents share one mutable working tree.
7. Overwrite project configuration automatically.
8. Hardcode project-specific commands.
9. Commit secrets.
10. Add dependencies the standard library can cover.
11. Build every feature before testing the current phase.
12. Assume the context survives.
13. Treat the LLM as the supervisor.
14. Infer CLI support from the absence of an error; unknown flags are silently
    accepted (3.1).
15. Rely on `permissions.allow` in an untrusted workspace (3.2).

============================================================

## 11. SUCCESS CRITERIA

A user should be able to:

```
git clone <framework>
install into project
edit MISSION.md
confirm the detected project contract
start the supervisor
```

and get repeated cycles of: session, in-session gate, structured result,
verification, supervisor decision, fresh session.

The project must survive context exhaustion, session termination, supervisor
restart, machine restart, transient failures, and repeated dead ends without losing
important progress.

The system must remain reusable, modular, configurable, observable, safe, efficient,
recoverable, and Git-friendly.

**Honest caveat.** The value of this framework is bounded by the quality of the
target project's verification oracle. With a strong test suite, verification is a
real progress signal. Without one it degrades to "files changed and it compiles",
which cannot distinguish progress from motion. Where the oracle is weak, building
one is higher-leverage than running longer autonomous loops.
