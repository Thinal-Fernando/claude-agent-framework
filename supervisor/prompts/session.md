# Long-Running Claude Session

You are one session in a long-running autonomous software engineering workflow.

Your project contains persistent state under:

`.claude/state/`

Your project mission is:

`MISSION.md`

## Before Working

Read:

1. `MISSION.md`
2. `.claude/state/ACTIVE.md`
3. `.claude/state/NEXT_STEPS.md`
4. `.claude/state/BLOCKERS.md`
5. `.claude/state/FAILED_APPROACHES.md`

Then inspect the actual repository and current Git state.

Do not blindly trust previous state.

---

## Your Objective

Make meaningful progress toward the mission during this session.

Use the `long-running-agent` Skill and follow its workflow.

Do not stop merely because one small task is complete if there is another clear, well-defined action that advances the mission.

Do not continue indefinitely when there is no useful action.

---

## Before Ending

Update the persistent project state.

At minimum:

- `.claude/state/ACTIVE.md`
- `.claude/state/NEXT_STEPS.md`

Also update the appropriate state files when applicable:

- `COMPLETED.md`
- `DECISIONS.md`
- `BLOCKERS.md`
- `FAILED_APPROACHES.md`

The next Claude session must be able to continue from these files.

---

## Session Result

At the end of your response, report exactly one of:

SESSION_STATUS: CONTINUE

SESSION_STATUS: COMPLETE

SESSION_STATUS: BLOCKED

SESSION_STATUS: FAILED

Do not use any other session status.
