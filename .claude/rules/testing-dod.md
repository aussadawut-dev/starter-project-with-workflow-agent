# Testing and Definition of Done

Validation is proportional to semantic risk, not file count. Verification should find defects without multiplying the same expensive checks across every Worker.

## Validation waterfall

### Worker level

Every persistent change requires:

- read-back or diff inspection of changed files;
- focused tests for changed behavior;
- regression checks for adjacent public behavior when the diff makes them relevant;
- documentation/tracking/queue consistency;
- no secrets or runtime claim state staged.

A Worker should not run the entire repository suite merely because it is available when targeted validation gives equivalent evidence for the claimed slice.

### Integration level

At a combined workset checkpoint:

1. run combined targeted tests for the integrated diff;
2. run full suite/build **once** when required by the workset risk/DoD;
3. repeat the full suite only when there is observed flakiness/nondeterminism or an explicit release-certification requirement.

Do not make “full suite twice” a default habit. Repeated identical green runs without a stated reason spend compute/context without adding material evidence.

Agent-governance and queue changes additionally require, when the host exposes the recipes/commands:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_agent_governance.py
python3 scripts/agent_queue.py validate
```

If the execution gateway does not expose one of these commands, report it `NOT_RUN` with the access limitation rather than fabricating a pass.

## Compact evidence

Queue completion evidence is an index, not a diary.

Prefer at most a few concise entries such as:

```text
focused unit tests: PASS
typecheck/lint: PASS
integration build: PASS
manual scenario: PASS
artifact: docs/tracking/evidence/TCKxxx-Qxxxx.md
```

Long browser walkthroughs, investigation narratives, command transcripts, or multi-angle review prose belong in a referenced evidence artifact when they are materially useful. Do not copy the same narrative into the queue item, tracker, handoff, and final report.

A Lean handoff may include `artifactRefs`; the queue still requires enough evidence to prove completion without loading the artifact by default.

## Lean evidence freshness

When the Lean path is used for a tracked item:

- create the Git/toolchain evidence fingerprint only after the validations that justify completion;
- fingerprint HEAD plus staged, unstaged and untracked inputs; commit SHA alone is insufficient for a dirty worktree;
- treat any fingerprint/input mismatch as `STALE` and rerun the impacted validation before completion;
- never store raw diff/content, claim tokens or credential values in the evidence/finalize journal;
- finalization must be complete-once: an interrupted finalize reconciles from queue completion evidence and must not replay `complete`;
- `SYNCED` requires declared tracker markers to be present; later tracker drift returns to reconciliation-required rather than staying silently complete.

## MCP tool checks

For each changed tool verify:

- published schema equals accepted runtime arguments/defaults/bounds;
- permission profile and approval behavior;
- workspace/path boundary and symlink safety;
- stable success/error shape;
- size/pagination/output bounds;
- positive, invalid-input, denied, conflict, and failure-path tests;
- audit/observability behavior without secret leakage;
- documentation example validity.

## Queue checks

For queue runtime changes verify:

- two Workers cannot own one item;
- one Worker is limited to one item by default;
- dependency and capability filtering;
- exclusive-scope conflict prevention;
- token ownership;
- heartbeat and stale recovery;
- release/block/unblock;
- evidence requirement for completion;
- invalid JSON/missing dependency/cycle handling;
- atomic state behavior under interrupted operations where practical.

## Result states

Use:

- `PASS` — required evidence passed without change;
- `FIXED` — a finding was corrected and revalidated;
- `BLOCKED` — external decision, authority, or environment prevents completion;
- `FAIL` — required behavior is incorrect;
- `NOT_RUN` — validation was not run; reason required.

`NOT_RUN`, unresolved `FAIL`, or material `BLOCKED` prevents `DONE`.

## Definition of Done

A queue item is `DONE` only when its objective and acceptance criteria have evidence and the claim is closed.

A tracker/workset is `DONE` only when:

- all in-scope items are `DONE` or intentionally `CANCELLED` with rationale;
- no active/stale claims remain;
- acceptance criteria map to passing evidence;
- applicable security, approval, contract, and compatibility checks pass;
- required combined review has no unresolved blocker;
- documentation and indexes match actual behavior;
- requested commit/push/release/deploy actions succeeded;
- rollback/operational notes exist where relevant.

When implementation is complete but publication or live verification lacks authority, use `REVIEW`, not `DONE`.
