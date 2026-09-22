# Testing and Definition of Done

Validation is proportional to semantic risk, not file count. Verification finds defects without multiplying expensive checks across every Worker.

## Validation waterfall

### Worker level

Every persistent change requires:

- read-back or diff inspection of changed files;
- focused tests for changed behavior;
- regression checks for adjacent public behavior when diff makes relevant;
- documentation/tracking/queue consistency;
- no secrets or runtime claim state staged.

Worker should not run entire repository suite merely because available when targeted validation gives equivalent evidence for claimed slice.

### Integration level

At a combined workset checkpoint:

1. run combined targeted tests for integrated diff;
2. run full suite/build **once** when required by workset risk/DoD;
3. repeat full suite only when observed flakiness/nondeterminism or explicit release-certification requirement.

Do not make “full suite twice” default habit. Repeated identical green runs without stated reason spend compute/context without adding material evidence.

Agent-governance and queue changes additionally require, when host exposes recipes/commands:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_agent_governance.py
python3 scripts/agent_queue.py validate
```

If execution gateway does not expose one of these commands, report `NOT_RUN` with access limitation rather than fabricating pass.

## Compact evidence

Queue completion evidence is index, not diary.

Prefer at most few concise entries like:

```text
focused unit tests: PASS
typecheck/lint: PASS
integration build: PASS
manual scenario: PASS
artifact: docs/tracking/evidence/TCKxxx-Qxxxx.md
```

Long browser walkthroughs, investigation narratives, command transcripts, multi-angle review prose belong in referenced evidence artifact when materially useful. Do not copy same narrative into queue item, tracker, handoff, final report.

Lean handoff may include `artifactRefs`; queue still requires enough evidence to prove completion without loading artifact by default.

## Lean evidence freshness

When Lean path is used for tracked item:

- create Git/toolchain evidence fingerprint only after validations justify completion;
- fingerprint HEAD plus staged, unstaged, untracked inputs; commit SHA alone insufficient for dirty worktree;
- treat any fingerprint/input mismatch as `STALE` and rerun impacted validation before completion;
- never store raw diff/content, claim tokens, credential values in evidence/finalize journal;
- finalization must be complete-once: interrupted finalize reconciles from queue completion evidence and must not replay `complete`;
- `SYNCED` requires declared tracker markers; later tracker drift returns to reconciliation-required rather than staying silently complete.

## MCP tool checks

For each changed tool verify:

- published schema equals accepted runtime arguments/defaults/bounds;
- permission profile and approval behavior;
- workspace/path boundary and symlink safety;
- stable success/error shape;
- size/pagination/output bounds;
- positive, invalid-input, denied, conflict, failure-path tests;
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
- `FIXED` — finding corrected and revalidated;
- `BLOCKED` — external decision, authority, environment prevents completion;
- `FAIL` — required behavior incorrect;
- `NOT_RUN` — validation not run; reason required.

`NOT_RUN`, unresolved `FAIL`, or material `BLOCKED` prevents `DONE`.

## Definition of Done

Queue item is `DONE` only when objective and AC have evidence and claim is closed.

Tracker/workset is `DONE` only when:

- all in-scope items are `DONE` or intentionally `CANCELLED` with rationale;
- no active/stale claims remain;
- AC map to passing evidence;
- applicable security, approval, contract, compatibility checks pass;
- required combined review has no unresolved blocker;
- documentation and indexes match actual behavior;
- requested commit/push/release/deploy actions succeeded;
- rollback/operational notes exist where relevant.

When implementation complete but publication or live verification lacks authority, use `REVIEW`, not `DONE`.
