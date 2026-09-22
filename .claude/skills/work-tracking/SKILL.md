---
name: work-tracking
description: Create, resume, and maintain Medium/Large requirement-to-delivery tracking, including acceptance criteria, decisions, task decomposition, queue mapping, validation evidence, handoff, and closure.
---

# Work Tracking

Use [the tracking rule](../../rules/tracking.md) as the authoritative policy.

## Preconditions

- The request authorizes a persistent change.
- Git/current-state inspection is available.
- Duplicate requirements and trackers have been checked.
- Material decisions are resolved or explicitly BLOCKED.

## Procedure

1. Capture or resume the IMP under `docs/waiting-implement/`.
2. Move selected work to `in-breakdown/`.
3. Create/resume `docs/tracking/TCKNNN-<topic>.md`.
4. Define testable ACs, decisions, impacts, risks, dependencies, and tasks.
5. Convert only queue-ready tasks into `.agents/queue/items/QNNNN.json`.
6. Keep queue item, TASK line, execution snapshot, and indexes synchronized.
7. Map all ACs to evidence.
8. Hand off at `REVIEW`, `BLOCKED`, or `DONE` truthfully.

Use [the tracker template](../../../docs/tracking/TEMPLATE.md) and [queue claim](../queue-claim/SKILL.md).

Tracking does not substitute for security, approval, contract, Git, test, or publication policy.
