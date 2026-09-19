# Requirement-to-Delivery Tracking

Tracking is the durable record that connects the requested outcome, accepted decisions, plan, queue ownership, implementation, evidence, handoff, and closure.

Use [work tracking](../skills/work-tracking/SKILL.md) to execute this rule.

## Artifacts and identifiers

```text
IMP / requirement  docs/waiting-implement/imp-<topic>.md
Selected IMP       docs/waiting-implement/in-breakdown/imp-<topic>.md
Tracker            docs/tracking/TCKNNN-<topic>.md
Tracker task       TASK-NNN inside one tracker
Queue item         .agents/queue/items/QNNNN.json
```

Sequences are repository-local and stable. Do not renumber history. A queue item must reference exactly one tracker workset and task.

## When tracking is required

Create or resume tracking before implementation for:

- Medium/Large or multi-step work;
- workspace isolation, permissions, approvals, secrets, or destructive behavior;
- tool schema/runtime/error contract changes;
- development command policy or process lifecycle changes;
- persistence/migration or public compatibility changes;
- cross-area integration, release, or deployment;
- any task needing parallel Workers.

Read-only work and genuinely Small localized changes may skip a tracker. Record the Small-work exception in the final report when risk is non-obvious.

## Ordered lifecycle

### 1. Intake and locate

Capture requested outcome, actor, constraints, exclusions, and source. Search current requirements and trackers before creating a duplicate. Inspect actual repository and runtime state.

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

Record confirmed decisions, reversible assumptions, dependencies, edge cases, and open issues. Material unresolved issues make readiness `BLOCKED`.

### 4. Create plan and tracker

Create `TCKNNN-<topic>.md` from `docs/tracking/TEMPLATE.md`. Tasks begin at `TASK-001` in each tracker. Map every acceptance criterion to planned evidence.

### 5. Queue executable tasks

Only queue tasks that:

- have a single verifiable objective;
- have known dependencies and decisions;
- name primary files and exclusions;
- can be owned independently;
- define capabilities, exclusive scopes, and validation.

A tracker task may map to one or more queue items, but each queue item maps to one tracker task. Keep the mapping explicit.

### 6. Claim, implement, validate

For each queue item:

```text
claim -> implement smallest safe slice -> validate -> collect evidence
      -> complete/block/release -> synchronize tracker immediately
```

Do not start the next item while the completed item or owning tracker task has stale state.

### 7. Review and handoff

Review the combined workset against acceptance criteria, queue ownership, risk, and evidence. Record changed behavior, commands/results, limitations, rollback notes, and publication state.

### 8. Publish and close

Commit, push, merge, release, deployment, and external updates are separate authorized actions. Closure requires terminal in-scope items, synchronized tracking, passing evidence, and no unresolved blocking review result.

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

- a decision changes;
- a queue item is created, completed, blocked, released, or cancelled;
- a required validation passes or fails;
- scope/dependency changes;
- publication succeeds or is denied;
- a new blocker appears.

Update order:

```text
queue item -> TASK line/evidence -> tracker status/snapshot -> indexes/requirement
```

Actual repository/runtime evidence outranks stale documents, but never silently overwrites an accepted requirement or architecture decision. Record and route the mismatch.

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
Publication:
```

This snapshot is a resume pointer, not a duplicate source of truth.

## Security

Do not store secrets, tokens, raw production data, private paths outside the registered workspace, or sensitive logs in requirements, trackers, or queue items. Use redacted evidence.
