# Requirement-to-Delivery Tracking

Tracking is durable record connecting requested outcome, accepted decisions, plan, queue ownership, implementation, evidence, handoff, closure.

Use [work tracking](../skills/work-tracking/SKILL.md) to execute this rule.

## Artifacts and identifiers

```text
IMP / requirement  docs/waiting-implement/imp-<topic>.md
Selected IMP       docs/waiting-implement/in-breakdown/imp-<topic>.md
Tracker            docs/tracking/TCKNNN-<topic>.md
Tracker task       TASK-NNN inside one tracker
Queue item         .agents/queue/items/QNNNN.json
```

Sequences are repository-local and stable. Do not renumber history. Queue item must reference exactly one tracker workset and task.

## When tracking is required

Create or resume tracking before implementation for:

- Medium/Large or multi-step work;
- workspace isolation, permissions, approvals, secrets, destructive behavior;
- tool schema/runtime/error contract changes;
- development command policy or process lifecycle changes;
- persistence/migration or public compatibility changes;
- cross-area integration, release, deployment;
- any task needing parallel Workers.

Read-only work and genuinely Small localized changes may skip tracker. Record Small-work exception in final report when risk non-obvious.

## Ordered lifecycle

### 1. Intake and locate

Capture requested outcome, actor, constraints, exclusions, source. Search current requirements and trackers before creating duplicate. Inspect actual repository and runtime state.

### 2. Classify impact

Record size/risk and impact on:

```text
workspace boundary
path/symlink/secret safety
permission and exact-operation approval
tool schema and runtime validation
error compatibility
process command policy
Git/publication
observability/audit
documentation and tests
```

Use `None` only after review.

### 3. Resolve decisions

Record confirmed decisions, reversible assumptions, dependencies, edge cases, open issues. Material unresolved issues make readiness `BLOCKED`.

### 4. Create plan and tracker

Create `TCKNNN-<topic>.md` from `docs/tracking/TEMPLATE.md`. Tasks begin at `TASK-001` in each tracker. Map every acceptance criterion to planned evidence.

### 5. Queue executable tasks

Only queue tasks that:

- single verifiable objective;
- known dependencies and decisions;
- primary files and exclusions named;
- independently ownable;
- capabilities, exclusive scopes, validation defined.

Tracker task may map to one or more queue items, but each queue item maps to one tracker task. Keep mapping explicit.

### 6. Claim, implement, validate

For each queue item:

```text
claim -> implement smallest safe slice -> validate -> collect evidence
      -> complete/block/release -> synchronize tracker immediately
```

Do not start next item while completed item or owning tracker task has stale state.

### 7. Review and handoff

Review combined workset against AC, queue ownership, risk, evidence. Record changed behavior, commands/results, limitations, rollback notes, publication state.

### 8. Publish and close

Commit, push, merge, release, deployment, external updates are separate authorized actions. Closure requires terminal in-scope items, synchronized tracking, passing evidence, no unresolved blocking review result.

## Status model

Tracker/workset:

```text
TODO -> IN_PROGRESS -> REVIEW -> DONE
                  \-> BLOCKED
```

Queue item durable status:

```text
TODO -> BLOCKED -> TODO
  \-> DONE
  \-> CANCELLED
```

`CLAIMED`, `READY`, `WAITING`, and `STALE_CLAIM` are derived queue states, not durable tracker statuses.

## Update discipline

Synchronize immediately after:

- decision changes;
- queue item created, completed, blocked, released, or cancelled;
- required validation passes or fails;
- scope/dependency changes;
- publication succeeds or is denied;
- new blocker appears.

Update order:

```text
queue item -> TASK line/evidence -> tracker status/snapshot -> indexes/requirement
```

Actual repository/runtime evidence outranks stale documents, but never silently overwrites accepted requirement or architecture decision. Record and route mismatch.

## Execution snapshot

Every active tracker maintains:

```text
Status:
Current item:
Next ready item:
Blocked by:
Dependencies:
Accepted decisions:
Active exclusive scopes:
Required review/gates:
Last validation:
Budget:
Publication:
```

Snapshot is resume pointer, not duplicate source of truth.

## Security

Do not store secrets, tokens, raw production data, private paths outside registered workspace, sensitive logs in requirements, trackers, queue items. Use redacted evidence.
