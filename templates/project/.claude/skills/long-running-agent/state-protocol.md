# Persistent State Protocol

The `.claude/state/` directory is the persistent memory of the long-running agent.

Each file has a specific responsibility.

---

## ACTIVE.md

Purpose:

Represent the agent's current working state.

Keep it short.

Required information:

- Session
- Phase
- Current objective
- Current status
- Current problem
- Last successful action
- Next action
- Things not to repeat
- Last updated

Do not use it as a history log.

---

## COMPLETED.md

Purpose:

Record work that has been verified as completed.

Only record completed work when there is sufficient evidence.

Prefer entries grouped by session.

Do not mark work complete merely because code was written.

---

## NEXT_STEPS.md

Purpose:

Describe what should happen next.

Prioritize the actions.

Prefer concrete actions such as:

- Inspect `src/auth/token.go`
- Add a failing test for invalid audience
- Run the integration test
- Fix audience validation

Avoid vague entries such as:

- Continue working
- Finish implementation
- Fix things

---

## DECISIONS.md

Purpose:

Record decisions that future sessions must preserve.

Record:

- the decision
- why it was made
- alternatives considered
- consequences

Do not record trivial implementation details.

---

## BLOCKERS.md

Purpose:

Record problems that genuinely prevent progress.

A blocker should contain:

- the problem
- evidence
- what was tried
- current state
- what is required to unblock it

Remove or resolve blockers when they are no longer active.

Do not use BLOCKERS.md for ordinary test failures that the agent can reasonably fix.

---

## FAILED_APPROACHES.md

Purpose:

Prevent future agents from repeating unsuccessful approaches.

Record:

- what problem was being solved
- the approach attempted
- the observed result
- why it failed
- what evidence would justify trying it again

Do not record every minor mistake.

Record failures that are useful for future sessions.

---

# Consistency Rules

The state files must not contradict each other.

For example:

If `COMPLETED.md` says a feature is implemented but tests show it is broken, do not treat the feature as completely verified.

Correct the state.

The repository and actual command results are stronger evidence than previous agent claims.

---

# Minimal-State Principle

Do not duplicate the same information across every file.

Use:

ACTIVE.md
for the current situation.

COMPLETED.md
for completed work.

NEXT_STEPS.md
for upcoming work.

DECISIONS.md
for durable design decisions.

BLOCKERS.md
for current blockers.

FAILED_APPROACHES.md
for failed strategies.
