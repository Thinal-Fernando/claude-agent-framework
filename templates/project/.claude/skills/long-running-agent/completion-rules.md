# Completion Rules

Completion must be evidence-based.

## Level 1 — Implementation Complete

A requirement can be considered implemented when:

- the required code exists
- the implementation fits the existing architecture
- the relevant paths are connected correctly

This alone does NOT mean the mission is complete.

---

## Level 2 — Verification Complete

A requirement should be considered verified when applicable checks pass.

Examples:

- unit tests
- integration tests
- type checks
- lint
- build
- runtime verification

Only report checks that were actually executed.

---

## Level 3 — Mission Complete

The overall mission may be marked complete only when:

1. Required functionality is implemented.
2. Acceptance criteria in `MISSION.md` are satisfied.
3. Applicable verification passes.
4. No known blocker remains.
5. No known regression remains.
6. Persistent state accurately describes the final repository.

---

## If Verification Fails

Do not mark the mission complete.

Instead:

1. Record the failure.
2. Determine whether it is fixable.
3. Attempt a reasonable fix.
4. Re-run verification.
5. Update state.

---

## If Progress Is Blocked

Do not fabricate completion.

Record:

- exact blocker
- evidence
- attempts
- next required action

Then report that the mission is blocked.