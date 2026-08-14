# Claude Agent Framework

This project uses the Claude Agent Framework for long-running, checkpointed agent workflows.

## Mission

The overall project mission is defined in:

`MISSION.md`

Always read `MISSION.md` before beginning substantial work.

The mission defines the destination.

Do not use the mission file as a progress log.

---

## Persistent Agent State

The agent's persistent state is stored under:

`.claude/state/`

Important files:

- `ACTIVE.md` — current work and immediate objective
- `COMPLETED.md` — confirmed completed work
- `NEXT_STEPS.md` — highest-priority next actions
- `DECISIONS.md` — durable architectural decisions
- `BLOCKERS.md` — current blockers
- `FAILED_APPROACHES.md` — approaches that failed and should not be repeated without new evidence

Treat these files as persistent project state.

A fresh Claude Code session may have no useful conversational memory of previous sessions, so use these files to recover the current state. Claude Code sessions begin with a fresh context window, while project instructions provide persistent context across sessions. 

---

## Before Starting Work

Before making substantial changes:

1. Read `MISSION.md`.
2. Read `.claude/state/ACTIVE.md`.
3. Read `.claude/state/NEXT_STEPS.md`.
4. Read `.claude/state/BLOCKERS.md`.
5. Read `.claude/state/FAILED_APPROACHES.md`.
6. Inspect the actual repository.
7. Inspect the current Git status.
8. Verify that the recorded state matches the repository.

Do not blindly trust the state files.

The repository is authoritative about what actually exists.

---

## During Work

Work only toward the mission.

Prefer the smallest useful change that advances the current objective.

Do not:

- redo completed work without a reason
- repeat known failed approaches without new evidence
- modify unrelated parts of the repository
- claim something is complete without verification
- invent test results
- invent repository state
- mark a requirement complete merely because code was written

When an architectural decision is important and likely to affect future sessions, record it in:

`.claude/state/DECISIONS.md`

When an approach fails and should not be repeated, record it in:

`.claude/state/FAILED_APPROACHES.md`

When progress is blocked, record the blocker in:

`.claude/state/BLOCKERS.md`

---

## State Updates

Keep `.claude/state/ACTIVE.md` short.

It should answer:

- What phase are we in?
- What is the current objective?
- What is the current problem?
- What was the last successful action?
- What is the next action?
- What should not be repeated?

Do not turn `ACTIVE.md` into a historical log.

Put historical information in the appropriate state file instead.

---

## Verification

Do not consider a task complete merely because the implementation looks correct.

Whenever practical:

1. Run relevant tests.
2. Run relevant builds.
3. Run relevant lint/type checks.
4. Inspect the resulting Git diff.
5. Verify the changed behavior against the mission requirements.

Record important verification results in the persistent state.

---

## Session Completion

Before a session ends:

1. Update `.claude/state/ACTIVE.md`.
2. Update `.claude/state/COMPLETED.md` if work was completed.
3. Update `.claude/state/NEXT_STEPS.md`.
4. Update `.claude/state/BLOCKERS.md` if blocked.
5. Update `.claude/state/DECISIONS.md` for durable decisions.
6. Update `.claude/state/FAILED_APPROACHES.md` for failed approaches.
7. Verify that the state describes the actual repository.

The next Claude Code session must be able to continue from the state files without needing the previous conversation.

---

## Long-Running Agent Skill

The detailed long-running workflow is defined by:

`.claude/skills/long-running-agent/SKILL.md`

Use that Skill when operating as the autonomous long-running coding agent.

---

## General Rule

Treat conversational context as temporary.

Treat:

- source code
- Git history
- mission
- persistent state
- verified test results

as the durable project record.